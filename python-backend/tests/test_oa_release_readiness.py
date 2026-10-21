"""Nonproduction release checks; no cloud provider, dotenv or outbound mail."""
import csv
import io
import json
import os
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import mongomock
from bson import ObjectId
from openpyxl import load_workbook
from services.screening_export_service import COLUMNS, build_csv, build_xlsx, build_stage_export
from services.oa_operations import snapshot
from models.hiring_workflow import WorkflowError
from workflow_test_support import MongoTestCase, isolated_database
from test_workflow_foundation import migration_module


class ReleaseSecurityTests(unittest.TestCase):
    def test_all_export_paths_keep_formula_payloads_as_text(self):
        for payload in ('=1+1', '+cmd', '-cmd', '@SUM(1)', '  =1+1', '\ttext', '\rtext', '\ntext'):
            row = {field: '' for _, field in COLUMNS}
            row.update(student_name=payload, cv_score=80)
            exported = list(csv.reader(io.StringIO(build_csv([row]).decode('utf-8-sig'))))
            self.assertEqual(exported[1][0], "'"+payload)
            sheet = load_workbook(io.BytesIO(build_xlsx([row], 'job'))).active
            self.assertEqual(sheet['A2'].value, "'"+payload.replace('\r', '\n'))
            self.assertNotEqual(sheet['A2'].data_type, 'f')
            self.assertEqual(sheet['C2'].value, 80)
            stage = load_workbook(io.BytesIO(build_stage_export([{'name': payload}], 'xlsx'))).active
            self.assertEqual(stage['B2'].value, "'"+payload.replace('\r', '\n'))

    def test_rollout_examples_remain_explicitly_disabled(self):
        example = Path(__file__).resolve().parents[1] / '.env.example'
        entries = dict(line.split('=', 1) for line in example.read_text(encoding='utf-8').splitlines()
                       if line.startswith('GENHIRE_') and '=' in line)
        gates = [key for key in entries if key.endswith(('_ENABLED', '_ACCEPTED'))]
        self.assertGreaterEqual(len(gates), 15)
        for key in gates:
            self.assertEqual(entries[key].strip().lower(), 'false', key)

    def test_operations_snapshot_is_read_only_redacted_and_detects_backlog(self):
        db = mongomock.MongoClient().db
        now = datetime.now(timezone.utc)
        db.assessment_execution_tasks.insert_one(dict(state='queued', created_at=now-timedelta(minutes=10),
            question={'hidden': 'secret fixture'}, source='private source', owner_id='private identity'))
        db.company_messages.insert_one(dict(state='unknown', message='private message'))
        db.hiring_outbox.insert_one(dict(state='queued', due_at=now+timedelta(days=1), created_at=now-timedelta(days=1)))
        db.practice_generation_jobs.insert_one(dict(state='generating', lease_until=now-timedelta(seconds=1)))
        before = {name: list(db[name].find()) for name in db.list_collection_names()}
        result = snapshot(db, now)
        self.assertIn('execution:queued_over_5m', result['alerts'])
        self.assertIn('company_email:ambiguous_external_call', result['alerts'])
        self.assertIn('practice_generation:expired_external_lease_do_not_blindly_retry', result['alerts'])
        self.assertNotIn('notifications:queued_over_5m', result['alerts'])
        self.assertIn('execution:capacity_counter_mismatch_recheck_before_repair', result['alerts'])
        encoded = json.dumps(result)
        for secret in ('secret fixture', 'private source', 'private identity', 'private message'):
            self.assertNotIn(secret, encoded)
        self.assertEqual(before, {name: list(db[name].find()) for name in before})


class MigrationRestoreRehearsal(MongoTestCase):
    def test_dry_run_apply_replay_and_restore_to_separate_database(self):
        """Restore a BSON document/index snapshot into another disposable DB.

        This rehearses application-level backup semantics, not Atlas PITR or a
        production rollback that would erase accepted post-backup submissions.
        """
        db = self.db
        owner = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
        job_id = str(ObjectId())
        db.users.insert_one(owner)
        db.jobs.insert_one(dict(_id=ObjectId(job_id), created_by=str(owner['_id']), title='Legacy fixture'))
        db.applications.create_index([('job_id', 1), ('student_id', 1)], unique=True)
        db.applications.insert_many([
            dict(job_id=job_id, student_id=str(ObjectId()), status='screening_cleared', interview_score=80, processing_status='completed'),
            dict(job_id=job_id, student_id=str(ObjectId()), status='rejected', processing_status='completed')])
        original = {name: dict(documents=list(db[name].find()), indexes=db[name].index_information())
                    for name in db.list_collection_names()}
        migrate = migration_module().migrate
        report = migrate(db, job_id)
        self.assertEqual(report['counts'], {'eligible': 1, 'ambiguous_legacy': 1})
        self.assertEqual(original, {name: dict(documents=list(db[name].find()), indexes=db[name].index_information()) for name in db.list_collection_names()})
        first = migrate(db, job_id, apply=True, actor=owner)
        self.assertEqual(first['counts']['adopted'], 1)
        events = list(db.stage_events.find())
        migrate(db, job_id, apply=True, actor=owner)
        self.assertEqual(events, list(db.stage_events.find()))
        restored = isolated_database(self)
        for name, backup in original.items():
            if backup['documents']:
                restored[name].insert_many(backup['documents'])
            for index_name, spec in backup['indexes'].items():
                if index_name != '_id_':
                    restored[name].create_index(spec['key'], name=index_name,
                        **{key: spec[key] for key in ('unique', 'sparse', 'partialFilterExpression') if key in spec})
        self.assertEqual(original, {name: dict(documents=list(restored[name].find()), indexes=restored[name].index_information()) for name in restored.list_collection_names()})
        self.assertEqual(migrate(restored, job_id)['counts'], report['counts'])
        self.assertEqual(restored.stage_events.count_documents({}), 0)


class AdmissionDrainRehearsal(unittest.TestCase):
    def test_disabling_new_starts_preserves_accepted_saves_and_submission(self):
        import test_assessment_runtime as fixtures
        fixture = fixtures.RuntimeTests(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        started = fixture.start()
        with patch.dict(os.environ, {'GENHIRE_OA_RUNTIME_ENABLED': 'false'}):
            with self.assertRaises(WorkflowError) as error:
                fixture.runtime.start(fixture.actor, str(fixture.invitation['_id']), 'drain-block-start', 'oa-v1')
            self.assertEqual(getattr(error.exception, 'code', None), 'oa_runtime_not_ready')
            self.assertEqual(fixture.runtime.view(fixture.actor, fixture.identifier)['state'], 'in_progress')
            fixture.save()
            fixture.runtime.finalize(fixture.identifier, 'candidate', fixture.actor, 1)
            view = fixture.runtime.view(fixture.actor, fixture.identifier)
            self.assertNotEqual(view['state'], 'in_progress')
            self.assertEqual(fixtures.progression.utc(view['deadline']), fixtures.progression.utc(started['deadline']))
            self.assertEqual(fixture.db.assessment_submissions.count_documents({'attempt_id': fixture.identifier}), 1)

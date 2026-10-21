"""Configuration contracts plus real transaction/HTTP tests, with no cloud calls."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
import os
import unittest
from unittest.mock import patch
from bson import ObjectId
from flask import Flask
from werkzeug.datastructures import FileStorage
from workflow_test_support import MongoTestCase
from models.hiring_workflow import WorkflowError
from models.job_setup import default_setup, default_schedule, validate_setup, template, TEMPLATE_IDS, instant
from services.job_setup_service import JobSetupService, ensure_setup_indexes, quote, catalog, setup_reference, require_publishable_setup


class SetupContractTests(unittest.TestCase):
    def test_every_role_in_both_timer_modes_and_supported_dialects_contracts(self):
        for role in TEMPLATE_IDS:
            for timer in ('shared', 'section'):
                for engine in ('postgresql', 'mysql'):
                    for contract in ('stdin_stdout', 'function'):
                        with self.subTest(role=role, timer=timer, engine=engine, contract=contract):
                            c, preset = default_setup(), template(role)
                            c['pipeline']['oa_enabled'] = True
                            c['oa'].update(template_id=role, sections=preset['sections'], duration_minutes=preset['duration_minutes'],
                                timer_mode=timer, revisit_allowed=timer == 'shared', sql_engine=engine, coding_contract=contract)
                            self.assertEqual(validate_setup(c)['oa']['template_id'], role)

    def test_schedule_defaults_and_local_conversion(self):
        now = datetime(2030, 1, 1, 15, 30, tzinfo=timezone.utc)
        s = default_schedule(now)
        self.assertEqual(s['application_closes_at'], '2030-01-08T15:30:00Z')
        self.assertEqual(s['screening_closes_at'], '2030-01-11T15:30:00Z')
        self.assertEqual(s['oa_opens_at'], '2030-01-12T03:30:00Z')
        self.assertEqual(s['oa_start_closes_at'], '2030-01-13T03:30:00Z')
        c = default_setup(now)
        c['schedule']['application_closes_at'] = '2030-01-08T21:00'
        self.assertEqual(validate_setup(c)['schedule']['application_closes_at'], s['application_closes_at'])
        from zoneinfo import ZoneInfo
        for local in ('2030-03-10T02:30', '2030-11-03T01:30'):
            with self.assertRaises(WorkflowError):
                instant(local, ZoneInfo('America/New_York'), 'Window')
        self.assertEqual(instant('2030-11-03T01:30-04:00', ZoneInfo('America/New_York'), 'Window').hour, 5)
        dst_schedule = default_schedule(datetime(2030, 2, 26, 12, tzinfo=timezone.utc), 'America/New_York')
        parse = lambda key: datetime.fromisoformat(dst_schedule[key].replace('Z', '+00:00'))
        self.assertEqual(parse('oa_start_closes_at') - parse('oa_opens_at'), timedelta(hours=24))

    def test_invalid_nested_values_fail_with_contract_error(self):
        cases = [
            ('schema_version', True), ('pipeline.oa_enabled', 'true'), ('pipeline.company_stages', [None]),
            ('pipeline.company_stages', [{'id': 'screening', 'name': 'Collision'}]),
            ('qualification.interview_minimum', float('nan')), ('qualification.interview_minimum', True),
            ('qualification.oa_minimum', -1), ('qualification.proctoring_minimum', 101),
            ('oa.languages', [{}]), ('oa.languages', ['python', 'python']), ('oa.languages', ['ruby']),
            ('oa.sections', None), ('oa.sql_engine', 'sqlite'), ('oa.variant_count', 6), ('oa.duration_minutes', 0),
            ('oa.duration_minutes', 31.5), ('oa.source', 'unknown'), ('oa.coding_contract', 'shell'),
            ('schedule.timezone', 'not/a_timezone'), ('schedule.application_closes_at', ''),
        ]
        for path, value in cases:
            c = default_setup()
            target = c
            parts = path.split('.')
            for part in parts[:-1]: target = target[part]
            target[parts[-1]] = value
            with self.subTest(path=path, value=value), self.assertRaises(WorkflowError): validate_setup(c)
        for key, val in [('count', 101), ('count', True), ('marks', [1]), ('weight', 99),
                         ('duration_minutes', 0), ('difficulty', {'easy': 0, 'medium': 1, 'hard': 0})]:
            c = default_setup()
            c['oa']['sections'][0][key] = val
            with self.subTest(section=key), self.assertRaises(WorkflowError): validate_setup(c)

    def test_explicit_policies_and_timer_schedule_constraints(self):
        c = default_setup()
        self.assertEqual(validate_setup(c)['qualification']['interview_minimum'],60)
        self.assertEqual(validate_setup(c)['qualification']['proctoring_minimum'],70)
        c['pipeline']['advancement'] = 'automatic'
        c['qualification']['interview_minimum'] = None
        self.assertEqual(validate_setup(c)['qualification']['interview_minimum'],60)
        c['qualification']['interview_minimum'] = 0
        self.assertEqual(validate_setup(c)['qualification']['interview_minimum'], 0)
        c['qualification']['require_proctoring'] = True
        c['qualification']['proctoring_minimum'] = None
        self.assertEqual(validate_setup(c)['qualification']['proctoring_minimum'],70)
        c['qualification']['proctoring_minimum'] = 75
        validate_setup(c)
        c['oa']['timer_mode'] = 'section'
        with self.assertRaises(WorkflowError): validate_setup(c)
        c['oa']['revisit_allowed'] = False
        c['oa']['duration_minutes'] += 1
        with self.assertRaises(WorkflowError): validate_setup(c)
        c = default_setup()
        c['schedule']['screening_opens_at'] = c['schedule']['oa_opens_at']
        with self.assertRaises(WorkflowError): validate_setup(c)
        c = default_setup()
        c['schedule']['oa_start_closes_at'] = c['schedule']['oa_opens_at']
        with self.assertRaises(WorkflowError): validate_setup(c)

    def test_unknown_fields_and_candidate_question_content_cannot_be_saved(self):
        for path in ((), ('oa',), ('pipeline',), ('schedule',)):
            c = default_setup()
            target = c
            for name in path: target = target[name]
            target['questions'] = [{'answer': 'secret'}]
            with self.assertRaises(WorkflowError): validate_setup(c)
        from models.job_setup import validate_job_fields
        for fields in ({'questions': []}, {'minimum_cv_score': True}, {'proctoring_config': {'unknown': True}}):
            with self.assertRaises(WorkflowError): validate_job_fields(fields)

    def test_server_env_prices_quote_units_and_no_charge(self):
        c = default_setup()
        c['pipeline']['oa_enabled'] = True
        c['oa'].update(proctoring_level='dual', variant_count=3, advanced_analytics=True, plagiarism_check=True)
        with patch.dict(os.environ, {'RECRUITER_AI_JD_CREDITS': '17', 'GENHIRE_OA_JOB_SETUP_CREDITS': '41',
                'GENHIRE_OA_ATTEMPT_CREDITS': '', 'GENHIRE_DUAL_PROCTORING_CREDITS': '12'}):
            q = quote(c)
            self.assertEqual(q['charges_now'], 0)
            self.assertFalse(q['binding'])
            self.assertFalse(q['activation_available'])
            self.assertEqual(q['ai_jd_generation_credits'], 17)
            lines = {line['code']: line for line in q['line_items']}
            self.assertEqual(lines['oa_setup']['subtotal'], 41)
            self.assertEqual(lines['dual_proctoring']['subtotal'], 12)
            self.assertIsNone(lines['oa_attempt']['subtotal'])
            self.assertEqual(lines['variants']['quantity'], 2)
            self.assertNotEqual(lines['oa_setup']['unit'], lines['oa_attempt']['unit'])
            self.assertEqual(catalog()['prices']['ai_jd'], 17)
            with patch.dict(os.environ, {'GENHIRE_OA_JOB_SETUP_CREDITS': '-2'}):
                with self.assertRaises(WorkflowError): quote(c)
            with patch.dict(os.environ, {'GENHIRE_OA_JOB_SETUP_CREDITS': '42'}):
                self.assertNotEqual(quote(c)['price_version'], q['price_version'])

    def test_multipart_reference_hash_is_stable_and_restores_file_stream(self):
        d = {'setup_draft_id': str(ObjectId()), 'setup_draft_revision': '1', 'title': 'Role'}
        f = FileStorage(stream=BytesIO(b'job text'), filename='jd.txt')
        first = setup_reference(d, f)
        self.assertEqual(f.stream.tell(), 0)
        self.assertEqual(first, setup_reference(d, f))
        d['title'] = 'Other'
        self.assertNotEqual(first[2], setup_reference(d, f)[2])
        d['setup_draft_revision'] = True
        with self.assertRaises(WorkflowError): setup_reference(d)


class SetupPersistenceTests(MongoTestCase):
    def setUp(self):
        super().setUp()
        ensure_setup_indexes(self.db)
        self.service = JobSetupService(self.db)
        self.owner = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
        self.other = dict(_id=ObjectId(), user_type='recruiter', is_verified=True)
        self.configuration = default_setup()
        self.configuration['pipeline']['oa_enabled'] = True

    def draft(self, **kwargs):
        return self.service.save(self.owner, self.configuration, {'title': 'Role'}, 'create-draft-key', **kwargs)

    def job(self, status='draft'):
        return dict(_id=ObjectId(), created_by=str(self.owner['_id']), title='Role', status=status)

    def test_draft_revision_replay_and_owner_boundaries(self):
        d = self.draft()
        self.assertEqual(d, self.draft())
        self.assertEqual(self.db.job_setup_drafts.count_documents({}), 1)
        changed = deepcopy(self.configuration)
        changed['oa']['instructions'] = 'Focus on SQL'
        with self.assertRaises(WorkflowError):
            self.service.save(self.owner, changed, {}, 'create-draft-key')
        with self.assertRaises(WorkflowError): self.service.owned_draft(d['_id'], self.other)
        second = self.service.save(self.owner, changed, {}, 'update-draft-key', d['_id'], 1)
        self.assertEqual(second['revision'], 2)
        with self.assertRaises(WorkflowError):
            self.service.save(self.owner, changed, {}, 'stale-draft-key', d['_id'], 1)
        self.assertEqual(self.service.read_latest(self.owner)['revision'], 2)
        self.assertIsNone(self.service.read_latest(self.other))
        self.assertEqual(self.db.assessment_blueprints.count_documents({}), 0)

    def test_attach_is_atomic_immutable_separate_from_jd_and_does_not_enroll(self):
        d, j = self.draft(), self.job()
        saved = self.service.attach(self.owner, d['_id'], 1, j, 'job-request', creating=True)
        first_version = self.db.job_setup_versions.find_one({})
        self.assertEqual(saved['deadline'], self.configuration['schedule']['application_closes_at'])
        self.assertEqual(saved['hiring_setup_revision'], 1)
        self.assertEqual(self.db.jobs.count_documents({}), 1)
        replay = self.service.attach(self.owner, d['_id'], 1, self.job(), 'job-request', creating=True)
        self.assertEqual(saved['_id'], replay['_id'])
        blueprint = self.db.assessment_blueprints.find_one({})
        self.assertNotIn('description', blueprint)
        self.assertFalse(blueprint['question_content_ready'])
        self.assertEqual(self.db.hiring_workflow_versions.count_documents({}), 0)
        self.db.applications.insert_one({'job_id': str(j['_id']), 'status': 'shortlisted'})
        self.db.invites.insert_one({'job_id': str(j['_id']), 'status': 'sent'})
        apps, invites = list(self.db.applications.find()), list(self.db.invites.find())
        # A fresh editor starts from the current job revision, preserving the prior version.
        changed = deepcopy(self.configuration)
        changed['oa']['sql_engine'] = 'mysql'
        d2 = self.service.save(self.owner, changed, {}, 'edit-fresh-key', job_id=str(j['_id']))
        self.service.attach(self.owner, d2['_id'], 1, {'_id': j['_id'], 'description': 'Revised JD'}, 'edit-request')
        self.assertEqual(self.db.job_setup_versions.find_one({'_id': first_version['_id']}), first_version)
        self.assertEqual(self.db.job_setup_versions.count_documents({}), 2)
        self.assertEqual(list(self.db.applications.find()), apps)
        self.assertEqual(list(self.db.invites.find()), invites)
        view = self.service.get_job_setup(str(j['_id']), self.owner)
        self.assertEqual(view['version']['configuration']['oa']['sql_engine'], 'mysql')
        self.assertNotIn('source_request_hash', view['version'])
        with self.assertRaises(WorkflowError): self.service.get_job_setup(str(j['_id']), self.other)

    def test_failure_rolls_back_all_writes(self):
        d, j = self.draft(), self.job()
        from pymongo.collection import Collection
        original = Collection.insert_one
        def fail_jobs(collection, *args, **kwargs):
            if collection.name == 'jobs': raise RuntimeError('injected storage failure')
            return original(collection, *args, **kwargs)
        with patch.object(Collection, 'insert_one', fail_jobs):
            with self.assertRaises(RuntimeError): self.service.attach(self.owner, d['_id'], 1, j, 'request', creating=True)
        self.assertEqual(self.db.job_setup_versions.count_documents({}), 0)
        self.assertEqual(self.db.assessment_blueprints.count_documents({}), 0)
        self.assertEqual(self.db.jobs.count_documents({}), 0)
        self.assertIsNone(self.db.job_setup_drafts.find_one({})['job_id'])

    def test_oa_job_can_publish_immediately_without_activating_unready_assessment(self):
        d, j = self.draft(), self.job('active')
        saved = self.service.attach(self.owner, d['_id'], 1, j, 'request', creating=True)
        self.assertEqual(saved['status'],'active')
        self.assertEqual(saved['hiring_setup_status'],'draft')
        self.assertNotIn('active_hiring_version_id',saved)
        self.assertEqual(self.db.assessment_versions.count_documents({}),0)
        require_publishable_setup(self.db, saved, 'active')
        # A legacy active job can prepare OA without disturbing its live workflow/deadline.
        legacy = self.job('active')
        legacy['deadline'] = '2030-12-31'
        self.db.jobs.insert_one(legacy)
        edit = self.service.save(self.owner, self.configuration, {}, 'legacy-edit-key', job_id=str(legacy['_id']))
        updated = self.service.attach(self.owner, edit['_id'], 1, {'_id': legacy['_id']}, 'legacy-request')
        self.assertEqual(updated['status'], 'active')
        self.assertEqual(updated['deadline'], '2030-12-31')
        self.assertNotIn('workflow_version_id', updated)

    def test_stale_job_version_and_unverified_access_rejected(self):
        j = self.job()
        self.db.jobs.insert_one(j)
        a = self.service.save(self.owner, self.configuration, {}, 'editor-one-key', job_id=str(j['_id']))
        with self.assertRaises(WorkflowError):
            self.service.save(self.owner, self.configuration, {}, 'editor-second-create', job_id=str(j['_id']))
        b = self.service.save(self.owner, self.configuration, {}, 'editor-two-key', job_id=str(j['_id']), draft_id=a['_id'], expected_revision=1)
        with self.assertRaises(WorkflowError): self.service.attach(self.owner, a['_id'], 1, {'_id': j['_id']}, 'stale-first-request')
        self.service.attach(self.owner, b['_id'], 2, {'_id': j['_id']}, 'second-request')
        with self.assertRaises(WorkflowError):
            self.service.save(self.owner, self.configuration, {}, 'stale-save-key', job_id=str(j['_id']), draft_id=a['_id'], expected_revision=1)
        with self.assertRaises(WorkflowError):
            self.service.save(dict(self.owner, is_verified=False), self.configuration, {}, 'unverified-key')
        self.assertEqual(self.db.job_setup_versions.count_documents({}), 1)
        admin = dict(_id=ObjectId(), user_type='admin', permissions=['jobs.read'])
        self.assertEqual(self.service.get_job_setup(str(j['_id']), admin)['version']['revision'], 1)

    def test_http_roles_validation_flag_and_private_get(self):
        actor = [self.owner]
        def auth(fn):
            def wrapped(*args, **kwargs): return fn(actor[0], *args, **kwargs)
            wrapped.__name__ = fn.__name__
            return wrapped
        with patch('middleware.auth_middleware.token_required', auth):
            from routes.job_setup_routes import create_job_setup_routes
            # Decorators are bound while the factory runs, using its module binding.
            with patch('routes.job_setup_routes.token_required', auth):
                app = Flask(__name__)
                app.register_blueprint(create_job_setup_routes(self.db))
        client = app.test_client()
        self.assertTrue(client.get('/api/job-setup/catalog').json['workflow_enabled'])
        self.assertEqual(client.post('/api/job-setup/preview', json={'configuration': self.configuration}).status_code, 200)
        self.assertEqual(client.post('/api/job-setup/preview', json=[]).status_code, 400)
        with patch.dict(os.environ, {'GENHIRE_WORKFLOW_ENABLED': 'false'}):
            self.assertFalse(client.get('/api/job-setup/catalog').json['workflow_enabled'])
            self.assertEqual(client.post('/api/job-setup/preview', json={'configuration': self.configuration}).status_code, 404)
        actor[0] = dict(_id=ObjectId(), user_type='candidate')
        self.assertEqual(client.get('/api/job-setup/catalog').status_code, 403)
        self.assertEqual(client.get('/api/job-setup-drafts/latest').status_code, 403)

    def test_existing_job_controller_creation_edit_replay_and_publication_guards(self):
        from controllers.job_controller import JobController
        controller = JobController.__new__(JobController)
        controller.jobs_collection = self.db.jobs
        controller.users_collection = self.db.users
        controller.applications_collection = self.db.applications
        d = self.draft()
        payload = dict(title='Software Engineer', department='Engineering', location='Remote', type='Full-time',
            experience='2 years', salary='Competitive', description='Build products', skills=['Python'], status='draft',
            setup_draft_id=d['_id'], setup_draft_revision=1)
        result, status = controller.create_job(str(self.owner['_id']), payload, self.owner)
        self.assertEqual(status, 201, result)
        job_id = result['job']['_id']
        replay, status = controller.create_job(str(self.owner['_id']), payload, self.owner)
        self.assertEqual(status, 201, replay)
        self.assertEqual(replay['job']['_id'], job_id)
        self.assertEqual(self.db.jobs.count_documents({}), 1)
        published, status = controller.update_job(job_id, str(self.owner['_id']), {'status': 'active'}, self.owner)
        self.assertEqual(status, 200, published)
        self.assertTrue(self.configuration['pipeline']['oa_enabled'])
        # Updating an OA plan also preserves the published listing.
        d2 = self.service.save(self.owner, self.configuration, {}, 'disable-oa-key', job_id=job_id)
        edited, status = controller.update_job(job_id, str(self.owner['_id']), dict(status='active',
            setup_draft_id=d2['_id'], setup_draft_revision=1), self.owner)
        self.assertEqual(status, 200, edited)
        self.assertEqual(edited['job']['hiring_setup_revision'], 2)
        self.assertEqual(edited['job']['status'], 'active')
        self.assertNotIn('workflow_version_id', edited['job'])

    def test_first_create_with_oa_and_active_status_succeeds(self):
        from controllers.job_controller import JobController
        controller=JobController.__new__(JobController)
        controller.jobs_collection=self.db.jobs;controller.users_collection=self.db.users;controller.applications_collection=self.db.applications
        d=self.draft()
        payload=dict(title='First OA job',department='Engineering',location='Remote',type='Full-time',
            experience='2 years',salary='Competitive',description='Build products',skills=['Python'],status='active',
            setup_draft_id=d['_id'],setup_draft_revision=1)
        result,status=controller.create_job(str(self.owner['_id']),payload,self.owner)
        self.assertEqual(status,201,result);self.assertEqual(result['job']['status'],'active')
        self.assertEqual(self.db.assessment_versions.count_documents({}),0)
        self.assertEqual(controller.get_job_details(result['job']['_id'],'candidate',str(ObjectId()))[1],200)

    def test_public_job_and_bookmark_responses_never_expose_assessment_data(self):
        from controllers.job_controller import JobController
        from controllers.saved_job_controller import SavedJobController
        controller=JobController.__new__(JobController)
        controller.jobs_collection=self.db.jobs;controller.users_collection=self.db.users;controller.applications_collection=self.db.applications
        job=self.job('active');job.update(questions=[{'answer':'PRIVATE_OA_KEY'}],oa={'hidden_tests':'PRIVATE_CASE'},
            assessment_blueprint_id=str(ObjectId()),hiring_setup_version_id=str(ObjectId()),
            jd_gcs_path='private-jd-object',jd_extracted_text='PRIVATE_SOURCE',proctoring_config={'answers':'PRIVATE_NESTED_KEY'})
        self.db.jobs.insert_one(job);candidate=str(ObjectId())
        public,status=controller.get_job_details(str(job['_id']),'candidate',candidate)
        self.assertEqual(status,200);self.assertTrue(public['has_jd_document'])
        self.assertNotIn('PRIVATE',str(public));self.assertNotIn('hiring_setup_version_id',public)
        listing,status=controller.get_jobs('candidate',candidate)
        self.assertEqual(status,200);self.assertNotIn('PRIVATE',str(listing))
        invited,status=controller.get_jobs('candidate',candidate,user_doc={'is_invite_only':True,'invited_job_ids':[str(job['_id'])]})
        self.assertEqual(status,200);self.assertNotIn('PRIVATE',str(invited))
        saved=SavedJobController({name:self.db[name] for name in ('jobs','users','applications','saved_jobs')})
        saved.save_job(candidate,str(job['_id']));bookmarks,status=saved.list_saved_jobs(candidate)
        self.assertEqual(status,200);self.assertNotIn('PRIVATE',str(bookmarks))
        private,status=controller.get_job_details(str(job['_id']),'recruiter',str(self.owner['_id']))
        self.assertEqual(status,200);self.assertIn('PRIVATE_OA_KEY',str(private))
        self.assertEqual(controller.get_job_details(str(job['_id']),'recruiter',str(self.other['_id']))[1],403)

    def test_past_application_deadline_rejected_at_new_publication(self):
        c = default_setup(datetime.now(timezone.utc) - timedelta(days=30))
        d = self.service.save(self.owner, c, {}, 'expired-plan-key')
        with self.assertRaises(WorkflowError):
            self.service.attach(self.owner, d['_id'], 1, self.job('active'), 'expired-job', creating=True)
        self.assertEqual(self.db.jobs.count_documents({}), 0)

    def test_concurrent_replays_create_one_draft_job_and_blueprint(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as pool:
            drafts = list(pool.map(lambda _: self.draft(), range(3)))
        self.assertTrue(all(d == drafts[0] for d in drafts))
        d = drafts[0]
        def create(_):
            return self.service.attach(self.owner, d['_id'], 1, self.job(), 'concurrent-request', creating=True)
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs = list(pool.map(create, range(3)))
        self.assertTrue(all(j['_id'] == jobs[0]['_id'] for j in jobs))
        for collection in ('job_setup_drafts', 'job_setup_versions', 'assessment_blueprints', 'jobs'):
            self.assertEqual(self.db[collection].count_documents({}), 1)

    def test_admin_can_publish_oa_job_but_cannot_delete_its_workflow_history(self):
        from controllers.admin.job_admin import JobAdmin
        from types import SimpleNamespace
        d = self.draft()
        saved = self.service.attach(self.owner, d['_id'], 1, self.job(), 'admin-test-job', creating=True)
        admin = JobAdmin()
        admin.jobs_collection = self.db.jobs
        admin.job_repo = SimpleNamespace(find_one_by_id=lambda _: self.db.jobs.find_one({'_id': saved['_id']}))
        result, status = admin.update_job({}, str(saved['_id']), {'status': 'active'})
        self.assertEqual(status, 200, result)
        result, status = admin.delete_job({}, str(saved['_id']))
        self.assertEqual(status, 409, result)
        self.assertEqual(self.db.jobs.find_one({'_id': saved['_id']})['status'], 'active')


if __name__ == '__main__': unittest.main()


class SingleDraftTests(MongoTestCase):
    def setUp(self):
        super().setUp();ensure_setup_indexes(self.db)
        self.actor=dict(_id=ObjectId(),user_type='recruiter',is_verified=True)
        self.db.users.insert_one(self.actor);self.service=JobSetupService(self.db)
    def test_second_new_draft_requires_updating_existing_revision(self):
        first=self.service.save(self.actor,default_setup(),{'title':'Draft','description':'Role'},'single-draft-first')
        with self.assertRaises(WorkflowError) as error:self.service.save(self.actor,default_setup(),{'title':'Second'},'single-draft-second')
        self.assertEqual(error.exception.code,'draft_exists')
        revised=self.service.save(self.actor,default_setup(),{'title':'Revised'},'single-draft-update',draft_id=first['_id'],expected_revision=1)
        self.assertEqual(revised['_id'],first['_id']);self.assertEqual(revised['revision'],2)
        self.assertEqual(self.db.job_setup_drafts.count_documents({}),1)
    def test_concurrent_distinct_creates_leave_only_one_working_draft(self):
        from concurrent.futures import ThreadPoolExecutor
        def save(i):
            try:return self.service.save(self.actor,default_setup(),{'title':str(i)},'single-draft-concurrent-'+str(i))
            except WorkflowError as error:return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,range(2)))
        self.assertEqual(sum(isinstance(result,dict) for result in results),1)
        self.assertIn('draft_exists',results);self.assertEqual(self.db.job_setup_drafts.count_documents({}),1)

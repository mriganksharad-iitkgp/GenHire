"""Authored template contracts, SQL oracles, scoping and idempotent private seeding."""
import json
import sqlite3
import unittest
from copy import deepcopy
from bson import ObjectId
from models.job_setup import TEMPLATE_IDS, LANGUAGES
from models.assessment_content import blueprint_match, candidate_question
from models.hiring_workflow import WorkflowError
from services.role_assessment_templates import build_template, apply_template, coding
from services.assessment_authoring_service import AssessmentAuthoringService, ensure_authoring_indexes
from services.assessment_generation_service import parse_generated
from workflow_test_support import MongoTestCase

class RoleTemplateContractTests(unittest.TestCase):
    def test_all_presets_complete_private_and_match_both_sql_engines(self):
        for role in TEMPLATE_IDS:
            for engine in ('postgresql','mysql'):
                with self.subTest(role=role,engine=engine):
                    built=build_template(role,engine)
                    blueprint_match(built['oa'],built['questions'])
                    self.assertEqual(len({q['title'] for q in built['questions']}),len(built['questions']))
                    for q in built['questions']:
                        public=candidate_question(q)
                        self.assertNotIn('explanation',public)
                        if q['type']=='mcq':self.assertNotIn('correct_option_ids',public['mcq'])
                        if q['type']=='coding':
                            self.assertEqual(len(q['coding']['tests']),16)
                            self.assertNotIn('reference_solutions',public['coding'])
                            self.assertNotIn('tests',public['coding'])
    def test_sql_reference_matches_all_independent_fixtures(self):
        for q in build_template('data_analyst')['questions']:
            if q['type']!='sql':continue
            sql=q['sql']
            for d in sql['datasets']:
                with sqlite3.connect(':memory:') as conn:
                    conn.executescript(sql['schema_sql']+d['seed_sql'])
                    cursor=conn.execute(sql['reference_query'])
                    self.assertEqual([c[0] for c in cursor.description],d['columns'])
                    self.assertEqual([list(r) for r in cursor],d['expected_rows'])
    def test_small_coding_outputs_against_independent_enumeration(self):
        for task in ('sum','divisible','remainders','bits'):
            q=coding(task,'medium',1,LANGUAGES)
            for case in q['coding']['tests'][:6]:
                values=list(map(int,case['input'].split()));n=values[0]
                actual=sum(range(1,n+1)) if task=='sum' else sum(i%values[1] for i in range(n+1)) if task=='remainders' else sum(i%values[1]==0 or i%values[2]==0 for i in range(1,n+1)) if task=='divisible' else sum(i.bit_count() for i in range(n+1))
                self.assertEqual(int(case['expected']),actual)
    def test_generated_coding_requires_new_suite_size(self):
        q=coding('divisible','medium',1,['python'])
        spec=dict(type='coding',difficulty='medium',marks=1)
        self.assertEqual(len(parse_generated(json.dumps(dict(questions=[q])),[spec])),1)
        q['coding']['tests']=[q['coding']['tests'][0],q['coding']['tests'][-1]]
        with self.assertRaises(WorkflowError):parse_generated(json.dumps(dict(questions=[q])),[spec])
    def test_invalid_inputs_rejected(self):
        for args in [('missing',),('sde','sqlite'),('sde','postgresql',['ruby']),('sde','postgresql',[{}])]:
            with self.assertRaises(WorkflowError):build_template(*args)

class RoleTemplateStorageTests(MongoTestCase):
    def setUp(self):
        super().setUp();ensure_authoring_indexes(self.db)
        self.actor=dict(_id=ObjectId(),user_type='recruiter',is_verified=True)
        self.db.users.insert_one(self.actor);self.service=AssessmentAuthoringService(self.db)
    def test_apply_is_free_private_atomic_and_idempotent(self):
        first=apply_template(self.service,self.actor,'data_analyst','role-template-operation')
        again=apply_template(self.service,self.actor,'data_analyst','role-template-operation')
        self.assertEqual(first,again);self.assertEqual(len(first['questions']),22)
        self.assertEqual(self.db.question_versions.count_documents({}),22)
        self.assertEqual(self.db.credit_wallets.count_documents({}),0)
        self.assertEqual(self.db.assessment_versions.count_documents({}),0)
        other=dict(_id=ObjectId(),user_type='recruiter',is_verified=True)
        with self.assertRaises(WorkflowError):self.service.get_question(other,first['questions'][0]['_id'])
        with self.assertRaises(WorkflowError):apply_template(self.service,self.actor,'sde','role-template-operation')
    def test_unverified_actor_and_invalid_suite_cannot_save(self):
        with self.assertRaises(WorkflowError):apply_template(self.service,dict(self.actor,is_verified=False),'sde','role-unverified')
        q=coding('divisible','medium',1,['python']);q['coding']['tests']=[q['coding']['tests'][0],q['coding']['tests'][-1]]
        with self.assertRaises(WorkflowError):self.service.save_question(self.actor,q,'suite-bad-key',suite_policy='oa_test_suite_v2')
        self.assertEqual(self.db.question_versions.count_documents({}),0)
        self.service.save_question(self.actor,q,'legacy-key') # Existing v1 clients remain compatible.

    def test_http_template_seed_requires_verified_recruiter_and_supported_fields(self):
        from flask import Flask
        from unittest.mock import patch
        from routes.job_setup_routes import create_job_setup_routes
        actor=[self.actor]
        def auth(fn):
            def wrapped(*args,**kwargs):return fn(actor[0],*args,**kwargs)
            wrapped.__name__=fn.__name__
            return wrapped
        with patch('routes.job_setup_routes.token_required',auth):
            app=Flask(__name__);app.register_blueprint(create_job_setup_routes(self.db))
        client=app.test_client();url='/api/job-setup/templates/sde/apply'
        payload=dict(operation_key='template-http-operation',languages=['python'])
        result=client.post(url,json=payload)
        self.assertEqual(result.status_code,200)
        self.assertEqual(len(result.json['questions']),23)
        self.assertEqual(client.post(url,json=dict(payload,unexpected=True)).status_code,400)
        actor[0]=dict(_id=ObjectId(),user_type='candidate')
        self.assertEqual(client.post(url,json=payload).status_code,403)
        actor[0]=dict(self.actor,is_verified=False)
        self.assertEqual(client.post(url,json=payload).status_code,403)

    def test_partial_template_storage_failure_rolls_back_every_question(self):
        from unittest.mock import patch
        from pymongo.collection import Collection
        original=Collection.insert_one;count=[0]
        def fail(collection,*args,**kwargs):
            if collection.name=='question_versions':
                count[0]+=1
                if count[0]==3:raise RuntimeError('injected template write failure')
            return original(collection,*args,**kwargs)
        with patch.object(Collection,'insert_one',fail):
            with self.assertRaises(RuntimeError):apply_template(self.service,self.actor,'sde','template-failed-key')
        self.assertEqual(self.db.question_versions.count_documents({}),0)
        self.assertEqual(self.db.assessment_authoring_requests.count_documents({}),0)

"""Owner-scoped immutable content and revisioned assessment workspaces.

Publication is content publication only; it never sends invitations, changes
application stages, activates a job, or charges a wallet.
"""
from copy import deepcopy
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from core.mongo_transactions import atomic
from models.assessment_content import validate_question, blueprint_match
from models.hiring_workflow import WorkflowError
from models.job_setup import integer, text
from services.job_setup_service import JobSetupService
from services.workflow_service import operation_key, request_identity


def ensure_authoring_indexes(db):
    db.question_versions.create_index([('question_id', 1), ('revision', 1)], unique=True)
    db.question_versions.create_index([('owner_id', 1), ('pool', 1), ('created_at', -1), ('_id', -1)])
    db.assessment_workspaces.create_index('blueprint_id', unique=True)
    db.assessment_versions.create_index([('blueprint_id', 1), ('workspace_revision', 1)], unique=True)
    db.assessment_authoring_requests.create_index([('actor_id', 1), ('operation_key', 1)], unique=True)
    db.question_validations.create_index([('question_version_id', 1), ('created_at', -1)])
    db.question_reviews.create_index([('question_version_id', 1), ('created_at', -1)])
    db.assessment_content_audit.create_index([('owner_id', 1), ('created_at', -1)])
    db.assessment_validation_jobs.create_index([('state', 1), ('lease_until', 1), ('created_at', 1)])
    db.assessment_validation_jobs.create_index([('question_version_id', 1), ('created_at', -1)])
    db.assessment_executor_attestations.create_index('profile_hash', unique=True)


def object_id(value, label='ID'):
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        raise WorkflowError('invalid_id', f'Invalid {label}.', 400)
    return ObjectId(value)


class AssessmentAuthoringService:
    def __init__(self, db, validator=None):
        self.db, self.setup = db, JobSetupService(db)
        if validator is None:
            from services.managed_assessment_validator import ManagedAssessmentValidator
            validator = ManagedAssessmentValidator(db)
        self.validator = validator

    @staticmethod
    def serialize(value):
        return JobSetupService.serialize(value)

    def authorize(self, actor, write=False):
        self.setup.actor(actor, write=write)
        if write: self.setup.enabled()

    def blueprint(self, blueprint_id, actor, write=False, session=None):
        self.authorize(actor, write)
        value = self.db.assessment_blueprints.find_one({'_id': object_id(blueprint_id, 'blueprint ID')}, session=session)
        if not value: raise WorkflowError('not_found', 'Assessment blueprint not found.', 404)
        job = self.setup.job(value['job_id'], actor, write, session)
        if write and job.get('hiring_setup_version_id') != value['setup_version_id']:
            raise WorkflowError('stale_blueprint', 'This blueprint belongs to an older hiring setup. Reopen the current job.')
        return value

    def question(self, version_id, actor, write=False, session=None):
        self.authorize(actor, write)
        q = self.db.question_versions.find_one({'_id': object_id(version_id, 'question version ID')}, session=session)
        if not q: raise WorkflowError('not_found', 'Question version not found.', 404)
        if actor['user_type'] != 'admin' and q['owner_id'] != str(actor['_id']):
            raise WorkflowError('forbidden', 'Question belongs to another recruiter.', 403)
        if q['pool'] != 'recruitment': raise WorkflowError('forbidden', 'Recruitment and practice content cannot be mixed.', 403)
        return q

    def mutate(self, actor, key, payload, callback, allow_disabled=False):
        self.setup.actor(actor, write=True)
        if not allow_disabled: self.setup.enabled()
        key = operation_key(key)
        fingerprint = request_identity(payload)
        identity = dict(actor_id=str(actor['_id']), operation_key=key)
        def run(session):
            receipt = self.db.assessment_authoring_requests.find_one(identity, session=session)
            if receipt:
                if receipt['request_hash'] != fingerprint:
                    raise WorkflowError('idempotency_conflict', 'Operation key reused with different authoring content.')
                return deepcopy(receipt['result'])
            result = callback(session)
            self.db.assessment_authoring_requests.insert_one(dict(identity, request_hash=fingerprint, result=result,
                created_at=datetime.now(timezone.utc)), session=session)
            return result
        try: return atomic(self.db, run)
        except DuplicateKeyError: return atomic(self.db, run)

    def audit(self, actor, owner_id, action, target_id, session=None):
        self.db.assessment_content_audit.insert_one(dict(actor_id=str(actor['_id']), owner_id=owner_id,
            action=action, target_id=target_id, created_at=datetime.now(timezone.utc)), session=session)

    def save_question(self, actor, content, key, previous_version_id=None, blueprint_id=None, suite_policy=None):
        self.authorize(actor, True)
        if previous_version_id: self.question(previous_version_id, actor, True)
        if blueprint_id: self.blueprint(blueprint_id, actor, True)
        content = validate_question(content)
        if suite_policy not in (None, 'oa_test_suite_v2'):
            raise WorkflowError('invalid_suite_policy', 'Unsupported testcase policy.', 400)
        if suite_policy and content['type'] == 'coding' and not 15 <= len(content['coding']['tests']) <= 20:
            raise WorkflowError('invalid_test_suite', 'Coding questions require 15-20 testcases.', 400)
        allocated = ObjectId()
        def save(session):
            previous = self.question(previous_version_id, actor, True, session) if previous_version_id else None
            bp = self.blueprint(blueprint_id, actor, True, session) if blueprint_id else None
            owner_id = (previous or bp or {}).get('owner_id', str(actor['_id']))
            if previous and bp and previous['owner_id'] != bp['owner_id']:
                raise WorkflowError('forbidden', 'Question and blueprint owners differ.', 403)
            revision = 1
            question_id = str(allocated)
            if previous:
                question_id = previous['question_id']
                latest = self.db.question_versions.find_one({'question_id': question_id}, sort=[('revision', -1)], session=session)
                if latest['_id'] != previous['_id']: raise WorkflowError('stale_revision', 'Question changed; open its latest version.')
                revision = previous['revision'] + 1
            q = dict(_id=allocated, question_id=question_id, revision=revision, owner_id=owner_id, pool='recruitment',
                content=content, content_hash=request_identity(content), source='manual', suite_policy=suite_policy, created_by=str(actor['_id']),
                previous_version_id=previous_version_id, created_at=datetime.now(timezone.utc))
            self.db.question_versions.insert_one(q, session=session)
            self.audit(actor, owner_id, 'question_version_created', str(allocated), session)
            return self.serialize(q)
        return self.mutate(actor, key, dict(action='save_question', content=content, previous=previous_version_id, blueprint=blueprint_id, suite_policy=suite_policy), save)

    def get_question(self, actor, version_id):
        q = self.question(version_id, actor)
        self.audit(actor, q['owner_id'], 'private_question_read', version_id)
        result = self.serialize(q)
        quality = self.db.question_quality.find_one({'_id': q['_id']}) or {}
        validation = self.db.question_validations.find_one({'_id': ObjectId(quality['validation_id'])}) if quality.get('validation_id') else None
        review = self.db.question_reviews.find_one({'_id': ObjectId(quality['review_id'])}) if quality.get('review_id') else None
        result['validation'] = self.serialize(validation) if validation else None
        result['review'] = self.serialize(review) if review else None
        job = self.db.assessment_validation_jobs.find_one({'question_version_id': version_id}, sort=[('created_at', -1), ('_id', -1)])
        result['validation_job'] = dict(id=str(job['_id']), state=job['state'], error_code=job.get('error_code')) if job else None
        return result

    def bank(self, actor, after=None, limit=20, kind=None):
        self.authorize(actor)
        integer(limit, 'Page size', 1, 50)
        query = dict(owner_id=str(actor['_id']), pool='recruitment')
        if kind:
            if kind not in {'mcq', 'coding', 'sql'}: raise WorkflowError('invalid_type', 'Unsupported question type.', 400)
            query['content.type'] = kind
        if after: query['_id'] = {'$lt': object_id(after, 'cursor')}
        # List summaries never return answer keys/hidden datasets/reference source.
        rows = list(self.db.question_versions.find(query, {'content.title': 1, 'content.type': 1, 'content.difficulty': 1,
            'content.marks': 1, 'question_id': 1, 'revision': 1, 'created_at': 1}).sort('_id', -1).limit(limit + 1))
        self.audit(actor, str(actor['_id']), 'private_bank_list', after)
        return dict(items=[self.serialize(q) for q in rows[:limit]], next_cursor=str(rows[limit - 1]['_id']) if len(rows) > limit else None)

    def workspace(self, actor, blueprint_id):
        bp = self.blueprint(blueprint_id, actor)
        workspace = self.db.assessment_workspaces.find_one({'blueprint_id': blueprint_id})
        value = self.serialize(workspace) if workspace else dict(blueprint_id=blueprint_id, revision=0, question_version_ids=[])
        value['blueprint'] = self.serialize(bp)
        value['questions'] = [self.get_question(actor, version_id) for version_id in value['question_version_ids']]
        value['publication_requires'] = ['Exact blueprint counts, marks and difficulties', 'Validation for every language/contract/dialect',
            'Explicit human review of every question', 'Explicit final assessment approval']
        value['validator'] = self.validator.capabilities() if self.validator else dict(available=False,
            reason='Managed execution and SQL providers are not configured. Coding/SQL publication is blocked.')
        from services.assessment_generation_service import generation_enabled
        value['generation'] = dict(enabled=generation_enabled(), max_batch=5, max_job_batches=30,
            reason='AI generation requires an enabled worker and an explicitly approved credit reservation quote.')
        from services.assessment_generation_service import AssessmentGenerationService
        latest = self.db.assessment_generation_jobs.find_one({'blueprint_id': blueprint_id}, sort=[('created_at', -1), ('_id', -1)])
        value['generation']['latest_job'] = AssessmentGenerationService.public_job(latest) if latest else None
        funding = self.db.assessment_setup_funding.find_one({'_id': bp['job_id'], 'owner_id': bp['owner_id']})
        value['generation']['setup_hold'] = dict(state=funding['state'], credits=funding['credits']) if funding else None
        return value

    def save_workspace(self, actor, blueprint_id, ids, expected_revision, key):
        self.blueprint(blueprint_id, actor, True)
        integer(expected_revision, 'Workspace revision', 0, 1000000)
        if not isinstance(ids, list) or len(ids) > 120 or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
            raise WorkflowError('invalid_questions', 'Select up to 120 unique question versions.', 400)
        def save(session):
            bp = self.blueprint(blueprint_id, actor, True, session)
            existing = self.db.assessment_workspaces.find_one({'blueprint_id': blueprint_id}, session=session)
            if (existing or {}).get('revision', 0) != expected_revision: raise WorkflowError('stale_revision', 'Assessment workspace changed; reload.')
            logical = set()
            for version_id in ids:
                q = self.question(version_id, actor, True, session)
                if q['owner_id'] != bp['owner_id'] or q['question_id'] in logical:
                    raise WorkflowError('invalid_questions', 'Use one version of each question from this job owner’s bank.', 400)
                logical.add(q['question_id'])
            value = dict(blueprint_id=blueprint_id, job_id=bp['job_id'], owner_id=bp['owner_id'], revision=expected_revision + 1,
                question_version_ids=ids, updated_at=datetime.now(timezone.utc), updated_by=str(actor['_id']))
            self.db.assessment_workspaces.update_one({'blueprint_id': blueprint_id}, {'$set': value}, upsert=True, session=session)
            self.audit(actor, bp['owner_id'], 'assessment_workspace_saved', blueprint_id, session)
            return self.serialize(value)
        return self.mutate(actor, key, dict(action='save_workspace', blueprint=blueprint_id, ids=ids, revision=expected_revision), save)

    def validate(self, actor, version_id, key, commit_guard=None):
        q = self.question(version_id, actor, True)
        key = operation_key(key)
        prior = self.db.assessment_authoring_requests.find_one(dict(actor_id=str(actor['_id']), operation_key=key))
        if prior:
            from services.workflow_service import request_identity
            if prior['request_hash'] != request_identity(dict(action='validate', version=version_id)):
                raise WorkflowError('idempotency_conflict', 'Validation key reused with different content.')
            return prior['result']
        content = validate_question(q['content'])
        if content['type'] == 'mcq':
            evidence = dict(passed=True, validator='structural_mcq_v1', coverage=['mcq_structure'], execution_verified=False,
                note='Structural checks only. Recruiter must independently review answer correctness and ambiguity.')
        else:
            if self.validator is None:
                raise WorkflowError('validator_unavailable', 'Managed code/SQL validation is not configured; question cannot be approved or published.', 503)
            # Never put execution or network work inside a retried Mongo transaction.
            from services.assessment_validation import verify_reference_results
            evidence = verify_reference_results(content, self.validator.validate(q['content'], q['content_hash']))
        def save(session):
            if commit_guard and not commit_guard(session): raise WorkflowError('validation_lease_lost', 'Validation worker lease expired.')
            current = self.question(version_id, actor, True, session)
            record = dict(_id=ObjectId(), question_version_id=version_id, content_hash=current['content_hash'],
                evidence=deepcopy(evidence), passed=evidence.get('passed') is True, created_by=str(actor['_id']),
                created_at=datetime.now(timezone.utc))
            self.db.question_validations.insert_one(record, session=session)
            self.db.question_quality.update_one({'_id': current['_id']}, {'$set': {'validation_id': str(record['_id']),
                'review_id': None}, '$inc': {'revision': 1}}, upsert=True, session=session)
            self.audit(actor, q['owner_id'], 'question_validated', version_id, session)
            return self.serialize(record)
        return self.mutate(actor, key, dict(action='validate', version=version_id), save)

    def review(self, actor, version_id, validation_id, decision, reason, key):
        self.question(version_id, actor, True)
        if not isinstance(decision, str) or decision not in {'approve', 'reject'}: raise WorkflowError('invalid_review', 'Approve or reject the question.', 400)
        reason = text(reason, 'Review rationale', 2000)
        if len(reason) < 10: raise WorkflowError('invalid_review', 'Document the answer/ambiguity review in at least 10 characters.', 400)
        def save(session):
            q = self.question(version_id, actor, True, session)
            v = self.db.question_validations.find_one({'_id': object_id(validation_id, 'validation ID'), 'question_version_id': version_id}, session=session) if validation_id else None
            latest = self.db.question_validations.find_one({'question_version_id': version_id}, sort=[('created_at', -1), ('_id', -1)], session=session)
            if ((validation_id and (not v or not latest or latest['_id'] != v['_id'] or v['content_hash'] != q['content_hash']))
                    or (decision == 'approve' and (not v or not v['passed']))):
                raise WorkflowError('validation_required', 'A current successful validation is required before approval.')
            record = dict(_id=ObjectId(), question_version_id=version_id, content_hash=q['content_hash'], validation_id=validation_id,
                decision=decision, reason=reason, reviewed_by=str(actor['_id']), created_at=datetime.now(timezone.utc))
            self.db.question_reviews.insert_one(record, session=session)
            self.db.question_quality.update_one({'_id': q['_id']}, {'$set': {'review_id': str(record['_id'])},
                '$inc': {'revision': 1}}, upsert=True, session=session)
            self.audit(actor, q['owner_id'], 'question_' + decision, version_id, session)
            return self.serialize(record)
        return self.mutate(actor, key, dict(action='review', version=version_id, validation=validation_id, decision=decision, reason=reason), save)

    def publish(self, actor, blueprint_id, expected_revision, key, approved):
        self.blueprint(blueprint_id, actor, True)
        if approved is not True: raise WorkflowError('approval_required', 'Explicit assessment approval is required.', 400)
        integer(expected_revision, 'Workspace revision', 1, 1000000)
        def publish(session):
            bp = self.blueprint(blueprint_id, actor, True, session)
            ws = self.db.assessment_workspaces.find_one({'blueprint_id': blueprint_id}, session=session)
            if not ws or ws['revision'] != expected_revision: raise WorkflowError('stale_revision', 'Workspace changed; reload before publishing.')
            old = self.db.assessment_versions.find_one(dict(blueprint_id=blueprint_id, workspace_revision=expected_revision), session=session)
            if old: return self.serialize(old)
            questions = [self.question(i, actor, True, session) for i in ws['question_version_ids']]
            blueprint_match(bp['configuration'], [q['content'] for q in questions])
            evidence = []
            for q in questions:
                version_id = str(q['_id'])
                quality = self.db.question_quality.find_one({'_id': q['_id']}, session=session) or {}
                validation = self.db.question_validations.find_one({'_id': ObjectId(quality['validation_id'])}, session=session) if quality.get('validation_id') else None
                review = self.db.question_reviews.find_one({'_id': ObjectId(quality['review_id'])}, session=session) if quality.get('review_id') else None
                if not validation or not validation['passed'] or not review or review['decision'] != 'approve' or review['validation_id'] != str(validation['_id']) or review['content_hash'] != q['content_hash']:
                    raise WorkflowError('review_required', 'Every selected question requires current validation and explicit approval.')
                if q['content']['type']=='sql':
                    from config.assessment_execution import sql_enabled
                    if not sql_enabled(q['content']['sql']['engine']):raise WorkflowError('sql_engine_unavailable','PostgreSQL questions are trusted authoring only; publish enabled SQLite/DuckDB questions for candidates.',503)
                if q['content']['type'] != 'mcq':
                    capabilities = self.validator.capabilities()
                    if q['content']['type']=='sql' and not capabilities.get('sql_available'):
                        raise WorkflowError('sql_acceptance_required','SQL publication requires live controlled-dataset isolation acceptance.',503)
                    profile_hash = capabilities.get('profile_hash')
                    if (not capabilities['available'] or not profile_hash or validation['evidence'].get('execution_verified') is not True
                            or validation['evidence'].get('execution_id') != profile_hash + ':' + q['content_hash']):
                        raise WorkflowError('live_validation_required', 'The current execution profile must have a real validated reference run before publication.')
                    attested = self.db.assessment_executor_attestations.update_one({'profile_hash': profile_hash, 'state': 'passed',
                        'expires_at': {'$gt': datetime.now(timezone.utc)}, **({'sql_verified':True} if q['content']['type']=='sql' else {})}, {'$inc': {'publication_fence': 1}}, session=session)
                    if attested.matched_count != 1: raise WorkflowError('live_validation_required', 'Execution attestation expired or changed.')
                evidence.append(dict(question_version_id=version_id, validation_id=str(validation['_id']), review_id=str(review['_id'])))
                # Prevent snapshot write-skew with concurrent validation/rejection.
                self.db.question_quality.update_one({'_id': q['_id']}, {'$inc': {'publication_fence': 1}}, session=session)
            version = dict(_id=ObjectId(), blueprint_id=blueprint_id, job_id=bp['job_id'], setup_version_id=bp['setup_version_id'],
                owner_id=bp['owner_id'], pool='recruitment', workspace_revision=expected_revision, question_version_ids=ws['question_version_ids'],
                configuration=deepcopy(bp['configuration']), question_hashes=[q['content_hash'] for q in questions],
                review_evidence=evidence, state='published', activated=False, published_by=str(actor['_id']), created_at=datetime.now(timezone.utc))
            self.db.assessment_versions.insert_one(version, session=session)
            self.db.assessment_workspaces.update_one({'_id': ws['_id']}, {'$set': {'last_content_version_id': str(version['_id'])}}, session=session)
            self.db.jobs.update_one({'_id': ObjectId(bp['job_id'])}, {'$inc': {'assessment_content_revision': 1}}, session=session)
            self.audit(actor, bp['owner_id'], 'assessment_content_published', str(version['_id']), session)
            return self.serialize(version)
        return self.mutate(actor, key, dict(action='publish', blueprint=blueprint_id, revision=expected_revision, approved=True), publish)

"""Private draft configuration and pricing previews; never generates or sells an OA."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from config.workflow import workflow_enabled
from core.mongo_transactions import atomic
from models.hiring_workflow import WorkflowError
from models.job_setup import default_setup, validate_setup, validate_job_fields, template, TEMPLATE_IDS, LANGUAGES, JOB_FIELDS
from services.workflow_service import WorkflowService, operation_key, request_identity


def ensure_setup_indexes(db):
    db.job_setup_drafts.create_index([('owner_id', 1), ('job_id', 1), ('updated_at', -1)])
    db.job_setup_draft_requests.create_index([('owner_id', 1), ('operation_key', 1)], unique=True)
    db.job_setup_versions.create_index([('job_id', 1), ('revision', 1)], unique=True)
    db.job_setup_versions.create_index([('draft_id', 1), ('draft_revision', 1)], unique=True)
    db.assessment_blueprints.create_index([('job_id', 1), ('setup_version_id', 1)], unique=True)


def credit_setting(name, default=None):
    raw = os.getenv(name, str(default) if default is not None else '')
    if raw == '' and default is None:
        return None
    if not isinstance(raw, str) or not raw.isascii() or not raw.isdigit() or not 0 <= int(raw) <= 100000:
        raise WorkflowError('invalid_pricing_configuration', f'{name} must be a nonnegative integer up to 100000.', 503)
    return int(raw)


def prices():
    return dict(ai_jd=credit_setting('RECRUITER_AI_JD_CREDITS', 10),
        screening=credit_setting('RECRUITER_REAL_INTERVIEW_CREDITS', 30),
        screening_proctored=credit_setting('RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS', 50),
        oa_setup=credit_setting('GENHIRE_OA_JOB_SETUP_CREDITS', 0),
        oa_regeneration=credit_setting('RECRUITER_AI_JD_CREDITS', 10),
        oa_attempt=credit_setting('GENHIRE_OA_ATTEMPT_CREDITS'),
        mock_oa=credit_setting('GENHIRE_MOCK_OA_CREDITS', 30),
        dual_proctoring=credit_setting('GENHIRE_DUAL_PROCTORING_CREDITS', 10),
        camera_proctoring=credit_setting('GENHIRE_CAMERA_PROCTORING_CREDITS', 10),
        analytics=credit_setting('GENHIRE_ADVANCED_OA_ANALYTICS_CREDITS', 10),
        variants=credit_setting('GENHIRE_EXTRA_VARIANTS_CREDITS', 10),
        plagiarism=credit_setting('GENHIRE_PLAGIARISM_CHECK_CREDITS', 10))


def quote(configuration, now=None):
    setup = validate_setup(configuration)
    p = prices()
    now = now or datetime.now(timezone.utc)
    lines = []
    def add(code, label, unit, credits, quantity=1):
        lines.append(dict(code=code, label=label, unit=unit, credits=credits, quantity=quantity,
                          subtotal=None if credits is None else credits * quantity))
    if setup['pipeline']['oa_enabled']:
        if p['oa_setup']: add('oa_setup', 'Initial OA setup', 'once_per_job_on_activation', p['oa_setup'])
        add('oa_attempt', 'OA attempt', 'per_candidate_attempt', p['oa_attempt'])
        oa = setup['oa']
        if oa['proctoring_level'] == 'dual':
            add('dual_proctoring', 'Dual-device proctoring', 'per_candidate_attempt', p['dual_proctoring'])
        elif oa['proctoring_level'] == 'camera':
            add('camera_proctoring', 'Sampled camera monitoring', 'per_candidate_attempt', p['camera_proctoring'])
        if oa['variant_count'] > 1:
            add('variants', 'Additional validated variant batch', 'per_additional_batch', p['variants'], oa['variant_count'] - 1)
        if oa['advanced_analytics']:
            add('analytics', 'Enriched assessment report', 'per_assessment_version_report', p['analytics'])
        if oa['plagiarism_check']:
            add('plagiarism', 'Similarity report', 'per_submitted_attempt_report', p['plagiarism'])
    return dict(schema_version=1, price_version=request_identity(p), configuration_hash=request_identity(setup),
        quoted_at=now.isoformat(), expires_at=(now + timedelta(minutes=15)).isoformat(), line_items=lines,
        charges_now=0, binding=False, activation_available=False,
        activation_blockers=['Assessment questions must be authored, validated and reviewed before activation.']
            + (['Recruiter OA attempt pricing has not been configured.'] if setup['pipeline']['oa_enabled'] and p['oa_attempt'] is None else []),
        included=['Objective grading', 'Basic scores and section reports', 'Autosave and required security', 'Accessible controls'],
        ai_jd_generation_credits=p['ai_jd'], screening_credits=p['screening'], screening_proctored_credits=p['screening_proctored'])


def catalog():
    return dict(schema_version=1, workflow_enabled=workflow_enabled(), defaults=default_setup(),
        templates=[template(key) for key in TEMPLATE_IDS], languages=LANGUAGES, sql_engines=['sqlite', 'duckdb', 'postgresql'], postgres_candidate_execution=False,
        coding_contracts=['stdin_stdout', 'function'], question_sources=['ai', 'manual', 'hybrid'],
        prices=prices(), authoring_api=dict(version=2, combined_ai_drafts=True, full_role_templates=True), capabilities=dict(configuration=True, question_authoring=workflow_enabled(),
            ai_question_generation=workflow_enabled() and os.getenv('GENHIRE_ASSESSMENT_GENERATION_ENABLED', '').lower() == 'true',
            assessment_activation=workflow_enabled() and os.getenv('GENHIRE_SCHEDULING_ENABLED', '').lower() == 'true'),
        limits=dict(total_questions=120, coding_questions=10, sql_questions=10, mcq_questions=100, total_minutes=300, variants=5))


class JobSetupService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def actor(actor, write=False):
        role = actor.get('user_type')
        perms = actor.get('permissions', [])
        if role == 'admin' and ('*' in perms or ('jobs.write' if write else 'jobs.read') in perms):
            return
        if role != 'recruiter' or (write and actor.get('is_verified') is not True):
            raise WorkflowError('forbidden', 'An authorized recruiter is required.', 403)

    @staticmethod
    def enabled():
        WorkflowService.require_enabled()

    def job(self, job_id, actor, write=False, session=None):
        self.actor(actor, write=write)
        if not isinstance(job_id, str) or not ObjectId.is_valid(job_id):
            raise WorkflowError('invalid_id', 'Invalid job ID.', 400)
        job = self.db.jobs.find_one({'_id': ObjectId(job_id)}, session=session)
        if not job:
            raise WorkflowError('not_found', 'Job not found.', 404)
        if actor.get('user_type') != 'admin' and str(job.get('created_by')) != str(actor['_id']):
            raise WorkflowError('forbidden', 'You do not have access to this job.', 403)
        return job

    def owned_draft(self, draft_id, actor, session=None):
        if not isinstance(draft_id, str) or not ObjectId.is_valid(draft_id):
            raise WorkflowError('invalid_id', 'Invalid setup draft ID.', 400)
        draft = self.db.job_setup_drafts.find_one({'_id': ObjectId(draft_id), 'owner_id': str(actor['_id'])}, session=session)
        if not draft:
            raise WorkflowError('not_found', 'Setup draft not found.', 404)
        return draft

    @staticmethod
    def serialize(draft):
        def value_for(key, value):
            if key == '_id':
                return str(value)
            if isinstance(value, datetime):
                # BSON stores UTC milliseconds; first response and replay must match.
                return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat(timespec='milliseconds')
            return deepcopy(value)
        return {key: value_for(key, value) for key, value in draft.items() if key != 'request_hash'}

    def read_latest(self, actor, job_id=None):
        self.actor(actor)
        if job_id:
            self.job(job_id, actor)
        draft = self.db.job_setup_drafts.find_one(dict(owner_id=str(actor['_id']), job_id=job_id), sort=[('updated_at', -1), ('_id', -1)])
        return self.serialize(draft) if draft else None

    def save(self, actor, configuration, job_fields, key, draft_id=None, expected_revision=0, job_id=None):
        self.enabled()
        self.actor(actor, write=True)
        setup, details = validate_setup(configuration), validate_job_fields(job_fields)
        key = operation_key(key)
        if type(expected_revision) is not int or expected_revision < 0:
            raise WorkflowError('invalid_revision', 'Provide a nonnegative expected revision.', 400)
        if not draft_id and expected_revision != 0:
            raise WorkflowError('invalid_revision', 'A new draft starts at revision zero.', 400)
        if job_id is not None and (not isinstance(job_id, str) or not ObjectId.is_valid(job_id)):
            raise WorkflowError('invalid_id', 'Invalid job ID.', 400)
        fingerprint = request_identity(dict(configuration=setup, job_fields=details, draft_id=draft_id,
                                            expected_revision=expected_revision, job_id=job_id))
        allocated = ObjectId()
        def save(session):
            prior = self.db.job_setup_draft_requests.find_one(dict(owner_id=str(actor['_id']), operation_key=key), session=session)
            if prior:
                if prior['request_hash'] != fingerprint:
                    raise WorkflowError('idempotency_conflict', 'Draft operation key reused with different content.')
                return prior['result']
            # Serialize draft creation per owner/job without modifying historical versions.
            scope = request_identity(dict(owner_id=str(actor['_id']), job_id=job_id))
            self.db.job_setup_draft_heads.update_one({'_id': scope}, {'$inc': {'writes': 1}}, upsert=True, session=session)
            latest = self.db.job_setup_drafts.find_one(dict(owner_id=str(actor['_id']), job_id=job_id), sort=[('updated_at', -1), ('_id', -1)], session=session)
            applied = latest and self.db.job_setup_versions.find_one(dict(draft_id=str(latest['_id']), draft_revision=latest['revision']), session=session)
            if latest and not applied and (not draft_id or str(latest['_id']) != draft_id):
                raise WorkflowError('draft_exists', 'This job already has a working draft. Reload its saved revision before saving.', 409)
            existing = self.owned_draft(draft_id, actor, session) if draft_id else None
            if existing and existing.get('job_id') != job_id:
                raise WorkflowError('invalid_draft_scope', 'A draft cannot be moved between jobs.')
            if existing and existing['revision'] != expected_revision:
                raise WorkflowError('stale_revision', 'Draft changed; reload before saving.')
            job = self.job(job_id, actor, write=True, session=session) if job_id else None
            now = datetime.now(timezone.utc)
            draft = dict(_id=existing['_id'] if existing else allocated, owner_id=str(actor['_id']), job_id=job_id,
                revision=expected_revision + 1, schema_version=1, configuration=setup, job_fields=details,
                base_setup_revision=existing['base_setup_revision'] if existing else (job or {}).get('hiring_setup_revision', 0),
                created_at=existing['created_at'] if existing else now, updated_at=now)
            if existing:
                self.db.job_setup_drafts.replace_one({'_id': existing['_id'], 'revision': expected_revision}, draft, session=session)
            else:
                self.db.job_setup_drafts.insert_one(draft, session=session)
            result = self.serialize(draft)
            self.db.job_setup_draft_requests.insert_one(dict(owner_id=str(actor['_id']), operation_key=key,
                request_hash=fingerprint, draft_id=str(draft['_id']), result=result, created_at=now), session=session)
            return result
        try:
            return atomic(self.db, save)
        except DuplicateKeyError:
            return atomic(self.db, save)

    def get_job_setup(self, job_id, actor):
        self.actor(actor)
        job = self.job(job_id, actor)
        version = self.db.job_setup_versions.find_one({'_id': ObjectId(job['hiring_setup_version_id'])}) if job.get('hiring_setup_version_id') else None
        if version:
            version = self.serialize(version)
            version.pop('source_request_hash', None)
        return dict(version=version, authoring_enabled=workflow_enabled(), existing_application_count=self.db.applications.count_documents({'job_id': job_id}),
                    impact=('Activated for future applications; existing candidates retain their version until explicit enrollment.' if version and version.get('status') == 'active'
                        else 'Saved as a new configuration draft; existing applications and invitations retain their current workflow.'))

    def replay_creation(self, actor, draft_id, revision, request_hash):
        self.enabled()
        self.actor(actor, write=True)
        draft = self.owned_draft(draft_id, actor)
        existing = self.db.job_setup_versions.find_one(dict(draft_id=draft_id, draft_revision=revision))
        if existing:
            if existing['source_request_hash'] != request_hash:
                raise WorkflowError('idempotency_conflict', 'This draft revision was already attached with different job details.')
            return self.db.jobs.find_one({'_id': ObjectId(existing['job_id']), 'created_by': str(actor['_id'])})
        if draft['revision'] != revision or draft.get('job_id'):
            raise WorkflowError('stale_revision', 'Draft changed or belongs to an existing job.')
        return None

    def attach(self, actor, draft_id, revision, job_document, request_hash, creating=False):
        self.enabled()
        self.actor(actor, write=True)
        if type(revision) is not int or revision < 1:
            raise WorkflowError('invalid_revision', 'Provide the saved setup draft revision.', 400)
        job_id = str(job_document['_id'])
        version_id, blueprint_id = ObjectId(), ObjectId()
        def attach(session):
            draft = self.owned_draft(draft_id, actor, session)
            prior = self.db.job_setup_versions.find_one(dict(draft_id=draft_id, draft_revision=revision), session=session)
            if prior:
                if prior['source_request_hash'] != request_hash or (not creating and prior['job_id'] != job_id):
                    raise WorkflowError('idempotency_conflict', 'Draft revision already used with different job details.')
                return self.db.jobs.find_one({'_id': ObjectId(prior['job_id'])}, session=session)
            if draft['revision'] != revision or draft.get('job_id') not in (None, job_id):
                raise WorkflowError('stale_revision', 'Setup draft changed; reload it before saving the job.')
            setup = validate_setup(draft['configuration'])
            previous = None if creating else self.job(job_id, actor, write=True, session=session)
            effective_job = dict(previous or {}, **job_document)
            if not creating and draft.get('job_id') != job_id:
                raise WorkflowError('invalid_draft_scope', 'Save an editing draft for this job first.')
            base = (previous or {}).get('hiring_setup_revision', 0)
            if draft['base_setup_revision'] != base:
                raise WorkflowError('stale_revision', 'Another configuration version was saved; reload this job.')
            if effective_job.get('status') == 'active' and (previous or {}).get('status') != 'active':
                if datetime.fromisoformat(setup['schedule']['application_closes_at'].replace('Z', '+00:00')) <= datetime.now(timezone.utc):
                    raise WorkflowError('invalid_job_setup', 'Applications must close in the future when publishing a job.', 400)
            if setup['qualification']['require_proctoring'] and not any((effective_job.get('proctoring_config') or {}).values()):
                raise WorkflowError('invalid_job_setup', 'Required screening proctoring needs an enabled screening monitoring check.', 400)
            now = datetime.now(timezone.utc)
            owner_id = str(effective_job.get('created_by') or actor['_id'])
            version = dict(_id=version_id, schema_version=1, job_id=job_id, owner_id=owner_id,
                revision=base + 1, draft_id=draft_id, draft_revision=revision, status='draft', configuration=setup,
                source_request_hash=request_hash, created_at=now, created_by=str(actor['_id']))
            if setup['pipeline']['oa_enabled']:
                self.db.assessment_blueprints.insert_one(dict(_id=blueprint_id, job_id=job_id, owner_id=owner_id, created_by=str(actor['_id']),
                    setup_version_id=str(version_id), schema_version=1, status='draft', configuration=setup['oa'],
                    question_content_ready=False, created_at=now), session=session)
                version['assessment_blueprint_id'] = str(blueprint_id)
            self.db.job_setup_versions.insert_one(version, session=session)
            job_document.update(hiring_setup_version_id=str(version_id), hiring_setup_revision=base + 1, hiring_setup_status='draft')
            if creating or (previous or {}).get('status') == 'draft':
                job_document['deadline'] = setup['schedule']['application_closes_at']
            if creating:
                self.db.jobs.insert_one(job_document, session=session)
            else:
                self.db.jobs.update_one({'_id': previous['_id']}, {'$set': {k: v for k, v in job_document.items() if k != '_id'}}, session=session)
            self.db.job_setup_drafts.update_one({'_id': draft['_id']}, {'$set': {'job_id': job_id,
                'base_setup_revision': base + 1, 'updated_at': now}}, session=session)
            return self.db.jobs.find_one({'_id': ObjectId(job_id)}, session=session)
        try:
            return atomic(self.db, attach)
        except DuplicateKeyError:
            return atomic(self.db, attach)


def setup_request_hash(job_data, jd_file=None):
    import hashlib
    digest = None
    if jd_file and jd_file.filename:
        position = jd_file.stream.tell()
        content = jd_file.stream.read(10 * 1024 * 1024 + 1)
        jd_file.stream.seek(position)
        if len(content) > 10 * 1024 * 1024:
            raise WorkflowError('invalid_job_setup', 'JD attachment exceeds 10 MB.', 400)
        digest = hashlib.sha256(content).hexdigest()
    return request_identity(dict(job={k: v for k, v in job_data.items() if k in JOB_FIELDS}, jd_sha256=digest))


def setup_reference(job_data, jd_file=None):
    draft_id = job_data.get('setup_draft_id')
    if draft_id is None:
        if 'setup_draft_revision' in job_data:
            raise WorkflowError('invalid_draft', 'A setup draft ID is required.', 400)
        return None
    revision = job_data.get('setup_draft_revision')
    if isinstance(revision, str) and revision.isascii() and revision.isdigit():
        revision = int(revision)
    if not isinstance(draft_id, str) or not ObjectId.is_valid(draft_id) or type(revision) is not int or revision < 1:
        raise WorkflowError('invalid_draft', 'Provide a valid saved setup draft and revision.', 400)
    validate_job_fields({k: v for k, v in job_data.items() if k in JOB_FIELDS})
    return draft_id, revision, setup_request_hash(job_data, jd_file)


def require_publishable_setup(db, job, status):
    if status == 'active' and job.get('status') != 'active' and job.get('hiring_setup_version_id'):
        version = db.job_setup_versions.find_one({'_id': ObjectId(job['hiring_setup_version_id'])})
        if not version:
            raise WorkflowError('setup_unavailable', 'Saved hiring settings could not be loaded; retry before publishing.')
        closes = datetime.fromisoformat(version['configuration']['schedule']['application_closes_at'].replace('Z', '+00:00'))
        if closes <= datetime.now(timezone.utc):
            raise WorkflowError('invalid_job_setup', 'Applications must close in the future when publishing a job.', 400)

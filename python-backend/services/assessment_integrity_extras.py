"""Opt-in reviewed variant pools and transparent code-overlap review reports.

Private, bounded and quoted. Overlap is never a misconduct verdict or a score.
"""
from datetime import timedelta
import hashlib
import os
import re
from bson import ObjectId
from core.mongo_transactions import atomic
from models.hiring_workflow import WorkflowError
from services.assessment_authoring_service import object_id
from services.hiring_progression_service import utc
from services.job_setup_service import prices
from services.workflow_service import operation_key, request_identity


def enabled(kind): return os.getenv('GENHIRE_OA_'+kind.upper()+'_ENABLED', '').lower() == 'true'


def shingles(source, starter=''):
    # Literal starter removal avoids reporting an unchanged template as original
    # overlap evidence. Common/trivial solutions still require human judgment.
    tokens = re.findall(r'\w+|[^\w\s]', source.replace(starter, '') if starter else source)[:20000]
    return {hashlib.sha256('\x1f'.join(tokens[i:i+5]).encode()).hexdigest()[:24] for i in range(max(0, len(tokens)-4))}


class AssessmentIntegrityExtras:
    def __init__(self, runtime): self.runtime, self.db, self.clock = runtime, runtime.db, runtime.clock

    def scope(self, actor, kind, target, version_ids, session=None):
        if not enabled(kind): raise WorkflowError('optional_feature_unavailable', 'This optional integrity feature is not enabled or billable.', 503)
        if kind == 'variants':
            setup = self.db.job_setup_versions.find_one({'_id': object_id(target)}, session=session)
            if not setup: raise WorkflowError('not_found', 'Job setup version not found.', 404)
            self.runtime.setup.job(setup['job_id'], actor, True, session)
            if not isinstance(version_ids, list) or not 2 <= len(version_ids) <= 5 or len(set(version_ids)) != len(version_ids):
                raise WorkflowError('invalid_pool', 'Choose two to five distinct published, reviewed assessment versions.', 400)
            if len(version_ids) != setup['configuration']['oa']['variant_count']: raise WorkflowError('invalid_pool', 'Pool size must match the saved JD setup variant count.', 400)
            hashes, ids = set(), []
            for identifier in version_ids:
                content = self.runtime.checked_content(setup, identifier, actor, session)
                if content['configuration'] != setup['configuration']['oa']: raise WorkflowError('incompatible_pool', 'All variants must match the saved blueprint exactly.')
                for qid in content['question_version_ids']:
                    q = self.db.question_versions.find_one({'_id': object_id(qid)}, session=session)
                    if q['content_hash'] in hashes: raise WorkflowError('duplicate_variant_content', 'Variant sets must contain distinct reviewed content.')
                    hashes.add(q['content_hash'])
                ids.append(identifier)
            return dict(owner_id=setup['owner_id'], job_id=setup['job_id'], target_id=target, version_ids=ids, content_hash=request_identity(sorted(hashes)))
        if kind != 'similarity': raise WorkflowError('invalid_feature', 'Choose variants or similarity.', 400)
        attempt = self.db.assessment_attempts.find_one({'_id': object_id(target)}, session=session)
        if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
        if attempt.get('pool') == 'practice': raise WorkflowError('practice_extra_unavailable', 'Recruitment similarity does not access practice submissions.', 403)
        app = self.runtime.workflow.repo.application(attempt['application_id'], session)
        self.runtime.workflow.access(app, actor, True, session)
        if attempt['state'] != 'completed': raise WorkflowError('evaluation_required', 'Similarity reports require a completed objective evaluation.')
        peers = list(self.db.assessment_attempts.find({'owner_id': attempt['owner_id'], 'workflow_version_id': attempt['workflow_version_id'], 'state': 'completed'}, {'_id': 1}).sort('_id', 1).limit(101))
        if len(peers) > 100: raise WorkflowError('similarity_pilot_limit', 'This local review report supports up to 100 completed cohort attempts.', 503)
        submissions, source_bytes = [], 0
        for peer in peers:
            value = self.db.assessment_submissions.find_one({'attempt_id': str(peer['_id']), 'state': 'complete'}, session=session)
            if value:
                source_bytes += sum(len(a.get('source', '').encode()) for a in value['answers'].values())
                if source_bytes > 2000000: raise WorkflowError('similarity_pilot_limit', 'Comparison source budget exceeds the 2 MB local review limit.', 503)
            submissions.append(value)
        if any(not s or request_identity(s['answers']) != s['content_hash'] for s in submissions): raise WorkflowError('submission_changed', 'Immutable comparison submissions are unavailable.', 503)
        question_ids = [q['id'] for q in attempt['questions'] if q['type'] == 'coding']
        original = next((s for s in submissions if s['attempt_id'] == target), None)
        if not original or not any(original['answers'].get(qid, {}).get('source', '').strip() and any(s['attempt_id'] != target and s['answers'].get(qid, {}).get('source', '').strip() and s['answers'][qid].get('language') == original['answers'][qid].get('language') for s in submissions) for qid in question_ids):
            raise WorkflowError('comparison_unavailable', 'At least two comparable nonempty coding submissions are required before purchasing this report.', 409)
        return dict(owner_id=attempt['owner_id'], job_id=app['job_id'], target_id=target,
            submissions=[dict(id=str(s['_id']), attempt_id=s['attempt_id'], hash=s['content_hash']) for s in submissions],
            question_ids=question_ids)

    def quote(self, actor, kind, target, version_ids=None):
        scope = self.scope(actor, kind, target, version_ids)
        price = prices()['variants' if kind == 'variants' else 'plagiarism']
        amount = price*(len(version_ids)-1) if kind == 'variants' else price
        value = dict(_id=ObjectId(), kind=kind, scope=scope, credits=amount, price=price, actor_id=str(actor['_id']),
            expires_at=self.clock()+timedelta(minutes=10), created_at=self.clock())
        self.db.assessment_integrity_quotes.insert_one(value)
        return dict(quote_id=str(value['_id']), credits=amount, kind=kind, expires_at=value['expires_at'],
            impact='Applies to future invitations; accepted and existing invitations remain pinned.' if kind == 'variants' else 'Token-overlap suggestions only; no score, misconduct verdict or advancement change.')

    def confirm(self, actor, quote_id, key, accepted):
        operation_key(key)
        if accepted is not True: raise WorkflowError('approval_required', 'Approve the quoted optional feature cost.', 400)
        billing = self.runtime.billing
        def create(session):
            quote = self.db.assessment_integrity_quotes.find_one({'_id': object_id(quote_id), 'actor_id': str(actor['_id'])}, session=session)
            if not quote: raise WorkflowError('not_found', 'Quote not found.', 404)
            if quote.get('result'): return quote['result']
            if utc(quote['expires_at']) <= self.clock(): raise WorkflowError('quote_expired', 'Preview a fresh optional feature quote.')
            kind, previous = quote['kind'], quote['scope']
            scope = self.scope(actor, kind, previous['target_id'], previous.get('version_ids'), session)
            if scope != previous or prices()['variants' if kind == 'variants' else 'plagiarism'] != quote['price']: raise WorkflowError('quote_changed', 'Content, comparison cohort or price changed; preview again.')
            collection = self.db.assessment_variant_pools if kind == 'variants' else self.db.assessment_similarity_reports
            existing = collection.find_one({'_id': scope['target_id']}, session=session)
            if existing:
                if kind == 'variants' and existing['version_ids'] != scope['version_ids']: raise WorkflowError('pool_already_pinned', 'A pool is already pinned for this workflow version.')
                result = dict(id=scope['target_id'], kind=kind, replayed=True)
            else:
                if kind == 'variants':
                    report = dict(_id=scope['target_id'], **scope, allocation_counts=[0]*len(scope['version_ids']), created_at=self.clock())
                else:
                    report = dict(_id=scope['target_id'], **scope, pairs=self.compare(scope, session), algorithm='literal-token-5gram-jaccard-v1',
                        warning='Common algorithms, templates, short solutions and accommodations can overlap. Human review is required; this is not proof of plagiarism.',
                        objective_score_unchanged=True, created_at=self.clock(), delete_after=self.clock()+timedelta(days=180))
                if quote['credits']:
                    billing_key='oa-integrity:'+str(quote['_id'])
                    billing.reserve(scope['owner_id'], 'recruiter', quote['credits'], billing_key, 'oa_'+kind, session=session)
                    billing.settle(scope['owner_id'], 'recruiter', billing_key, 'capture', session=session)
                collection.insert_one(report, session=session)
                result = dict(id=scope['target_id'], kind=kind, credits_captured=quote['credits'])
            self.db.assessment_integrity_quotes.update_one({'_id': quote['_id']}, {'$set': {'result': result}}, session=session)
            return result
        return atomic(self.db, create)

    def compare(self, scope, session):
        submissions = {s['attempt_id']: self.db.assessment_submissions.find_one({'_id': object_id(s['id'])}, session=session) for s in scope['submissions']}
        original = submissions.get(scope['target_id'])
        if not original: raise WorkflowError('submission_changed', 'Original comparison submission is unavailable.', 503)
        pairs = []
        for qid in scope['question_ids']:
            q = self.db.question_versions.find_one({'_id': object_id(qid)}, session=session)
            answer = original['answers'].get(qid, {})
            if not q or not answer.get('source'): continue
            left = shingles(answer['source'], q['content']['coding']['starter_code'].get(answer.get('language'), ''))
            if not left: continue
            for attempt_id, submission in submissions.items():
                if attempt_id == scope['target_id']: continue
                other = submission['answers'].get(qid, {})
                if other.get('language') != answer.get('language'): continue
                right = shingles(other.get('source', ''), q['content']['coding']['starter_code'].get(other.get('language'), ''))
                if not right: continue
                overlap = len(left & right); union = len(left | right)
                if overlap: pairs.append(dict(question_version_id=qid, peer_attempt_id=attempt_id, overlap_percentage=round(100*overlap/union, 2), shared_shingles=overlap, original_shingles=len(left)))
        return sorted(pairs, key=lambda p: p['overlap_percentage'], reverse=True)[:20]

    def report(self, actor, attempt_id):
        attempt = self.db.assessment_attempts.find_one({'_id': object_id(attempt_id)})
        if not attempt: raise WorkflowError('not_found', 'Attempt not found.', 404)
        if attempt.get('pool') == 'practice': raise WorkflowError('practice_extra_unavailable','Recruitment similarity does not access practice submissions.',403)
        if actor.get('user_type') not in {'recruiter', 'admin'}: raise WorkflowError('forbidden', 'Overlap evidence is reviewer-only.', 403)
        self.runtime.workflow.access(self.runtime.workflow.repo.application(attempt['application_id']), actor)
        self.db.assessment_evidence_access.insert_one(dict(attempt_id=attempt_id, actor_id=str(actor['_id']), action='similarity_read', occurred_at=self.clock()))
        value = self.db.assessment_similarity_reports.find_one({'_id': attempt_id})
        if not value: raise WorkflowError('not_found', 'No similarity report is available.', 404)
        return {k: value[k] for k in ('pairs', 'algorithm', 'warning', 'objective_score_unchanged', 'created_at')}

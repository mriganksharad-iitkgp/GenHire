"""
Background Processing Service for CV Scoring
Uses Mongo-persisted applications, atomic leases and a bounded thread pool.
"""
import threading
import queue
import time
import logging
from datetime import datetime, timedelta
import os
import uuid
import math
from pymongo import ReturnDocument
from middleware.rate_limiter import env_int
from services.bounded_executor import submit_notification
from typing import Dict, Any, Callable, Optional
from bson import ObjectId
from services.usage_telemetry_service import record_usage_event
from services.email_service import EmailService

logger = logging.getLogger(__name__)


def _notify_candidate_of_status(applications_collection, application_id: str, application_status: str, job: Optional[Dict[str, Any]]):
    """
    Fire-and-forget candidate email when automatic CV scoring shortlists or
    rejects an application — this is the platform's highest-volume status
    change (every applicant goes through it), and previously nothing emailed
    the candidate at all here; only a recruiter manually changing status via
    the dashboard did. Reuses the existing status-notification email/template
    (application_controller.py already uses it for that manual path) rather
    than adding a new one. Runs on a daemon thread so a slow send never blocks
    the single serial CV-scoring worker behind it.
    """
    if application_status not in ("shortlisted", "rejected"):
        return
    try:
        app_doc = applications_collection.find_one(
            {"_id": ObjectId(application_id)},
            {"student_email": 1, "student_name": 1},
        )
        candidate_email = app_doc.get("student_email") if app_doc else None
        if not candidate_email:
            return
        candidate_name = (app_doc or {}).get("student_name") or "Candidate"
        job_title = (job or {}).get("title") or "the position"
        company = (job or {}).get("company") or (job or {}).get("company_name") or "the company"

        email_svc = EmailService()
        submit_notification(
            email_svc.send_application_status_notification,
            candidate_email, candidate_name, job_title, company, application_status,
        )
    except Exception:
        logger.warning("Candidate status-notification email failed to send", exc_info=True)


class BackgroundProcessor:
    """
    Durable CV scoring processor with bounded workers and renewable Mongo leases.
    """
    
    def __init__(self):
        self.task_queue = queue.Queue(maxsize=1)  # compatibility stats; Mongo owns the work
        self.worker_thread = None
        self.threads = []
        self.running = False
        self.processed_count = 0
        self.failed_count = 0
        self.collections = None
        self.scoring_service = None
        self.wakeup = threading.Event()
        self.stop_event = threading.Event()
        self.claim_lock = threading.Lock()
        self.claims = {}
        self.worker_count = env_int('CV_SCORING_WORKERS', 2, maximum=16)
        self.lease_seconds = env_int('CV_SCORING_LEASE_SECONDS', 300, minimum=30)
        self.poll_seconds = env_int('CV_SCORING_POLL_SECONDS', 2, maximum=60)

    def configure(self, collections, scoring_service):
        self.collections = collections
        self.scoring_service = scoring_service

    def start(self):
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.threads = [
            threading.Thread(target=self._worker, daemon=True, name=f'cv-scoring-{i}')
            for i in range(self.worker_count)
        ]
        self.threads.append(threading.Thread(target=self._renew_claims, daemon=True, name='cv-lease-renewal'))
        for thread in self.threads:
            thread.start()
        self.worker_thread = self.threads[0]

    def stop(self):
        self.running = False
        self.stop_event.set()
        self.wakeup.set()
        for thread in self.threads:
            thread.join(timeout=1)

    def enqueue_cv_scoring(self, application_id, cv_data, jd_data, db_collections, cv_scoring_service):
        # Snapshots and pending status are saved in the original application write.
        # No provider call or in-memory queue is required to accept the application.
        self.configure(db_collections, cv_scoring_service)
        self.wakeup.set()

    def _claim_task(self):
        if self.collections is None:
            return None
        now = datetime.utcnow()
        token = uuid.uuid4().hex
        collection = self.collections['applications']
        doc = collection.find_one_and_update(
            {
                'workflow_version_id': {'$in': [None, '']},
                'cv_snapshot': {'$ne': None},
                'cv_score_waived': {'$ne': True},
                '$or': [
                    {'processing_status': 'pending'},
                    {'processing_status': 'scoring_retrying', '$or': [
                        {'scoring_next_retry_at': {'$lte': now}},
                        {'scoring_next_retry_at': None},
                    ]},
                    {'processing_status': 'processing', '$or': [
                        {'scoring_lease_until': {'$lte': now}},
                        {'scoring_lease_until': None},
                    ]},
                ],
            },
            {'$set': {
                'processing_status': 'processing', 'scoring_lease_token': token,
                'scoring_lease_until': now + timedelta(seconds=self.lease_seconds),
                'updated_at': now,
            }},
            sort=[('applied_at', 1)], return_document=ReturnDocument.AFTER,
        )
        if not doc:
            return None
        snapshot = doc.get('cv_snapshot') or {}
        jd = doc.get('jd_snapshot') or {}
        job_id = doc.get('job_id')
        job = jd.get('job')
        if not job:
            job = self.collections['jobs'].find_one({'_id': ObjectId(job_id)}) if ObjectId.is_valid(job_id) else {}
        job = job or {'title': jd.get('job_title'), 'description': jd.get('text', '')}
        return {
            'application_id': str(doc['_id']), 'lease_token': token,
            'retry_count': doc.get('scoring_retry_count', 0),
            'cv_data': {
                'cv_text': snapshot.get('text'), 'cv_details': snapshot.get('details'),
                'parsing_confidence': (snapshot.get('metadata') or {}).get('parsing_confidence', 'high'),
            },
            'jd_data': {
                'jd_text': jd.get('text', ''), 'job': job, 'job_id': job_id,
                'minimum_cv_score': doc.get('minimum_cv_score_required', 50.0),
            },
            'db_collections': self.collections, 'cv_scoring_service': self.scoring_service,
        }

    @staticmethod
    def _task_filter(task):
        query = {'_id': ObjectId(task['application_id']), 'workflow_version_id': {'$in': [None, '']}}
        if task.get('lease_token'):
            query['scoring_lease_token'] = task['lease_token']
            query['processing_status'] = 'processing'
        return query

    def _renew_claims(self):
        while not self.stop_event.wait(self.lease_seconds / 3):
            with self.claim_lock:
                tasks = list(self.claims.values())
            for task in tasks:
                try:
                    task['db_collections']['applications'].update_one(
                        self._task_filter(task),
                        {'$set': {'scoring_lease_until': datetime.utcnow() + timedelta(seconds=self.lease_seconds)}},
                    )
                except Exception:
                    logger.warning('CV scoring lease renewal failed')

    def _worker(self):
        while self.running:
            task = None
            try:
                task = self._claim_task()
                if task is None:
                    self.wakeup.wait(self.poll_seconds)
                    self.wakeup.clear()
                    continue
                with self.claim_lock:
                    self.claims[task['lease_token']] = task
                self._process_cv_scoring(task)
                self.processed_count += 1
            except Exception:
                logger.warning('CV worker could not claim/process work', exc_info=True)
                self.failed_count += 1
                self.stop_event.wait(self.poll_seconds)
            finally:
                if task:
                    with self.claim_lock:
                        self.claims.pop(task['lease_token'], None)

    # Maximum retry attempts for CV scoring
    MAX_SCORING_RETRIES = 3
    # Backoff delays in seconds between retries: 30s, 60s, 120s
    RETRY_DELAYS = [30, 60, 120]

    def _process_cv_scoring(self, task: Dict[str, Any]):
        """
        Process CV scoring task with retry on provider exhaustion.

        Updates application with:
        - cv_score and cv_score_breakdown
        - processing_status = 'completed' | 'scoring_retrying' | 'scoring_failed'
        - is_visible = True (always — user should see their application)
        - status = 'shortlisted' | 'rejected' | 'pending' based on score
        """
        application_id = task['application_id']
        cv_data = task['cv_data']
        jd_data = task['jd_data']
        db_collections = task['db_collections']
        cv_scoring_service = task['cv_scoring_service']
        retry_count = task.get('retry_count', 0)

        applications_collection = db_collections['applications']
        jobs_collection = db_collections['jobs']

        try:
            # Update status to processing
            applications_collection.update_one(
                self._task_filter(task),
                {
                    '$set': {
                        'processing_status': 'processing',
                        'is_visible': True,  # Always visible so user sees their app
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            # Calculate CV score
            cv_score = None
            cv_score_breakdown = None
            scoring_result = {}

            cv_text = cv_data.get('cv_text')
            cv_details = cv_data.get('cv_details')
            jd_text = jd_data.get('jd_text', '')
            job = jd_data.get('job')
            minimum_cv_score = jd_data.get('minimum_cv_score', 50.0)
            parsing_confidence = str(cv_data.get('parsing_confidence') or 'low').lower()
            scoring_failed = False

            if cv_scoring_service:
                try:
                    if cv_details:
                        logger.info("Scoring CV from structured details")
                        scoring_result = cv_scoring_service.calculate_cv_score(cv_details, job)
                    elif cv_text:
                        logger.info(f"Scoring CV from text ({len(cv_text)} chars)")
                        scoring_result = cv_scoring_service.calculate_cv_score_from_text(cv_text, jd_text)
                    else:
                        raise ValueError("No CV data available for scoring")

                    # Check if the result is a real score or a fallback
                    is_fallback = bool(scoring_result.get('is_fallback'))

                    if is_fallback:
                        # All providers exhausted — this is NOT a real score
                        scoring_failed = True
                        cv_score = None
                        cv_score_breakdown = None
                        logger.warning(
                            f"CV scoring returned fallback for application "
                            f"{application_id}: {scoring_result.get('error')}"
                        )
                    else:
                        cv_score = scoring_result.get('total_score')
                        cv_score_breakdown = scoring_result.get('score_breakdown')
                        if (isinstance(cv_score, bool) or not isinstance(cv_score, (int, float))
                                or not math.isfinite(cv_score) or not 0 <= cv_score <= 100):
                            cv_score = None
                            scoring_failed = True
                        else:
                            logger.info(
                                f"CV score calculated: {cv_score} "
                                f"(provider: {scoring_result.get('provider_used', 'unknown')})"
                            )

                except Exception as e:
                    logger.error(f"Error calculating CV score: {e}", exc_info=True)
                    scoring_failed = True
            else:
                scoring_failed = True
                logger.error("CV scoring service not available")

            # ──────────────────────────────────────────────────────────────
            # Handle scoring failure with retry
            # ──────────────────────────────────────────────────────────────
            if scoring_failed:
                if retry_count < self.MAX_SCORING_RETRIES:
                    delay = self.RETRY_DELAYS[min(retry_count, len(self.RETRY_DELAYS) - 1)]
                    next_retry = retry_count + 1
                    logger.warning(
                        f"CV scoring failed for application {application_id} "
                        f"(attempt {next_retry}/{self.MAX_SCORING_RETRIES}). "
                        f"Retrying in {delay}s..."
                    )
                    applications_collection.update_one(
                        self._task_filter(task),
                        {
                            '$set': {
                                'processing_status': 'scoring_retrying',
                                'processing_error': str(scoring_result.get('error', 'Scoring failed')),
                                'scoring_retry_count': next_retry,
                                'scoring_next_retry_at': datetime.utcnow() + timedelta(seconds=delay),
                                'is_visible': True,
                                'updated_at': datetime.utcnow()
                            }
                        }
                    )

                    # Persistent retry time is claimed by the same bounded workers.
                    return
                else:
                    # No invented score or eligibility decision when providers fail.
                    applications_collection.update_one(
                        self._task_filter(task),
                        {'$set': {
                            'cv_score': None, 'cv_score_breakdown': None,
                            'processing_status': 'scoring_failed',
                            'processing_error': 'Scoring unavailable; recruiter review required.',
                            'scoring_retry_count': retry_count,
                            'is_visible': True, 'updated_at': datetime.utcnow(),
                        }},
                    )
                    self.failed_count += 1
                    return

            # ──────────────────────────────────────────────────────────────
            # Scoring succeeded — determine application status
            # ──────────────────────────────────────────────────────────────
            current_app = applications_collection.find_one({'_id': ObjectId(application_id)})
            auto_shortlisted_via_invite = bool(
                current_app and current_app.get('auto_shortlisted_via_invite')
            )

            if current_app and current_app.get('status') not in ('pending', 'applied', None) and not auto_shortlisted_via_invite:
                application_status = current_app['status']
                status_reason = current_app.get('status_reason') or 'Recruiter decision preserved'
            elif auto_shortlisted_via_invite:
                application_status = 'shortlisted'
                status_reason = (
                    f'CV score ({cv_score:.1f}); status preserved from recruiter interview invite'
                )
            elif cv_score >= minimum_cv_score:
                application_status = 'shortlisted'
                status_reason = f'CV score ({cv_score:.1f}) meets minimum requirement ({minimum_cv_score:.1f})'
            elif parsing_confidence != 'high':
                application_status = 'pending'
                status_reason = (
                    f'CV score ({cv_score:.1f}) requires manual review because '
                    f'parsing confidence is {parsing_confidence}'
                )
            else:
                application_status = 'rejected'
                status_reason = f'CV score ({cv_score:.1f}) below minimum requirement ({minimum_cv_score:.1f})'

            usage_data = (scoring_result or {}).get('usage', {}) if isinstance(scoring_result, dict) else {}
            prompt_tokens = usage_data.get('prompt_tokens')
            completion_tokens = usage_data.get('completion_tokens')
            usage_source = usage_data.get('usage_source', 'assumed')
            provider_used = scoring_result.get('provider_used', 'unknown')
            model_used = scoring_result.get('model_used', 'unknown')

            # Do not overwrite a recruiter decision that changes after our read.
            result_filter = self._task_filter(task)
            result_filter['workflow_version_id'] = {'$in': [None, '']}
            result_filter['status'] = (current_app or {}).get('status')
            # Update application with results
            result_update = {
                '$set': {
                    'cv_score': cv_score,
                    'cv_score_breakdown': cv_score_breakdown,
                    'status': application_status,
                    'status_reason': status_reason,
                    'processing_status': 'completed',
                    'processing_error': None,
                    'is_visible': True,
                    'cv_score_calculated_at': datetime.utcnow(),
                    'cv_scoring_usage': {
                        'prompt_tokens': int(prompt_tokens or 0),
                        'completion_tokens': int(completion_tokens or 0),
                        'usage_source': usage_source,
                        'provider_used': provider_used,
                        'model_used': model_used,
                    },
                    'prompt_tokens': int(prompt_tokens or 0),
                    'completion_tokens': int(completion_tokens or 0),
                    'updated_at': datetime.utcnow(),
                    'auto_processed': True
                }
            }
            update_result = applications_collection.update_one(result_filter, result_update)
            decision_changed = False
            if not update_result.modified_count:
                # A concurrent recruiter decision must survive. Publish the already
                # calculated score without replaying a paid provider call.
                score_only = {key: value for key, value in result_update['$set'].items()
                              if key not in ('status', 'status_reason')}
                update_result = applications_collection.update_one(self._task_filter(task), {'$set': score_only})
                decision_changed = bool(update_result.modified_count)


            if update_result.modified_count > 0:
                from services.hiring_progression_service import sync_application_enrollment
                sync_application_enrollment(applications_collection, application_id)
                # Update job statistics
                job_id = jd_data.get('job_id')
                if job_id:
                    job_update = {}
                    # NOTE: 'shortlisted' used to (incorrectly) bump the
                    # selected counter; shortlisted applications belong in the
                    # pending bucket, which recruiter job listings recompute
                    # from application statuses anyway.
                    if application_status == 'rejected' and not decision_changed and (current_app or {}).get('status') != application_status:
                        job_update['rejected'] = 1

                    if job_update:
                        jobs_collection.update_one(
                            {'_id': ObjectId(job_id)},
                            {'$inc': job_update}
                        )

                if not decision_changed and (current_app or {}).get("status") != application_status:
                    _notify_candidate_of_status(
                        applications_collection, application_id, application_status, job,
                    )

                logger.info(
                    f"Application {application_id} scored successfully: "
                    f"{cv_score} -> {application_status} "
                    f"(provider: {provider_used})"
                )

                record_usage_event(
                    db_collections,
                    action_type='cv_scoring',
                    actor_type='recruiter',
                    actor_id=str((jd_data.get('job') or {}).get('created_by') or ''),
                    model=model_used,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    usage_source='actual' if usage_source == 'actual' else 'assumed',
                    occurred_at=datetime.utcnow(),
                    source={
                        'type': 'application',
                        'id': application_id,
                        'label': (jd_data.get('job') or {}).get('title') or 'Application CV Scoring',
                    },
                    metadata={
                        'job_id': jd_data.get('job_id'),
                        'cv_score': cv_score,
                        'provider_used': provider_used,
                    }
                )
            else:
                logger.info("Application scoring lease changed or application was removed; stale result discarded")

        except Exception as e:
            logger.error(f"Failed to process CV scoring for application {application_id}: {e}", exc_info=True)

            # Mark as failed but VISIBLE
            try:
                applications_collection.update_one(
                    self._task_filter(task),
                    {
                        '$set': {
                            'processing_status': 'scoring_failed',
                            'processing_error': str(e),
                            'is_visible': True,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
            except Exception as update_error:
                logger.error(f"Failed to update error status: {update_error}")

        finally:
            self._publish_progress(task)

    def _publish_progress(self, task):
        try:
            from extensions import socketio
            doc = task['db_collections']['applications'].find_one({'_id': ObjectId(task['application_id'])})
            if not doc:
                return
            keys = ('job_id', 'job_title', 'status', 'cv_score', 'interview_score', 'proctoring_score',
                    'processing_status', 'processing_error', 'scoring_retry_count', 'auto_processed')
            payload = {key: doc.get(key) for key in keys}
            payload['_id'] = str(doc['_id'])
            applied_at = doc.get('applied_at')
            payload['applied_at'] = applied_at.isoformat() if isinstance(applied_at, datetime) else applied_at
            job = task['jd_data'].get('job') or {}
            payload['job_details'] = {key: job.get(key) for key in ('company', 'location', 'type', 'department')}
            for room in {str(doc.get('student_id') or ''), str(doc.get('recruiter_id') or '')} - {''}:
                socketio.emit('application_update', {'type': 'updated', 'application': payload}, room=room)
        except Exception:
            # Progress is best effort; polling reads the authoritative stored state.
            logger.debug('Application progress push unavailable')

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        return {
            'running': self.running,
            'queue_size': (self.collections['applications'].count_documents({'processing_status': {'$in': ['pending', 'scoring_retrying']}}) if self.collections else 0),
            'workers': self.worker_count,
            'processed_count': self.processed_count,
            'failed_count': self.failed_count
        }


# Global singleton instance
_background_processor = None


def get_background_processor() -> BackgroundProcessor:
    """Get or create the global background processor instance"""
    global _background_processor
    if _background_processor is None:
        _background_processor = BackgroundProcessor()
    return _background_processor

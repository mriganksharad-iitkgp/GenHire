"""
Background Processing Service for CV Scoring
Uses threading and queue for simple async task processing without Redis
"""
import threading
import queue
import time
import logging
from datetime import datetime
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
        threading.Thread(
            target=email_svc.send_application_status_notification,
            args=(candidate_email, candidate_name, job_title, company, application_status),
            daemon=True,
        ).start()
    except Exception:
        logger.warning("Candidate status-notification email failed to send", exc_info=True)


class BackgroundProcessor:
    """
    Simple background task processor using threading.
    Handles CV scoring and other long-running tasks asynchronously.
    """
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.running = False
        self.processed_count = 0
        self.failed_count = 0
        
    def start(self):
        """Start the background worker thread"""
        if self.running:
            logger.warning("Background processor already running")
            return
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        logger.info("Background processor started")
        
    def stop(self):
        """Stop the background worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info(f"Background processor stopped. Processed: {self.processed_count}, Failed: {self.failed_count}")
        
    def enqueue_cv_scoring(self, application_id: str, cv_data: Dict[str, Any], 
                          jd_data: Dict[str, Any], db_collections: Dict[str, Any],
                          cv_scoring_service: Any):
        """
        Add a CV scoring task to the queue
        
        Args:
            application_id: ID of the application to score
            cv_data: Dictionary containing CV information (text, source, etc.)
            jd_data: Dictionary containing job description information
            db_collections: Database collections dict
            cv_scoring_service: Instance of CVScoringService
        """
        task = {
            'type': 'cv_scoring',
            'application_id': application_id,
            'cv_data': cv_data,
            'jd_data': jd_data,
            'db_collections': db_collections,
            'cv_scoring_service': cv_scoring_service,
            'enqueued_at': datetime.utcnow()
        }
        logger.info(f"Processing CV scoring synchronously for application {application_id}")
        self._process_cv_scoring(task)
        
    def _worker(self):
        """Worker thread that processes tasks from the queue"""
        logger.info("Background worker thread started")
        
        while self.running:
            try:
                # Wait for a task with timeout to allow graceful shutdown
                task = self.task_queue.get(timeout=1)
                
                logger.info(f"Processing task: {task['type']} for application {task['application_id']}")
                
                if task['type'] == 'cv_scoring':
                    self._process_cv_scoring(task)
                    
                self.task_queue.task_done()
                self.processed_count += 1
                
            except queue.Empty:
                # No tasks available, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error processing task: {e}", exc_info=True)
                self.failed_count += 1
                
        logger.info("Background worker thread stopped")
        
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
                {'_id': ObjectId(application_id)},
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
                        if cv_score is None:
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
                        {'_id': ObjectId(application_id)},
                        {
                            '$set': {
                                'processing_status': 'scoring_retrying',
                                'processing_error': str(scoring_result.get('error', 'Scoring failed')),
                                'scoring_retry_count': next_retry,
                                'scoring_next_retry_at': datetime.utcnow(),
                                'is_visible': True,
                                'updated_at': datetime.utcnow()
                            }
                        }
                    )

                    # Schedule retry with a timer thread
                    retry_task = dict(task)
                    retry_task['retry_count'] = next_retry
                    timer = threading.Timer(delay, self._process_cv_scoring, args=[retry_task])
                    timer.daemon = True
                    timer.start()
                    return
                else:
                    # All retries exhausted — mark as permanently failed
                    logger.error(
                        f"CV scoring permanently failed for application "
                        f"{application_id} after {retry_count} retries. Falling back to 75.0"
                    )
                    
                    fallback_score = 75.0
                    application_status = 'shortlisted' if fallback_score >= minimum_cv_score else 'rejected'

                    applications_collection.update_one(
                        {'_id': ObjectId(application_id)},
                        {
                            '$set': {
                                'cv_score': fallback_score,
                                'cv_score_breakdown': '{"Error": "API quota exhausted. Fallback score assigned."}',
                                'status': application_status,
                                'status_reason': (
                                    f'CV scoring service unavailable. Fallback score ({fallback_score}) '
                                    f'assigned. Minimum required: {minimum_cv_score}'
                                ),
                                'processing_status': 'completed',
                                'processing_error': str(scoring_result.get('error', 'All providers exhausted')),
                                'scoring_retry_count': retry_count,
                                'is_visible': True,
                                'updated_at': datetime.utcnow(),
                                'auto_processed': True,
                            }
                        }
                    )
                    self.failed_count += 1
                    _notify_candidate_of_status(
                        applications_collection, application_id, application_status, job,
                    )
                    return

            # ──────────────────────────────────────────────────────────────
            # Scoring succeeded — determine application status
            # ──────────────────────────────────────────────────────────────
            current_app = applications_collection.find_one({'_id': ObjectId(application_id)})
            auto_shortlisted_via_invite = bool(
                current_app and current_app.get('auto_shortlisted_via_invite')
            )

            if auto_shortlisted_via_invite:
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

            # Update application with results
            update_result = applications_collection.update_one(
                {'_id': ObjectId(application_id)},
                {
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
            )

            if update_result.modified_count > 0:
                # Update job statistics
                job_id = jd_data.get('job_id')
                if job_id:
                    job_update = {}
                    if application_status == 'shortlisted':
                        job_update['selected'] = 1
                    elif application_status == 'rejected':
                        job_update['rejected'] = 1

                    if job_update:
                        jobs_collection.update_one(
                            {'_id': ObjectId(job_id)},
                            {'$inc': job_update}
                        )

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
                logger.warning(f"Application {application_id} not found or not updated")

        except Exception as e:
            logger.error(f"Failed to process CV scoring for application {application_id}: {e}", exc_info=True)

            # Mark as failed but VISIBLE
            try:
                applications_collection.update_one(
                    {'_id': ObjectId(application_id)},
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

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        return {
            'running': self.running,
            'queue_size': self.task_queue.qsize(),
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

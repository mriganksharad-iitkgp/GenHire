"""
Background Processing Service for CV Scoring
Uses threading and queue for simple async task processing without Redis
"""
import threading
import queue
import time
import logging
from datetime import datetime
from typing import Dict, Any, Callable
from bson import ObjectId
from services.usage_telemetry_service import record_usage_event

logger = logging.getLogger(__name__)


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
        self.task_queue.put(task)
        logger.info(f"CV scoring task enqueued for application {application_id}")
        
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
        
    def _process_cv_scoring(self, task: Dict[str, Any]):
        """
        Process CV scoring task
        
        Updates application with:
        - cv_score and cv_score_breakdown
        - processing_status = 'completed' or 'failed'
        - is_visible = True (when successful)
        - status = 'shortlisted' or 'rejected' based on score
        """
        application_id = task['application_id']
        cv_data = task['cv_data']
        jd_data = task['jd_data']
        db_collections = task['db_collections']
        cv_scoring_service = task['cv_scoring_service']
        
        applications_collection = db_collections['applications']
        jobs_collection = db_collections['jobs']
        
        try:
            # Update status to processing
            applications_collection.update_one(
                {'_id': ObjectId(application_id)},
                {
                    '$set': {
                        'processing_status': 'processing',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            # Calculate CV score
            cv_score = 75.0  # fallback
            cv_score_breakdown = None
            scoring_result = {}
            
            cv_text = cv_data.get('cv_text')
            cv_details = cv_data.get('cv_details')
            jd_text = jd_data.get('jd_text', '')
            job = jd_data.get('job')
            minimum_cv_score = jd_data.get('minimum_cv_score', 50.0)
            
            if cv_scoring_service:
                try:
                    if cv_text:
                        # Score using CV PDF text
                        logger.info(f"Scoring CV from text ({len(cv_text)} chars)")
                        scoring_result = cv_scoring_service.calculate_cv_score_from_text(cv_text, jd_text)
                    elif cv_details:
                        # Score using manual CV details
                        logger.info("Scoring CV from manual details")
                        scoring_result = cv_scoring_service.calculate_cv_score(cv_details, job)
                    else:
                        raise ValueError("No CV data available for scoring")
                        
                    cv_score = scoring_result.get('total_score', 75.0)
                    cv_score_breakdown = scoring_result.get('score_breakdown')
                    logger.info(f"CV score calculated: {cv_score}")
                    
                except Exception as e:
                    logger.error(f"Error calculating CV score: {e}", exc_info=True)
                    cv_score = 75.0
            
            # Determine application status based on score
            if cv_score >= minimum_cv_score:
                application_status = 'shortlisted'
                status_reason = f'CV score ({cv_score:.1f}) meets minimum requirement ({minimum_cv_score:.1f})'
            else:
                application_status = 'rejected'
                status_reason = f'CV score ({cv_score:.1f}) below minimum requirement ({minimum_cv_score:.1f})'
            
            usage_data = (scoring_result or {}).get('usage', {}) if isinstance(scoring_result, dict) else {}
            prompt_tokens = usage_data.get('prompt_tokens')
            completion_tokens = usage_data.get('completion_tokens')
            usage_source = usage_data.get('usage_source', 'assumed')

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
                        'is_visible': True,  # Now visible to users
                        'cv_score_calculated_at': datetime.utcnow(),
                        'cv_scoring_usage': {
                            'prompt_tokens': int(prompt_tokens or 0),
                            'completion_tokens': int(completion_tokens or 0),
                            'usage_source': usage_source,
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
                
                logger.info(f"Application {application_id} scored successfully: {cv_score} -> {application_status}")

                record_usage_event(
                    db_collections,
                    action_type='cv_scoring',
                    actor_type='recruiter',
                    actor_id=str((jd_data.get('job') or {}).get('created_by') or ''),
                    model='gemini-1.5-flash-latest',
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
                    }
                )
            else:
                logger.warning(f"Application {application_id} not found or not updated")
                
        except Exception as e:
            logger.error(f"Failed to process CV scoring for application {application_id}: {e}", exc_info=True)
            
            # Mark as failed
            try:
                applications_collection.update_one(
                    {'_id': ObjectId(application_id)},
                    {
                        '$set': {
                            'processing_status': 'failed',
                            'processing_error': str(e),
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

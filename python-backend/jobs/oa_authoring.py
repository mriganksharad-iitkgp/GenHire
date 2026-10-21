"""Development-only authoring queue runner; production uses the explicit worker."""
import logging
import os
import threading
from core import config

logger=logging.getLogger(__name__)


class LocalPracticeWorker:
    def __init__(self, db):
        from services.practice_assessment_service import PracticeAssessmentService, ensure_practice_assessment_indexes
        ensure_practice_assessment_indexes(db)
        self.service = PracticeAssessmentService(db)

    def run_once(self):
        generated = self.service.generation_once()
        feedback = self.service.feedback_once()
        self.service.expire_ready()
        return generated or feedback

def enabled():
    return (not config.is_production() and not config.jobs_disabled()
            and os.getenv('GENHIRE_LOCAL_OA_WORKER','true').lower()=='true'
            and os.getenv('GENHIRE_WORKFLOW_ENABLED','').lower()=='true'
            and os.getenv('GENHIRE_ASSESSMENT_GENERATION_ENABLED','').lower()=='true')

class LocalAuthoringWorker:
    def __init__(self,db,workers=None):
        self.db=db;self.workers=workers;self.stopping=threading.Event();self.thread=None
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stopping.clear();self.thread=threading.Thread(target=self.run,name='genhire-local-oa-authoring',daemon=True);self.thread.start()
    def run(self):
        if self.workers is None:
            from services.job_draft_generation_service import JobDraftGenerationService
            from services.assessment_generation_service import AssessmentGenerationService
            self.workers=[LocalPracticeWorker(self.db),JobDraftGenerationService(self.db),AssessmentGenerationService(self.db)]
        while not self.stopping.is_set():
            worked=False
            for worker in self.workers:
                if self.stopping.is_set():break
                try:worked=worker.run_once() or worked
                except Exception as error:
                    # Never log provider response bodies or credentials.
                    logger.warning('Local OA queue iteration failed (%s)',type(error).__name__)
            self.stopping.wait(.1 if worked else 2)
    def stop(self):
        self.stopping.set()
        if self.thread:self.thread.join(timeout=2)

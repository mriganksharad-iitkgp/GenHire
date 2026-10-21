import os
import unittest
from unittest.mock import patch
from jobs.oa_authoring import enabled,LocalAuthoringWorker,LocalPracticeWorker

class LocalAuthoringWorkerTests(unittest.TestCase):
    def test_practice_adapter_processes_generation_feedback_and_expiry(self):
        with patch('services.practice_assessment_service.ensure_practice_assessment_indexes') as indexes, patch('services.practice_assessment_service.PracticeAssessmentService') as factory:
            service=factory.return_value
            service.generation_once.return_value=True
            service.feedback_once.return_value=False
            worker=LocalPracticeWorker('isolated-test-db')
            self.assertTrue(worker.run_once())
            indexes.assert_called_once_with('isolated-test-db')
            service.generation_once.assert_called_once()
            service.feedback_once.assert_called_once()
            service.expire_ready.assert_called_once()
    def test_startup_policy_is_local_only_and_respects_tooling_and_flags(self):
        with patch.dict(os.environ,dict(FLASK_ENV='development',GENHIRE_DISABLE_JOBS='0',GENHIRE_LOCAL_OA_WORKER='true',GENHIRE_WORKFLOW_ENABLED='true',GENHIRE_ASSESSMENT_GENERATION_ENABLED='true')):
            self.assertTrue(enabled())
            for key,value in [('FLASK_ENV','production'),('GENHIRE_DISABLE_JOBS','1'),('GENHIRE_LOCAL_OA_WORKER','false'),('GENHIRE_WORKFLOW_ENABLED','false'),('GENHIRE_ASSESSMENT_GENERATION_ENABLED','false')]:
                with patch.dict(os.environ,{key:value}):self.assertFalse(enabled())
    def test_worker_drains_accepted_jobs_and_stop_prevents_more_calls(self):
        worker=LocalAuthoringWorker(None,workers=[]);calls=[]
        class Task:
            def run_once(inner):calls.append('run');worker.stopping.set();return True
        worker.workers=[Task()];worker.start();worker.thread.join(2)
        self.assertFalse(worker.thread.is_alive());self.assertEqual(calls,['run'])
    def test_iteration_failure_does_not_drop_next_task(self):
        worker=LocalAuthoringWorker(None,workers=[]);calls=[]
        class Bad:
            def run_once(inner):raise RuntimeError('private provider payload must not be logged')
        class Good:
            def run_once(inner):calls.append('drained');worker.stopping.set();return False
        worker.workers=[Bad(),Good()]
        with self.assertLogs('jobs.oa_authoring',level='WARNING') as captured:worker.run()
        self.assertEqual(calls,['drained']);self.assertNotIn('private provider payload',''.join(captured.output))

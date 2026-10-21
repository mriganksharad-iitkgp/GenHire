"""Explicit standalone generation/compensation worker; no import-time work.

Run from python-backend after configuring Mongo transactions and providers.
Default-off generation still permits durable refunds/settlements to drain.
"""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    from config.env_loader import load_environment
    load_environment(require_database=True)
    from config.database import db_config
    from services.assessment_generation_service import AssessmentGenerationService
    db = db_config.get_collections()['jobs'].database
    worker = AssessmentGenerationService(db)
    from services.job_draft_generation_service import JobDraftGenerationService
    job_drafts = JobDraftGenerationService(db)
    from services.assessment_validation_jobs import AssessmentValidationJobs
    validator = AssessmentValidationJobs(db)
    while True:
        worked = job_drafts.run_once()
        worked = worker.run_once() or worked
        worked = validator.run_once() or worked
        if args.once: return
        if not worked: time.sleep(2)


if __name__ == '__main__': main()

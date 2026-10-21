"""Explicit durable deadline/public-run worker; never starts during web import."""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    from config.env_loader import load_environment
    load_environment(require_database=True)
    from config.database import db_config
    from services.assessment_runtime_service import AssessmentRuntimeService, ensure_runtime_indexes
    from services.assessment_public_run_service import AssessmentPublicRunService
    from services.assessment_execution_service import ensure_execution_indexes
    db = db_config.get_collections()['jobs'].database
    ensure_runtime_indexes(db)
    ensure_execution_indexes(db)
    runtime = AssessmentRuntimeService(db)
    runs = AssessmentPublicRunService(runtime)
    while True:
        # Accepted deadlines remain enforceable even when rollout is disabled.
        runtime.expire_due()
        runs.tick()
        if args.once: return
        time.sleep(2)


if __name__ == '__main__': main()

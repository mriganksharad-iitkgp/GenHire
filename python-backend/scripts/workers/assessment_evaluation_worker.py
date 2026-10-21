"""Explicit objective evaluator; no execution on the web host or import-time work."""
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
    from services.assessment_runtime_service import AssessmentRuntimeService
    from services.assessment_evaluation_service import AssessmentEvaluationService, ensure_evaluation_indexes
    db = db_config.get_collections()['jobs'].database
    ensure_evaluation_indexes(db)
    evaluation = AssessmentEvaluationService(AssessmentRuntimeService(db))
    while True:
        evaluation.tick()
        evaluation.execution.tick()
        if args.once: return
        time.sleep(2)


if __name__ == '__main__': main()

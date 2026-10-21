"""Explicit OA raw-media/summary cleanup; never removes scores/history."""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--once', action='store_true'); args = parser.parse_args()
    from config.env_loader import load_environment
    load_environment(require_database=True)
    from config.database import db_config
    from services.assessment_runtime_service import AssessmentRuntimeService
    from services.assessment_integrity_service import AssessmentIntegrityService, ensure_integrity_indexes
    from services.assessment_media_service import AssessmentMediaService
    db = db_config.get_collections()['jobs'].database; ensure_integrity_indexes(db)
    media = AssessmentMediaService(AssessmentIntegrityService(AssessmentRuntimeService(db)))
    while True:
        media.retention_tick()
        if args.once: return
        time.sleep(30)


if __name__ == '__main__': main()

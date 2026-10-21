"""Explicit practice generation/advice worker; no local candidate code execution."""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--once',action='store_true');args=parser.parse_args()
    from config.env_loader import load_environment
    load_environment(require_database=True)
    from config.database import db_config
    from services.practice_assessment_service import PracticeAssessmentService,ensure_practice_assessment_indexes
    db=db_config.get_db();ensure_practice_assessment_indexes(db);service=PracticeAssessmentService(db)
    while True:
        service.generation_once();service.feedback_once();service.expire_ready()
        if args.once:return
        time.sleep(3)


if __name__=='__main__':main()

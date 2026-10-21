"""Explicit bounded company email dispatch; unknown deliveries require reconciliation."""
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
    from services.company_hiring_service import CompanyHiringService, ensure_company_indexes
    db = db_config.get_db(); ensure_company_indexes(db); service = CompanyHiringService(db)
    while True:
        service.deliver_once()
        if args.once: return
        time.sleep(2)


if __name__ == '__main__': main()

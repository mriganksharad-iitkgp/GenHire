"""Explicit scheduling/outbox worker; no import-time or startup work."""
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
    from services.hiring_scheduler import HiringScheduler
    from services.hiring_progression_service import ensure_progression_indexes
    db = db_config.get_collections()['jobs'].database
    ensure_progression_indexes(db)
    scheduler = HiringScheduler(db)
    while True:
        scheduler.tick()
        for _ in range(50):
            if not scheduler.deliver_once(): break
        if args.once: return
        time.sleep(5)


if __name__ == '__main__': main()

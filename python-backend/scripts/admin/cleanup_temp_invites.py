"""Standalone CLI to purge dormant invite-only (burner) accounts.

Usage (from repo root):
    python python-backend/scripts/cleanup_temp_invites.py
    python python-backend/scripts/cleanup_temp_invites.py --max-age-days 60

Wire into Windows Task Scheduler / cron if you'd rather not run the in-process
daemon scheduler started by app.py.
"""

import argparse
import json
import os
import sys

# Allow running as `python scripts/cleanup_temp_invites.py` from the backend
# folder OR from the repo root.
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from config.database import db_config  # noqa: E402
from services.invite_cleanup_scheduler import run_cleanup_once  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge dormant invite-only accounts.")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=30,
        help="Delete invite-only accounts older than this many days (default: 30).",
    )
    args = parser.parse_args()

    db_config.connect()
    collections = db_config.get_collections()
    stats = run_cleanup_once(collections, max_age_days=args.max_age_days)
    print(json.dumps(stats, indent=2, default=str))


if __name__ == "__main__":
    main()

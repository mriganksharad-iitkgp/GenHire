"""
One-time migration: backfill job counters from applications.

This script recalculates and updates, for every job:
  - applicants
  - pending
  - interviewed
  - screening_cleared (formerly "selected"; the legacy field is removed)
  - rejected

Usage:
  python migrate_job_counters.py status
  python migrate_job_counters.py migrate
  python migrate_job_counters.py migrate --dry-run
"""

import argparse
import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.database import db_config


def _compute_counters_for_job(applications_collection, job_id_str):
    apps = list(
        applications_collection.find(
            {
                "job_id": job_id_str,
                "is_visible": {"$ne": False},
            },
            {"status": 1},
        )
    )

    interviewed = 0
    screening_cleared = 0
    rejected = 0
    pending = 0

    for app in apps:
        status = str(app.get("status", "pending")).lower()
        if status == "interviewed":
            interviewed += 1
        elif status in ("screening_cleared", "selected"):  # 'selected' = legacy value
            screening_cleared += 1
        elif status == "rejected":
            rejected += 1
        elif status in ["pending", "reviewed", "shortlisted"]:
            pending += 1

    return {
        "applicants": len(apps),
        "pending": pending,
        "interviewed": interviewed,
        "screening_cleared": screening_cleared,
        "rejected": rejected,
    }


def show_status():
    db = db_config.connect()
    jobs_collection = db["jobs"]
    applications_collection = db["applications"]

    jobs = list(jobs_collection.find({}, {"_id": 1, "title": 1, "applicants": 1, "pending": 1, "interviewed": 1, "screening_cleared": 1, "selected": 1, "rejected": 1}))

    print("=" * 90)
    print("Job Counter Backfill Status")
    print("=" * 90)
    print(f"Total jobs: {len(jobs)}")
    print()

    mismatches = 0
    for job in jobs:
        job_id_str = str(job["_id"])
        computed = _compute_counters_for_job(applications_collection, job_id_str)

        current = {
            "applicants": int(job.get("applicants", 0) or 0),
            "pending": int(job.get("pending", 0) or 0),
            "interviewed": int(job.get("interviewed", 0) or 0),
            "screening_cleared": int(job.get("screening_cleared", job.get("selected", 0)) or 0),
            "rejected": int(job.get("rejected", 0) or 0),
        }

        if current != computed:
            mismatches += 1
            print(f"- {job.get('title', 'Untitled Job')} ({job_id_str})")
            print(f"  Current : {current}")
            print(f"  Computed: {computed}")

    if mismatches == 0:
        print("✓ All job counters are already in sync.")
    else:
        print()
        print(f"⚠ Jobs needing backfill: {mismatches}")

    print("=" * 90)


def migrate(dry_run=False):
    db = db_config.connect()
    jobs_collection = db["jobs"]
    applications_collection = db["applications"]

    jobs = list(jobs_collection.find({}, {"_id": 1, "title": 1, "applicants": 1, "pending": 1, "interviewed": 1, "screening_cleared": 1, "selected": 1, "rejected": 1}))

    print("=" * 90)
    print("Backfill Job Counters")
    print("=" * 90)
    print(f"Total jobs scanned: {len(jobs)}")
    print(f"Dry run: {'YES' if dry_run else 'NO'}")
    print()

    updated = 0
    for job in jobs:
        job_id = job["_id"]
        job_id_str = str(job_id)

        computed = _compute_counters_for_job(applications_collection, job_id_str)
        current = {
            "applicants": int(job.get("applicants", 0) or 0),
            "pending": int(job.get("pending", 0) or 0),
            "interviewed": int(job.get("interviewed", 0) or 0),
            "screening_cleared": int(job.get("screening_cleared", job.get("selected", 0)) or 0),
            "rejected": int(job.get("rejected", 0) or 0),
        }

        if current == computed and "selected" not in job:
            continue

        updated += 1
        print(f"Updating: {job.get('title', 'Untitled Job')} ({job_id_str})")
        print(f"  From: {current}")
        print(f"  To  : {computed}")

        if not dry_run:
            jobs_collection.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        **computed,
                        "updated_at": datetime.datetime.utcnow(),
                    },
                    # Remove the legacy counter so nothing double-counts.
                    "$unset": {"selected": ""},
                },
            )

    print()
    if updated == 0:
        print("✓ No jobs required updates.")
    else:
        action = "would be updated" if dry_run else "updated"
        print(f"✓ {updated} job(s) {action}.")
    print("=" * 90)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill job counters from applications")
    parser.add_argument("action", choices=["status", "migrate"], help="status: show mismatches, migrate: apply updates")
    parser.add_argument("--dry-run", action="store_true", help="Show updates without writing to DB")
    args = parser.parse_args()

    try:
        if args.action == "status":
            show_status()
        elif args.action == "migrate":
            migrate(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
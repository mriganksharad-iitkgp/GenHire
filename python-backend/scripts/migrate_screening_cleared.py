"""
One-time migration: rename the application status "selected" to
"screening_cleared" and the job counter field "selected" to
"screening_cleared".

GenHire only screens candidates — it never makes hiring decisions — so the
terminal positive status is "screening cleared", not "selected". The backend
keeps accepting the legacy value on read, but all new writes use
"screening_cleared"; this script converts historical documents so the legacy
tolerance can eventually be dropped.

What it does:
  1. applications: {status: "selected"}                -> "screening_cleared"
  2. applications: {highest_status_reached: "selected"} -> "screening_cleared"
  3. jobs: folds the legacy "selected" counter into "screening_cleared"
     and removes the legacy field.

Usage (from python-backend/):
  python scripts/migrate_screening_cleared.py status
  python scripts/migrate_screening_cleared.py migrate --dry-run
  python scripts/migrate_screening_cleared.py migrate
"""

import argparse
import datetime
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from config.database import db_config  # noqa: E402


def show_status():
    db = db_config.connect()
    apps = db["applications"]
    jobs = db["jobs"]

    legacy_status = apps.count_documents({"status": "selected"})
    legacy_highest = apps.count_documents({"highest_status_reached": "selected"})
    migrated_status = apps.count_documents({"status": "screening_cleared"})
    legacy_job_counter = jobs.count_documents({"selected": {"$exists": True}})

    print("=" * 70)
    print("screening_cleared migration status")
    print("=" * 70)
    print(f'applications with legacy status "selected":            {legacy_status}')
    print(f'applications with legacy highest_status "selected":    {legacy_highest}')
    print(f'applications already on "screening_cleared":           {migrated_status}')
    print(f'jobs still carrying the legacy "selected" counter:     {legacy_job_counter}')
    if not legacy_status and not legacy_highest and not legacy_job_counter:
        print("\n✓ Nothing to migrate.")
    print("=" * 70)


def migrate(dry_run=False):
    db = db_config.connect()
    apps = db["applications"]
    jobs = db["jobs"]
    now = datetime.datetime.utcnow()

    print("=" * 70)
    print(f"Migrating to screening_cleared (dry run: {'YES' if dry_run else 'NO'})")
    print("=" * 70)

    # 1. Application status
    n_status = apps.count_documents({"status": "selected"})
    print(f'1. applications status "selected" -> "screening_cleared": {n_status}')
    if not dry_run and n_status:
        apps.update_many(
            {"status": "selected"},
            {"$set": {"status": "screening_cleared", "updated_at": now}},
        )

    # 2. highest_status_reached
    n_highest = apps.count_documents({"highest_status_reached": "selected"})
    print(f'2. applications highest_status_reached: {n_highest}')
    if not dry_run and n_highest:
        apps.update_many(
            {"highest_status_reached": "selected"},
            {"$set": {"highest_status_reached": "screening_cleared"}},
        )

    # 3. Job counter field: fold "selected" into "screening_cleared", then drop it.
    legacy_jobs = list(
        jobs.find({"selected": {"$exists": True}}, {"selected": 1, "screening_cleared": 1, "title": 1})
    )
    print(f'3. jobs with legacy "selected" counter: {len(legacy_jobs)}')
    for job in legacy_jobs:
        legacy = int(job.get("selected", 0) or 0)
        existing = int(job.get("screening_cleared", 0) or 0)
        merged = existing + legacy
        print(f'   - {job.get("title", "Untitled")}: selected={legacy} + screening_cleared={existing} -> {merged}')
        if not dry_run:
            jobs.update_one(
                {"_id": job["_id"]},
                {
                    "$set": {"screening_cleared": merged, "updated_at": now},
                    "$unset": {"selected": ""},
                },
            )

    print()
    print("✓ Done." if not dry_run else "✓ Dry run complete — no writes performed.")
    print("  Tip: run `python migrate_job_counters.py status` afterwards to")
    print("  verify job counters against actual application statuses.")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Rename status "selected" to "screening_cleared"')
    parser.add_argument("action", choices=["status", "migrate"])
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()

    try:
        if args.action == "status":
            show_status()
        else:
            migrate(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)

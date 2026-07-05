"""
One-time backfill: seed `email_signup_registry` with every email that has
ever existed on the platform, so a deleted-and-recreated account can no
longer re-claim the signup bonus.

Signup bonuses are deduped per user _id (credit_wallets.signup_bonus_granted).
Account deletion hard-deletes the user row, so recreating an account with the
same email gets a fresh _id and looks "new" to that check, granting the bonus
again. `email_signup_registry` is a separate, never-deleted collection keyed
by normalized email; grant_signup_bonus_once() now checks it in addition to
the per-wallet flag. This script backfills it from every user that currently
exists (accounts already deleted before this fix can't be recovered, but this
closes the hole for everyone still on the platform).

Usage (from python-backend/):
  python scripts/migrate_email_signup_registry.py status
  python scripts/migrate_email_signup_registry.py migrate --dry-run
  python scripts/migrate_email_signup_registry.py migrate
"""

import argparse
import datetime
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from config.database import db_config  # noqa: E402

REGISTRY_COLLECTION = "email_signup_registry"


def normalize_audience(user_type):
    return "candidate" if str(user_type or "").strip().lower() in {"candidate", "student"} else "recruiter"


def show_status():
    db = db_config.connect()
    users = db["users"]
    registry = db[REGISTRY_COLLECTION]

    total_users = users.count_documents({})
    registered_emails = registry.count_documents({})

    print("=" * 70)
    print("email_signup_registry backfill status")
    print("=" * 70)
    print(f"users currently on the platform:        {total_users}")
    print(f"emails already in the registry:         {registered_emails}")
    print("=" * 70)


def migrate(dry_run=False):
    db = db_config.connect()
    users = db["users"]
    registry = db[REGISTRY_COLLECTION]
    now = datetime.datetime.utcnow()

    print("=" * 70)
    print(f"Backfilling email_signup_registry (dry run: {'YES' if dry_run else 'NO'})")
    print("=" * 70)

    registry.create_index("email_lower", unique=True)

    inserted = 0
    skipped_no_email = 0
    already_present = 0

    for user in users.find({}, {"_id": 1, "user_type": 1, "email": 1, "email_lower": 1, "created_at": 1}):
        email = str(user.get("email_lower") or user.get("email") or "").strip().lower()
        if not email:
            skipped_no_email += 1
            continue

        if registry.find_one({"email_lower": email}):
            already_present += 1
            continue

        inserted += 1
        if not dry_run:
            registry.update_one(
                {"email_lower": email},
                {
                    "$setOnInsert": {
                        "email_lower": email,
                        "audience": normalize_audience(user.get("user_type")),
                        "owner_id": str(user["_id"]),
                        "granted_at": user.get("created_at") or now,
                    }
                },
                upsert=True,
            )

    print(f"Emails newly registered: {inserted}")
    print(f"Already in registry:     {already_present}")
    print(f"Users with no email:     {skipped_no_email}")
    print()
    print("Done." if not dry_run else "Dry run complete — no writes performed.")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill email_signup_registry from existing users")
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

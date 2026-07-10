"""
One-time migration for the invite-anyone burner flow + score-only face
verification (2026-07).

What it does:
  1. users: burner (is_invite_only) accounts missing `access_expires_at`
     get a 7-day grace window from now. Going forward every invite stamps a
     recruiter-chosen window at send time; without this backfill, legacy
     burners would keep working forever (is_invite_access_expired treats a
     missing field as non-expiring only until this migration runs).
  2. applications: identity_verification summaries written before the
     score-only flow lack the `score`/`matched` fields the recruiter UI now
     renders ("Face match NN%"). Where the interview document has them,
     copy the full new-shape summary onto the application so historical
     face-match results show on the candidate card.

Usage (from python-backend/):
  python scripts/migrations/migrate_invite_face_flow.py status
  python scripts/migrations/migrate_invite_face_flow.py migrate --dry-run
  python scripts/migrations/migrate_invite_face_flow.py migrate
"""

import argparse
import datetime
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from bson import ObjectId  # noqa: E402

from config.database import db_config  # noqa: E402

GRACE_DAYS = 7


def _burner_filter():
    return {"is_invite_only": True, "access_expires_at": {"$exists": False}}


def _stale_summary_filter():
    # Application has an identity summary but not the score field the new
    # card/report UI reads.
    return {
        "identity_verification": {"$exists": True, "$ne": None},
        "identity_verification.score": {"$exists": False},
    }


def show_status():
    db = db_config.connect()
    users = db["users"]
    apps = db["applications"]

    burners_total = users.count_documents({"is_invite_only": True})
    burners_missing_expiry = users.count_documents(_burner_filter())
    stale_summaries = apps.count_documents(_stale_summary_filter())

    print("=" * 70)
    print("invite-face-flow migration status")
    print("=" * 70)
    print(f"burner accounts total:                         {burners_total}")
    print(f"burner accounts missing access_expires_at:     {burners_missing_expiry}")
    print(f"applications with pre-score identity summary:  {stale_summaries}")
    if not burners_missing_expiry and not stale_summaries:
        print("\n[OK] Nothing to migrate.")
    print("=" * 70)


def _identity_summary(identity, session_id):
    """Mirror of routes/interview_routes._identity_summary — kept inline so
    this script has no import-time side effects from the routes package."""
    return {
        "status": identity.get("status"),
        "verified": identity.get("verified"),
        "matched": identity.get("matched"),
        "score": identity.get("score"),
        "distance": identity.get("distance"),
        "threshold": identity.get("threshold"),
        "session_id": session_id,
        "checked_at": identity.get("checked_at"),
        "scored_at": identity.get("scored_at"),
    }


def migrate(dry_run=False):
    db = db_config.connect()
    users = db["users"]
    apps = db["applications"]
    interviews = db["interviews"]
    now = datetime.datetime.utcnow()

    # --- 1. Backfill access_expires_at on legacy burners -------------------
    burner_filter = _burner_filter()
    missing = users.count_documents(burner_filter)
    if dry_run:
        print(f"[dry-run] would set access_expires_at = now + {GRACE_DAYS}d on {missing} burner account(s)")
    else:
        result = users.update_many(
            burner_filter,
            {
                "$set": {
                    "access_expires_at": now + datetime.timedelta(days=GRACE_DAYS),
                    "updated_at": now,
                }
            },
        )
        print(f"[1/2] backfilled access_expires_at on {result.modified_count} burner account(s)")

    # --- 2. Copy score-bearing identity summaries onto applications --------
    updated = 0
    skipped_no_interview_score = 0
    for app in apps.find(_stale_summary_filter(), {"_id": 1}):
        app_id_str = str(app["_id"])
        interview = interviews.find_one(
            {
                "application_id": app_id_str,
                "identity_verification.score": {"$exists": True, "$ne": None},
            },
            sort=[("updated_at", -1)],
        )
        if not interview:
            # Nothing better recorded on any interview — leave the legacy
            # summary as-is (the UI still maps legacy statuses).
            skipped_no_interview_score += 1
            continue

        identity = interview.get("identity_verification") or {}
        summary = _identity_summary(identity, interview.get("session_id"))
        if dry_run:
            updated += 1
            continue
        apps.update_one(
            {"_id": ObjectId(app_id_str)},
            {"$set": {"identity_verification": summary, "updated_at": now}},
        )
        updated += 1

    prefix = "[dry-run] would update" if dry_run else "[2/2] updated"
    print(f"{prefix} {updated} application identity summar(ies) with scores")
    print(f"      ({skipped_no_interview_score} left untouched — no scored interview found)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "migrate"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.command == "status":
        show_status()
    else:
        migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

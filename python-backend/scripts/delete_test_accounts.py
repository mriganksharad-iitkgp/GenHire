"""One-shot purge of specific test accounts (and their applications + invite_tokens).

Usage:
    python python-backend/scripts/delete_test_accounts.py
    python python-backend/scripts/delete_test_accounts.py --commit

Emails are hard-coded; this is intentionally a non-reusable utility for the
2026-04-29 invite-flow test reset.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from config.database import db_config  # noqa: E402

EMAILS = [
    "aptidude.in@gmail.com",
    "roshanyadav35867@gmail.com",
    "roshanyadav2100467@gmail.com",
    "roshan@aptidude.in",
    "bendbrain1@gmail.com",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually delete. Default is dry-run.",
    )
    args = parser.parse_args()

    db_config.connect()
    collections = db_config.get_collections()
    users = collections["users"]
    applications = collections["applications"]
    invite_tokens = collections["invite_tokens"]

    normalized = [e.strip().lower() for e in EMAILS]
    query = {
        "$or": [
            {"email_lower": {"$in": normalized}},
            {"email": {"$in": normalized}},
        ]
    }

    matched = list(users.find(query, {"_id": 1, "email": 1, "user_type": 1, "is_invite_only": 1}))
    print(f"Matched {len(matched)} users:")
    for u in matched:
        print(
            f"  {u['_id']}  email={u.get('email')!r}  type={u.get('user_type')}"
            f"  invite_only={bool(u.get('is_invite_only'))}"
        )

    if not matched:
        print("Nothing to delete.")
        return

    user_ids = [u["_id"] for u in matched]
    user_id_strs = [str(uid) for uid in user_ids]

    apps_count = applications.count_documents({"student_id": {"$in": user_id_strs}})
    tokens_count = invite_tokens.count_documents({"user_id": {"$in": user_ids}})
    print(f"Linked: {apps_count} applications, {tokens_count} invite_tokens")

    if not args.commit:
        print("\nDRY RUN -- pass --commit to actually delete.")
        return

    apps_result = applications.delete_many({"student_id": {"$in": user_id_strs}})
    tokens_result = invite_tokens.delete_many({"user_id": {"$in": user_ids}})
    users_result = users.delete_many({"_id": {"$in": user_ids}})

    print(
        f"\nDeleted: users={users_result.deleted_count}, "
        f"applications={apps_result.deleted_count}, "
        f"invite_tokens={tokens_result.deleted_count}"
    )


if __name__ == "__main__":
    main()

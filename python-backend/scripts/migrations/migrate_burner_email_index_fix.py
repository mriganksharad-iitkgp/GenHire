"""
One-time correctness fix for a bug found in the invite-anyone burner flow
(2026-07-12): burner (is_invite_only) accounts were minted with `email_lower`
populated, but `users` has a UNIQUE sparse index on `email_lower` intended to
cover real accounts only (burners are meant to be excluded by leaving the
field absent — see config/database.py). The practical effect:

  1. Inviting the SAME email to a SECOND different job silently failed with
     a duplicate-key error (reported as a "skipped: duplicate_key" row) — a
     real burner already occupied that email_lower slot.
  2. Inviting an email that already belongs to a real candidate/recruiter/
     admin ALSO silently failed the same way — directly breaking the
     "invite anyone, even existing accounts" feature.
  3. bootstrap_signup_bonus_for_all_users() (runs at every boot) iterated
     burner accounts too and could insert their email into
     `email_signup_registry`, which would then falsely block that email's
     REAL future signup bonus ("this email already claimed a bonus").

Code fixes landed alongside this script:
  - services/invite_service.py no longer sets email_lower on new burners.
  - payment_module/services/wallet_service.py excludes is_invite_only users
    from the signup-bonus bootstrap.

What this script does for EXISTING data:
  1. users: $unset email_lower on every is_invite_only:true doc (frees the
     unique index slot immediately, no restart required).
  2. credit_wallets + credit_transactions: for burner accounts that already
     received a signup bonus from the pre-fix bootstrap bug, reverse it —
     burners never pay for their own interviews (the recruiter's wallet is
     debited instead), so this bonus was never earned and reversing it has
     no effect on any recruiter, candidate, or feature.
  3. email_signup_registry: delete any entry whose owner_id is a burner
     account, so a real future signup with that email is never falsely
     blocked.

Usage (from python-backend/):
  python scripts/migrations/migrate_burner_email_index_fix.py status
  python scripts/migrations/migrate_burner_email_index_fix.py migrate --dry-run
  python scripts/migrations/migrate_burner_email_index_fix.py migrate
"""

import argparse
import datetime
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from bson import ObjectId  # noqa: E402

from config.database import db_config  # noqa: E402


def _burner_with_email_lower_filter():
    return {"is_invite_only": True, "email_lower": {"$exists": True}}


def show_status():
    db = db_config.connect()
    users = db["users"]
    wallets = db["credit_wallets"]
    registry = db["email_signup_registry"]

    burners_with_email_lower = users.count_documents(_burner_with_email_lower_filter())
    burner_ids = [str(u["_id"]) for u in users.find({"is_invite_only": True}, {"_id": 1})]
    burner_wallets_with_bonus = wallets.count_documents(
        {"owner_id": {"$in": burner_ids}, "signup_bonus_granted": True}
    ) if burner_ids else 0
    burner_registry_entries = registry.count_documents(
        {"owner_id": {"$in": burner_ids}}
    ) if burner_ids else 0

    print("=" * 70)
    print("burner email-index fix — status")
    print("=" * 70)
    print(f"burner accounts with email_lower set (index-colliding): {burners_with_email_lower}")
    print(f"burner wallets with a granted signup bonus to reverse:  {burner_wallets_with_bonus}")
    print(f"email_signup_registry entries owned by a burner:        {burner_registry_entries}")
    if not burners_with_email_lower and not burner_wallets_with_bonus and not burner_registry_entries:
        print("\n[OK] Nothing to migrate.")
    print("=" * 70)


def migrate(dry_run=False):
    db = db_config.connect()
    users = db["users"]
    wallets = db["credit_wallets"]
    transactions = db["credit_transactions"]
    registry = db["email_signup_registry"]
    now = datetime.datetime.utcnow()

    # --- 1. Free the unique index slot on existing burners -----------------
    burner_filter = _burner_with_email_lower_filter()
    affected = users.count_documents(burner_filter)
    if dry_run:
        print(f"[dry-run] would $unset email_lower on {affected} burner account(s)")
    else:
        result = users.update_many(burner_filter, {"$unset": {"email_lower": ""}, "$set": {"updated_at": now}})
        print(f"[1/3] unset email_lower on {result.modified_count} burner account(s)")

    burner_ids = [str(u["_id"]) for u in users.find({"is_invite_only": True}, {"_id": 1})]

    # --- 2. Reverse any signup bonus a burner wallet was incorrectly granted
    reversed_count = 0
    if burner_ids:
        for wallet in wallets.find(
            {"owner_id": {"$in": burner_ids}, "signup_bonus_granted": True}
        ):
            owner_id = wallet["owner_id"]
            audience = wallet.get("audience", "candidate")
            bonus_amount = int(wallet.get("total_credited", 0))
            # Find the actual signup-bonus transaction to know the exact
            # amount credited (falls back to the wallet's total_credited
            # only if no matching transaction is found).
            bonus_txn = transactions.find_one(
                {"owner_id": owner_id, "audience": audience, "transaction_type": "signup_bonus"}
            )
            amount = int(bonus_txn.get("credits", bonus_amount)) if bonus_txn else bonus_amount
            if amount <= 0:
                continue
            if dry_run:
                print(f"[dry-run] would reverse {amount} signup-bonus credits from burner wallet {owner_id}")
                reversed_count += 1
                continue
            wallets.update_one(
                {"owner_id": owner_id, "audience": audience},
                {
                    "$inc": {"balance": -amount, "total_credited": -amount},
                    "$set": {"signup_bonus_granted": False, "updated_at": now},
                },
            )
            transactions.insert_one(
                {
                    "owner_id": owner_id,
                    "audience": audience,
                    "credits": -amount,
                    "transaction_type": "signup_bonus_correction",
                    "reference_type": "migration",
                    "reference_id": "migrate_burner_email_index_fix",
                    "metadata": {
                        "reason": "burner accounts never earn a signup bonus — reversing bug-granted credits"
                    },
                    "idempotency_key": f"burner-bonus-reversal:{owner_id}",
                    "created_at": now,
                }
            )
            reversed_count += 1
    prefix = "[dry-run] would reverse" if dry_run else "[2/3] reversed"
    print(f"{prefix} signup bonus on {reversed_count} burner wallet(s)")

    # --- 3. Free the email_signup_registry slot for burner-owned entries ---
    if burner_ids:
        registry_filter = {"owner_id": {"$in": burner_ids}}
        registry_count = registry.count_documents(registry_filter)
        if dry_run:
            print(f"[dry-run] would delete {registry_count} email_signup_registry entr(ies) owned by burners")
        else:
            result = registry.delete_many(registry_filter)
            print(f"[3/3] deleted {result.deleted_count} email_signup_registry entr(ies) owned by burners")
    else:
        print("[3/3] no burner accounts found — nothing to clean in email_signup_registry")


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

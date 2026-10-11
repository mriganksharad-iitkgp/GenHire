r"""Explicit legacy signup-bonus backfill, separate from HTTP worker startup.

From python-backend/:
  .\venv\Scripts\python.exe scripts/migrations/backfill_signup_bonuses.py
  .\venv\Scripts\python.exe scripts/migrations/backfill_signup_bonuses.py --apply

The default only counts eligible accounts and performs no wallet writes.
--apply uses the existing per-wallet and email-registry bonus checks. Run only
against the intended database/profile; existing production accounts have already
been backfilled. No new env variable or scheduled job is required.
"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def backfill(database, apply=False):
    users = database["users"]
    if not apply:
        return {"eligible_accounts": users.count_documents({"is_invite_only": {"$ne": True}})}

    from payment_module.services.wallet_service import WalletService

    granted, skipped = WalletService(database).bootstrap_signup_bonus_for_all_users(users)
    return {"granted": granted, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the legacy backfill to the configured database")
    options = parser.parse_args()

    from config.database import db_config
    from pymongo import MongoClient

    # Avoid DatabaseConfig.connect(): its index migration writes are unnecessary
    # for the default read-only inventory.
    with MongoClient(db_config.uri, serverSelectionTimeoutMS=5000) as client:
        result = backfill(client[db_config.database_name], apply=options.apply)
    print(result)
    if not options.apply:
        print("Read-only count; no bonus eligibility or balances changed. Use --apply to run the backfill.")


if __name__ == "__main__":
    main()

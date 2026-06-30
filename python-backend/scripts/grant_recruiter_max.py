"""
One-shot script: grant rajjinikhilji@gmail.com a Recruiter Max recharge (10,000 credits).
Run from the python-backend directory:
    python scripts/grant_recruiter_max.py
"""
import sys
import os
import uuid
from datetime import datetime

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import db_config
from payment_module.services.wallet_service import WalletService

TARGET_EMAIL = "rajjinikhilji@gmail.com"
CREDITS = 10_000
PLAN_SLUG = "recruiter-max"
PLAN_NAME = "Recruiter Max"
AMOUNT_PAISE = 999900  # ₹9,999.00

def main():
    db = db_config.connect()
    users = db["users"]

    recruiter = users.find_one({"email": TARGET_EMAIL, "user_type": "recruiter"})
    if not recruiter:
        recruiter = users.find_one({"email": TARGET_EMAIL})
    if not recruiter:
        print(f"ERROR: No user found with email {TARGET_EMAIL}")
        sys.exit(1)

    owner_id = str(recruiter["_id"])
    print(f"Found recruiter: {recruiter.get('name', 'Unknown')} ({TARGET_EMAIL}), id={owner_id}")

    wallet_service = WalletService(db)

    # Use a stable idempotency key so re-running the script won't double-charge
    idempotency_key = f"manual-recharge:{PLAN_SLUG}:{owner_id}"

    result = wallet_service.credit_wallet(
        owner_id=owner_id,
        audience="recruiter",
        credits=CREDITS,
        transaction_type="recharge",
        reference_type="manual_grant",
        reference_id=idempotency_key,
        metadata={
            "plan_slug": PLAN_SLUG,
            "plan_name": PLAN_NAME,
            "recharge_credits": CREDITS,
            "amount_paise": AMOUNT_PAISE,
            "granted_by": "admin_script",
            "granted_at": datetime.utcnow().isoformat(),
            "razorpay_order_id": f"manual_{uuid.uuid4().hex[:12]}",
            "razorpay_payment_id": f"manual_{uuid.uuid4().hex[:12]}",
        },
        idempotency_key=idempotency_key,
    )

    if result.get("success") or result.get("idempotent_replay"):
        wallet = result.get("wallet") or {}
        balance = wallet.get("balance") or result.get("credits_remaining", "?")
        replay = " (idempotent replay — already granted)" if result.get("idempotent_replay") else ""
        print(f"SUCCESS{replay}: {TARGET_EMAIL} now has {balance} credits (Recruiter Max plan granted).")
    else:
        print(f"FAILED: {result}")
        sys.exit(1)

if __name__ == "__main__":
    main()

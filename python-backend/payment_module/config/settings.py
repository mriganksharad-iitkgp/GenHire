"""
Payment Module Configuration

Design Decisions:
1. Environment-based configuration for security
2. Separate test/live Stripe keys
3. Configurable webhook endpoints for different environments
4. Default plans seeded on first run
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class PaymentConfig:
    """
    Centralized configuration for the payment module.
    All sensitive data loaded from environment variables.
    """

    # Razorpay Configuration
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

    # URLs for Razorpay redirects
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    PAYMENT_SUCCESS_URL = os.getenv(
        "PAYMENT_SUCCESS_URL", f"{FRONTEND_URL}/payment/success"
    )
    PAYMENT_CANCEL_URL = os.getenv(
        "PAYMENT_CANCEL_URL", f"{FRONTEND_URL}/payment/cancel"
    )

    # MongoDB Configuration (inherits from main app)
    MONGODB_URI = os.getenv("MONGODB_URI")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "hrtech")

    # Payment Module Settings
    CURRENCY = os.getenv("PAYMENT_CURRENCY", "INR")

    # Wallet and fixed-deduction settings
    SIGNUP_BONUS_CREDITS = int(os.getenv("SIGNUP_BONUS_CREDITS", "100"))
    CANDIDATE_PRACTICE_CREDITS = int(os.getenv("CANDIDATE_PRACTICE_CREDITS", "30"))
    CANDIDATE_PRACTICE_PROCTORED_CREDITS = int(
        os.getenv("CANDIDATE_PRACTICE_PROCTORED_CREDITS", "50")
    )
    RECRUITER_AI_JD_CREDITS = int(os.getenv("RECRUITER_AI_JD_CREDITS", "10"))
    RECRUITER_REAL_INTERVIEW_CREDITS = int(
        os.getenv("RECRUITER_REAL_INTERVIEW_CREDITS", "30")
    )
    RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS = int(
        os.getenv("RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS", "50")
    )
    # Bulk candidate invites (magic link): 1 credit per candidate invited.
    # Charged upfront for the whole batch; rows whose email fails to send are
    # auto-refunded (the invite/link still exists for manual sharing).
    RECRUITER_INVITE_CREDITS_PER_CANDIDATE = int(
        os.getenv("RECRUITER_INVITE_CREDITS_PER_CANDIDATE", "1")
    )

    # Recharge pack configuration — every plan's price and credit amount is
    # env-editable (PLAN_<NAME>_PRICE_PAISE / PLAN_<NAME>_CREDITS). Prices are
    # in paise (1 INR = 100 paise). plan_service syncs these into MongoDB on
    # every boot, so an env change + restart updates the live plans.

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            return default

    _CANDIDATE_PRO_PRICE = int(os.getenv("PLAN_CANDIDATE_PRO_PRICE_PAISE", "49900"))
    _CANDIDATE_PRO_CREDITS = int(os.getenv("PLAN_CANDIDATE_PRO_CREDITS", "500"))
    _CANDIDATE_MAX_PRICE = int(os.getenv("PLAN_CANDIDATE_MAX_PRICE_PAISE", "99900"))
    _CANDIDATE_MAX_CREDITS = int(os.getenv("PLAN_CANDIDATE_MAX_CREDITS", "1000"))
    _RECRUITER_PRO_PRICE = int(os.getenv("PLAN_RECRUITER_PRO_PRICE_PAISE", "499900"))
    _RECRUITER_PRO_CREDITS = int(os.getenv("PLAN_RECRUITER_PRO_CREDITS", "5000"))
    _RECRUITER_MAX_PRICE = int(os.getenv("PLAN_RECRUITER_MAX_PRICE_PAISE", "999900"))
    _RECRUITER_MAX_CREDITS = int(os.getenv("PLAN_RECRUITER_MAX_CREDITS", "10000"))

    DEFAULT_PLANS: Dict[str, Dict[str, Any]] = {
        "candidate_pro": {
            "name": "Candidate Pro",
            "slug": "candidate-pro",
            "description": f"Recharge pack with {_CANDIDATE_PRO_CREDITS:,} non-expiring candidate credits",
            "price_paise": _CANDIDATE_PRO_PRICE,
            "credits_allocated": _CANDIDATE_PRO_CREDITS,
            "validity_days": 36500,
            "audience": "candidate",
            "features": [
                f"{_CANDIDATE_PRO_CREDITS:,} non-expiring credits",
                "Practice interviews",
                "Wallet recharge support",
            ],
            "is_active": True,
            "display_order": 1,
            "is_popular": True,
        },
        "candidate_max": {
            "name": "Candidate Max",
            "slug": "candidate-max",
            "description": f"Recharge pack with {_CANDIDATE_MAX_CREDITS:,} non-expiring candidate credits",
            "price_paise": _CANDIDATE_MAX_PRICE,
            "credits_allocated": _CANDIDATE_MAX_CREDITS,
            "validity_days": 36500,
            "audience": "candidate",
            "features": [
                f"{_CANDIDATE_MAX_CREDITS:,} non-expiring credits",
                "Practice interviews",
                "Wallet recharge support",
            ],
            "is_active": True,
            "display_order": 2,
        },
        "recruiter_pro": {
            "name": "Recruiter Pro",
            "slug": "recruiter-pro",
            "description": f"Recharge pack with {_RECRUITER_PRO_CREDITS:,} non-expiring recruiter credits",
            "price_paise": _RECRUITER_PRO_PRICE,
            "credits_allocated": _RECRUITER_PRO_CREDITS,
            "validity_days": 36500,
            "audience": "recruiter",
            "features": [
                f"{_RECRUITER_PRO_CREDITS:,} non-expiring credits",
                "AI JD generation",
                "Real interview wallet deductions",
            ],
            "is_active": True,
            "display_order": 3,
            "is_popular": True,
        },
        "recruiter_max": {
            "name": "Recruiter Max",
            "slug": "recruiter-max",
            "description": f"Recharge pack with {_RECRUITER_MAX_CREDITS:,} non-expiring recruiter credits",
            "price_paise": _RECRUITER_MAX_PRICE,
            "credits_allocated": _RECRUITER_MAX_CREDITS,
            "validity_days": 36500,
            "audience": "recruiter",
            "features": [
                f"{_RECRUITER_MAX_CREDITS:,} non-expiring credits",
                "AI JD generation",
                "Real interview wallet deductions",
            ],
            "is_active": True,
            "display_order": 4,
        },
    }

    @classmethod
    def validate(cls) -> bool:
        """Validate that all required configuration is present"""
        required = ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "MONGODB_URI"]

        missing = [key for key in required if not getattr(cls, key)]

        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

        return True

    @classmethod
    def is_test_mode(cls) -> bool:
        """Check if Razorpay is in test mode"""
        return bool(cls.RAZORPAY_KEY_ID and cls.RAZORPAY_KEY_ID.startswith("rzp_test_"))

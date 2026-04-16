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

    # Recharge pack configuration
    # Prices in paise (1 INR = 100 paise)
    DEFAULT_PLANS: Dict[str, Dict[str, Any]] = {
        "candidate_pro": {
            "name": "Candidate Pro",
            "slug": "candidate-pro",
            "description": "Recharge pack with 500 non-expiring candidate credits",
            "price_paise": 49900,
            "credits_allocated": 500,
            "validity_days": 36500,
            "audience": "candidate",
            "features": [
                "500 non-expiring credits",
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
            "description": "Recharge pack with 1,000 non-expiring candidate credits",
            "price_paise": 99900,
            "credits_allocated": 1000,
            "validity_days": 36500,
            "audience": "candidate",
            "features": [
                "1,000 non-expiring credits",
                "Practice interviews",
                "Wallet recharge support",
            ],
            "is_active": True,
            "display_order": 2,
        },
        "recruiter_pro": {
            "name": "Recruiter Pro",
            "slug": "recruiter-pro",
            "description": "Recharge pack with 5,000 non-expiring recruiter credits",
            "price_paise": 499900,  # ₹4,999.00
            "credits_allocated": 5000,
            "validity_days": 36500,
            "audience": "recruiter",
            "features": [
                "5,000 non-expiring credits",
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
            "description": "Recharge pack with 10,000 non-expiring recruiter credits",
            "price_paise": 999900,  # ₹9,999.00
            "credits_allocated": 10000,
            "validity_days": 36500,
            "audience": "recruiter",
            "features": [
                "10,000 non-expiring credits",
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

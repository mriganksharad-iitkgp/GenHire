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

    # Interview settings
    UNLIMITED_INTERVIEWS = -1  # Sentinel value for unlimited plans

    # Default Plans Configuration
    # These are seeded if no plans exist in the database
    # Prices in paise (1 INR = 100 paise)
    # - Free Tier: 2 free interviews + one-time ₹200 account credit
    # - Enterprise: 1 month validity, 100 interviews + ₹10,000 account credit
    DEFAULT_PLANS: Dict[str, Dict[str, Any]] = {
        "free": {
            "name": "Free Tier",
            "slug": "free",
            "description": "Starter free tier with limited interviews and a small account credit",
            "price_paise": 0,  # Free plan
            "interviews_allowed": 2,
            "validity_days": 365,  # Keep free tier valid for 1 year by default
            "features": [
                "2 AI-powered interviews",
                "One-time ₹200 account credit",
                "Basic access to features",
            ],
            "is_active": True,
            "display_order": 1,
        },
        "enterprise": {
            "name": "Enterprise",
            "slug": "enterprise",
            "description": "Enterprise plan with 1 month validity, 100 interviews and account credit",
            "price_paise": 999900,  # ₹9,999.00
            "interviews_allowed": 100,
            "validity_days": 30,  # 1 month validity
            "features": [
                "100 AI-powered interviews",
                "Includes ₹10,000 account credit",
                "Priority support and integrations",
            ],
            "is_active": True,
            "display_order": 2,
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
        return cls.RAZORPAY_KEY_ID and cls.RAZORPAY_KEY_ID.startswith("rzp_test_")

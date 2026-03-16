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
    # - Free Tier: 2 free interviews
    # - Recruiter Pro: ₹4,999/month, 100 interviews
    # - Recruiter Max: ₹9,999/month, 300 interviews
    DEFAULT_PLANS: Dict[str, Dict[str, Any]] = {
        "free": {
            "name": "Free Tier",
            "slug": "free",
            "description": "Starter free tier with limited interviews",
            "price_paise": 0,  # Free plan
            "interviews_allowed": 2,
            "validity_days": 365,  # Keep free tier valid for 1 year by default
            "audience": "recruiter",
            "features": [
                "2 AI-powered interviews",
                "Basic candidate analytics",
                "Smart CV matching",
            ],
            "is_active": True,
            "display_order": 1,
        },
        "professional": {
            "name": "Recruiter Pro",
            "slug": "professional",
            "description": "Professional plan for growing teams with 100 interviews per month",
            "price_paise": 499900,  # ₹4,999.00
            "interviews_allowed": 100,
            "validity_days": 30,  # 1 month validity
            "audience": "recruiter",
            "features": [
                "100 AI-powered interviews/month",
                "Advanced analytics & reporting",
                "CV screening & ranking",
                "Proctoring features",
                "Priority support",
            ],
            "is_active": True,
            "display_order": 2,
            "is_popular": True,
        },
        "recruiter_max": {
            "name": "Recruiter Max",
            "slug": "recruiter-max",
            "description": "Advanced recruiter plan with 300 interviews per month",
            "price_paise": 999900,  # ₹9,999.00
            "interviews_allowed": 300,
            "validity_days": 30,  # 1 month validity
            "audience": "recruiter",
            "features": [
                "300 AI-powered interviews/month",
                "Custom integrations",
                "Advanced analytics and reporting",
                "Custom branding",
                "Priority support",
            ],
            "is_active": True,
            "display_order": 3,
        },
        "candidate_free": {
            "name": "Free Tier",
            "slug": "candidate-free",
            "description": "Free plan with 2 practice interviews per month",
            "price_paise": 0,
            "interviews_allowed": 2,
            "validity_days": 30,
            "audience": "candidate",
            "features": [
                "2 Practice Interviews/month",
                "Smart practice feedback",
                "Basic interview analytics",
            ],
            "is_active": True,
            "display_order": 1,
        },
        "candidate_pro": {
            "name": "Candidate Pro",
            "slug": "candidate-pro",
            "description": "50 practice interviews per month for active preparation",
            "price_paise": 99900,
            "interviews_allowed": 50,
            "validity_days": 30,
            "audience": "candidate",
            "features": [
                "50 Practice Interviews/month",
                "Detailed interview scoring",
                "Priority report generation",
            ],
            "is_active": True,
            "display_order": 2,
            "is_popular": True,
        },
        "candidate_max": {
            "name": "Candidate Max",
            "slug": "candidate-max",
            "description": "100 practice interviews per month for intensive preparation",
            "price_paise": 149900,
            "interviews_allowed": 100,
            "validity_days": 30,
            "audience": "candidate",
            "features": [
                "100 Practice Interviews/month",
                "Advanced analytics dashboard",
                "Priority support",
            ],
            "is_active": True,
            "display_order": 3,
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

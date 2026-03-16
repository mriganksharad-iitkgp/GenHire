"""
Payment Module for Hiring/Recruitment Platform

This module provides a complete payment solution using Stripe for:
- Plan management (Free Tier, Recruiter Pro, Recruiter Max)
- Payment processing with Stripe Checkout
- Subscription management
- Webhook handling with signature verification
- Interview credit tracking

Architecture:
- Models: MongoDB schemas for plans, subscriptions, payments
- Services: Business logic and Stripe integration
- Controllers: Request handling and validation
- Routes: REST API endpoints
"""

from .routes import payment_routes

__all__ = ["payment_routes"]

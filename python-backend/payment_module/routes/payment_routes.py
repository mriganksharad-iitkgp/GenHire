"""
Payment Routes - Flask Blueprint for payment module APIs

Design Decisions:
1. Blueprint for modular registration
2. Auth middleware applied to protected routes
3. Raw body parsing for webhooks
4. Consistent response format
"""

import logging
from functools import wraps
from flask import Blueprint, request, jsonify, g
from bson import ObjectId
import jwt
import os

logger = logging.getLogger(__name__)

# Create Blueprint
payment_bp = Blueprint("payment", __name__, url_prefix="/api/payment")

# Controllers (initialized later)
_plan_controller = None
_payment_controller = None
_subscription_controller = None
_webhook_controller = None


def init_payment_routes(db):
    """
    Initialize payment routes with database connection.

    Must be called before routes can handle requests.

    Args:
        db: MongoDB database instance
    """
    global _plan_controller, _payment_controller, _subscription_controller, _webhook_controller

    from ..controllers.plan_controller import PlanController
    from ..controllers.payment_controller import PaymentController
    from ..controllers.subscription_controller import SubscriptionController
    from ..controllers.webhook_controller import WebhookController

    _plan_controller = PlanController(db)
    _payment_controller = PaymentController(db)
    _subscription_controller = SubscriptionController(db)
    _webhook_controller = WebhookController(db)

    logger.info("Payment routes initialized")


def require_auth(f):
    """
    Decorator to require authentication.

    Extracts user from JWT token and passes to handler.
    Integrates with existing auth middleware pattern.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        # Get token from header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Authorization header required",
                        "error_code": "missing_auth",
                    }
                ),
                401,
            )

        try:
            # Parse Bearer token
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                raise ValueError("Invalid authorization format")

            token = parts[1]

            # Decode JWT
            secret = os.getenv("JWT_SECRET", "your-jwt-secret")
            payload = jwt.decode(token, secret, algorithms=["HS256"])

            # Add user data to request context
            g.user_data = payload

            return f(*args, **kwargs)

        except jwt.ExpiredSignatureError:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Token expired",
                        "error_code": "token_expired",
                    }
                ),
                401,
            )

        except (jwt.InvalidTokenError, ValueError) as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid token",
                        "error_code": "invalid_token",
                    }
                ),
                401,
            )

    return decorated


# =============================================================================
# PLAN ROUTES (Public)
# =============================================================================


@payment_bp.route("/plans", methods=["GET"])
def get_plans():
    """
    GET /api/payment/plans

    Get all active pricing plans.
    Public endpoint - no auth required.

    Response:
    {
        "success": true,
        "data": {
            "plans": [...],
            "count": 3
        }
    }
    """
    response, status_code = _plan_controller.get_all_plans()
    return jsonify(response), status_code


@payment_bp.route("/plans/<plan_id>", methods=["GET"])
def get_plan(plan_id):
    """
    GET /api/payment/plans/<plan_id>

    Get specific plan by ID.
    Public endpoint.
    """
    response, status_code = _plan_controller.get_plan(plan_id)
    return jsonify(response), status_code


@payment_bp.route("/plans/slug/<slug>", methods=["GET"])
def get_plan_by_slug(slug):
    """
    GET /api/payment/plans/slug/<slug>

    Get specific plan by slug (e.g., 'starter').
    Public endpoint.
    """
    response, status_code = _plan_controller.get_plan_by_slug(slug)
    return jsonify(response), status_code


# =============================================================================
# PAYMENT ROUTES (Protected)
# =============================================================================


@payment_bp.route("/payments/initiate", methods=["POST"])
@require_auth
def initiate_payment():
    """
    POST /api/payment/payments/initiate

    Initiate payment for a plan.
    Requires authentication.

    Request:
    {
        "plan_id": "plan_object_id"
    }

    Response:
    {
        "success": true,
        "data": {
            "checkout_url": "https://checkout.stripe.com/...",
            "session_id": "cs_..."
        }
    }
    """
    response, status_code = _payment_controller.initiate_payment(g.user_data)
    return jsonify(response), status_code


@payment_bp.route("/payments/<payment_id>", methods=["GET"])
@require_auth
def get_payment(payment_id):
    """
    GET /api/payment/payments/<payment_id>

    Get payment status.
    Requires authentication.
    """
    response, status_code = _payment_controller.get_payment_status(
        payment_id, g.user_data
    )
    return jsonify(response), status_code


@payment_bp.route("/payments/history", methods=["GET"])
@require_auth
def get_payment_history():
    """
    GET /api/payment/payments/history

    Get payment history for authenticated user.
    Optional: ?limit=20
    """
    response, status_code = _payment_controller.get_payment_history(g.user_data)
    return jsonify(response), status_code


@payment_bp.route("/payments/<payment_id>/refund", methods=["POST"])
@require_auth
def request_refund(payment_id):
    """
    POST /api/payment/payments/<payment_id>/refund

    Request refund for a payment.

    Optional Request:
    {
        "reason": "requested_by_customer",
        "amount_cents": 1000  // Optional, for partial refund
    }
    """
    response, status_code = _payment_controller.request_refund(payment_id, g.user_data)
    return jsonify(response), status_code


# =============================================================================
# SUBSCRIPTION ROUTES (Protected)
# =============================================================================


@payment_bp.route("/subscriptions/me", methods=["GET"])
@require_auth
def get_current_subscription():
    """
    GET /api/payment/subscriptions/me

    Get current active subscription.
    Requires authentication.

    Response:
    {
        "success": true,
        "data": {
            "has_subscription": true,
            "subscription": {
                "id": "...",
                "plan": {...},
                "interviews_remaining": 5,
                "expires_at": "2026-02-05T..."
            }
        }
    }
    """
    response, status_code = _subscription_controller.get_current_subscription(
        g.user_data
    )
    return jsonify(response), status_code


@payment_bp.route("/subscriptions/history", methods=["GET"])
@require_auth
def get_subscription_history():
    """
    GET /api/payment/subscriptions/history

    Get subscription history.
    Optional: ?limit=10
    """
    response, status_code = _subscription_controller.get_subscription_history(
        g.user_data
    )
    return jsonify(response), status_code


@payment_bp.route("/subscriptions/check", methods=["GET"])
@require_auth
def check_subscription():
    """
    GET /api/payment/subscriptions/check

    Quick check if user can conduct interviews.
    Lightweight endpoint for frontend validation.

    Response:
    {
        "success": true,
        "data": {
            "can_interview": true,
            "interviews_remaining": 5
        }
    }
    """
    response, status_code = _subscription_controller.check_subscription_validity(
        g.user_data
    )
    return jsonify(response), status_code


@payment_bp.route("/subscriptions/cancel", methods=["POST"])
@require_auth
def cancel_subscription():
    """
    POST /api/payment/subscriptions/cancel

    Cancel current subscription.

    Optional Request:
    {
        "reason": "user_requested"
    }
    """
    response, status_code = _subscription_controller.cancel_subscription(g.user_data)
    return jsonify(response), status_code


# =============================================================================
# INTERVIEW ROUTES (Protected)
# =============================================================================


@payment_bp.route("/interviews/use", methods=["POST"])
@require_auth
def use_interview():
    """
    POST /api/payment/interviews/use

    Decrement interview count.
    Call this when starting an interview.

    Response:
    {
        "success": true,
        "data": {
            "interviews_remaining": 4,
            "interviews_used": 1,
            "is_unlimited": false
        }
    }

    Error Response (402 Payment Required):
    {
        "success": false,
        "error": "Interview limit reached",
        "error_code": "limit_exceeded"
    }
    """
    response, status_code = _subscription_controller.use_interview(g.user_data)
    return jsonify(response), status_code


# =============================================================================
# WEBHOOK ROUTES (Stripe - No Auth)
# =============================================================================


@payment_bp.route("/webhooks/stripe", methods=["POST"])
def stripe_webhook():
    """
    POST /api/payment/webhooks/stripe

    Handle Stripe webhook events.
    NO AUTH - Stripe verifies via signature.

    Headers Required:
    - Stripe-Signature: webhook signature

    Always returns 200 to acknowledge receipt.
    """
    response, status_code = _webhook_controller.handle_stripe_webhook()
    return jsonify(response), status_code


# =============================================================================
# HEALTH CHECK
# =============================================================================


@payment_bp.route("/health", methods=["GET"])
def health_check():
    """
    GET /api/payment/health

    Payment module health check.
    """
    return jsonify({"success": True, "module": "payment", "status": "healthy"}), 200

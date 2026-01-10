# Payment Module - Hiring Platform

## Overview

A production-ready payment service for a hiring/recruitment platform built with Flask, MongoDB, and Stripe.

## Features

- **Plan Management**: Starter, Growth, Enterprise plans with interview limits
- **Stripe Checkout**: PCI-compliant payment processing
- **Webhook Handling**: Secure signature verification
- **Interview Tracking**: Atomic decrement with race condition prevention
- **Refund Support**: Full and partial refunds

## Architecture

```
payment_module/
├── config/
│   └── settings.py          # Configuration and default plans
├── models/
│   ├── plan.py              # Plan schema with Stripe IDs
│   ├── subscription.py      # Subscription lifecycle management
│   └── payment.py           # Payment transaction records
├── services/
│   ├── stripe_service.py    # Stripe API wrapper
│   ├── plan_service.py      # Plan CRUD operations
│   ├── subscription_service.py  # Subscription management
│   └── payment_service.py   # Payment orchestration
├── controllers/
│   ├── plan_controller.py   # Plan endpoints
│   ├── payment_controller.py    # Payment endpoints
│   ├── subscription_controller.py   # Subscription endpoints
│   └── webhook_controller.py    # Webhook handler
├── routes/
│   └── payment_routes.py    # Flask blueprint
├── utils.py                 # Helper functions
└── README.md
```

## Quick Start

### 1. Install Dependencies

```bash
pip install stripe pymongo flask pyjwt python-dotenv
```

### 2. Configure Environment

```bash
cp payment_module/env.example .env
# Edit .env with your Stripe keys
```

### 3. Register Blueprint

In your main `app.py`:

```python
from payment_module.routes import payment_bp, init_payment_routes
from config.database import db_config

# Initialize database
db = db_config.connect()

# Initialize payment module
init_payment_routes(db)

# Register blueprint
app.register_blueprint(payment_bp)
```

### 4. Set Up Stripe Webhooks

For local development:

```bash
stripe listen --forward-to localhost:5000/api/payment/webhooks/stripe
```

For production, add webhook endpoint in Stripe Dashboard:

- URL: `https://yourdomain.com/api/payment/webhooks/stripe`
- Events: `checkout.session.completed`, `checkout.session.expired`, `payment_intent.payment_failed`, `charge.refunded`

## API Reference

### Plans (Public)

#### Get All Plans

```
GET /api/payment/plans

Response:
{
    "success": true,
    "data": {
        "plans": [
            {
                "id": "...",
                "name": "Starter",
                "slug": "starter",
                "price": 49.00,
                "interviews_allowed": 5,
                "validity_days": 30,
                "features": ["5 AI interviews", "Basic analytics"]
            }
        ],
        "count": 3
    }
}
```

### Payments (Protected)

#### Initiate Payment

```
POST /api/payment/payments/initiate
Authorization: Bearer <token>

Request:
{
    "plan_id": "507f1f77bcf86cd799439011"
}

Response:
{
    "success": true,
    "data": {
        "checkout_url": "https://checkout.stripe.com/c/pay/...",
        "session_id": "cs_test_..."
    }
}
```

### Subscriptions (Protected)

#### Get Current Subscription

```
GET /api/payment/subscriptions/me
Authorization: Bearer <token>

Response:
{
    "success": true,
    "data": {
        "has_subscription": true,
        "subscription": {
            "id": "...",
            "plan": {
                "name": "Starter",
                "slug": "starter"
            },
            "interviews_allowed": 5,
            "interviews_remaining": 3,
            "interviews_used": 2,
            "is_unlimited": false,
            "is_active": true,
            "expires_at": "2026-02-05T00:00:00"
        }
    }
}
```

#### Use Interview

```
POST /api/payment/interviews/use
Authorization: Bearer <token>

Response:
{
    "success": true,
    "data": {
        "interviews_remaining": 4,
        "interviews_used": 1,
        "is_unlimited": false
    }
}

Error (402 Payment Required):
{
    "success": false,
    "error": "Interview limit reached",
    "error_code": "limit_exceeded"
}
```

### Webhooks (Stripe)

```
POST /api/payment/webhooks/stripe
Headers: Stripe-Signature: <signature>

Always returns 200 to acknowledge receipt.
```

## Payment Flow

```
┌─────────────────┐
│  1. Employer    │
│  selects plan   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. Frontend    │
│  POST /payments │
│  /initiate      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. Backend     │
│  creates Stripe │
│  checkout       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. Employer    │
│  redirected to  │
│  Stripe checkout│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. Payment     │
│  completed      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  6. Stripe      │
│  sends webhook  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  7. Backend     │
│  verifies       │
│  signature      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  8. Subscription│
│  activated      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  9. Employer    │
│  can conduct    │
│  interviews     │
└─────────────────┘
```

## Data Models

### Plan

```javascript
{
    "_id": ObjectId,
    "name": "Starter",
    "slug": "starter",
    "description": "...",
    "price_cents": 4900,
    "interviews_allowed": 5,  // -1 for unlimited
    "validity_days": 30,
    "features": ["..."],
    "stripe_product_id": "prod_...",
    "stripe_price_id": "price_...",
    "is_active": true,
    "display_order": 1,
    "created_at": ISODate,
    "updated_at": ISODate
}
```

### Subscription

```javascript
{
    "_id": ObjectId,
    "employer_id": ObjectId,
    "plan_id": ObjectId,
    "plan_snapshot": {...},  // Denormalized plan data
    "status": "active",  // pending, active, expired, cancelled
    "interviews_allowed": 5,
    "interviews_remaining": 3,
    "interviews_used": 2,
    "started_at": ISODate,
    "expires_at": ISODate,
    "payment_id": ObjectId,
    "stripe_session_id": "cs_...",
    "created_at": ISODate,
    "updated_at": ISODate
}
```

### Payment

```javascript
{
    "_id": ObjectId,
    "employer_id": ObjectId,
    "subscription_id": ObjectId,
    "plan_id": ObjectId,
    "amount_cents": 4900,
    "currency": "usd",
    "status": "succeeded",  // pending, processing, succeeded, failed, refunded
    "stripe_session_id": "cs_...",
    "stripe_payment_intent_id": "pi_...",
    "stripe_charge_id": "ch_...",
    "idempotency_key": "pay_...",
    "refund_amount_cents": 0,
    "created_at": ISODate,
    "completed_at": ISODate
}
```

## Security Considerations

1. **Webhook Verification**: Always verify Stripe signatures
2. **Never Trust Frontend**: Payment success must come from webhook
3. **Idempotency**: All operations are idempotent to handle retries
4. **Atomic Operations**: Interview decrement uses MongoDB atomic `$inc`
5. **No Sensitive Data**: API responses exclude internal IDs and full Stripe responses

## Testing

### Test Cards

- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`
- Requires Auth: `4000 0025 0000 3155`

### Stripe CLI

```bash
# Forward webhooks to local server
stripe listen --forward-to localhost:5000/api/payment/webhooks/stripe

# Trigger test events
stripe trigger checkout.session.completed
```

## Error Codes

| Code                    | Description                    | HTTP Status |
| ----------------------- | ------------------------------ | ----------- |
| `invalid_plan`          | Plan not found or inactive     | 400         |
| `no_subscription`       | No active subscription         | 402         |
| `limit_exceeded`        | Interview limit reached        | 402         |
| `subscription_inactive` | Subscription expired/cancelled | 400         |
| `invalid_signature`     | Webhook signature invalid      | 400         |
| `not_refundable`        | Payment cannot be refunded     | 400         |

## Production Checklist

- [ ] Use live Stripe keys
- [ ] Set proper webhook URL in Stripe Dashboard
- [ ] Enable Stripe Radar for fraud protection
- [ ] Set up monitoring for webhook failures
- [ ] Configure proper CORS for production domain
- [ ] Enable HTTPS
- [ ] Set secure JWT secret
- [ ] Configure MongoDB authentication
- [ ] Set up logging and alerting

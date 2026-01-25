# Payment Module - Hiring Platform

## Overview

A production-ready payment service for a hiring/recruitment platform built with Flask, MongoDB, and Razorpay.

## Features

- **Plan Management**: Starter, Growth, Enterprise plans with interview limits
- **Razorpay Checkout**: PCI-compliant payment processing
- **Webhook Handling**: Secure signature verification
- **Interview Tracking**: Atomic decrement with race condition prevention
- **Refund Support**: Full and partial refunds

## Architecture

```
payment_module/
├── config/
│   └── settings.py          # Configuration and default plans
├── models/
│   ├── plan.py              # Plan schema
│   ├── subscription.py      # Subscription lifecycle management
│   └── payment.py           # Payment transaction records
├── services/
│   ├── razorpay_service.py  # Razorpay API wrapper
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
pip install razorpay pymongo flask pyjwt python-dotenv
```

### 2. Configure Environment

```bash
cp payment_module/env.example .env
# Edit .env with your Razorpay keys
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

### 4. Set Up Razorpay Webhooks

In Razorpay Dashboard:

- Go to Settings -> Webhooks
- Add webhook endpoint: `https://yourdomain.com/api/payment/webhooks/razorpay`
- Select events: `payment.captured`, `payment.failed`, `refund.created`, `order.paid`
- Copy the webhook secret to your `.env`

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
        "order_id": "order_...",
        "amount": 10000,
        "currency": "INR",
        "key_id": "rzp_...",
        "payment_id": "...",
        "prefill": {
            "name": "John Doe",
            "email": "john@example.com"
        }
    }
}
```

#### Verify Payment

After frontend checkout, verify the payment:

```
POST /api/payment/payments/verify
Authorization: Bearer <token>

Request:
{
    "razorpay_order_id": "order_...",
    "razorpay_payment_id": "pay_...",
    "razorpay_signature": "..."
}

Response:
{
    "success": true,
    "data": {
        "message": "Payment verified",
        "payment_id": "..."
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

### Webhooks (Razorpay)

```
POST /api/payment/webhooks/razorpay
Headers: X-Razorpay-Signature: <signature>

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
│  creates        │
│  Razorpay order │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. Frontend    │
│  opens Razorpay │
│  checkout modal │
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
│  6. Frontend    │
│  POST /payments │
│  /verify        │
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

## Frontend Integration

### React Example

```javascript
import React from "react";

const PaymentButton = ({ planId }) => {
  const handlePayment = async () => {
    // 1. Initiate payment
    const response = await fetch("/api/payment/payments/initiate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ plan_id: planId }),
    });

    const { data } = await response.json();

    // 2. Open Razorpay checkout
    const options = {
      key: data.key_id,
      amount: data.amount,
      currency: data.currency,
      order_id: data.order_id,
      name: "Your Company",
      description: "Plan Purchase",
      prefill: data.prefill,
      handler: async function (response) {
        // 3. Verify payment
        await fetch("/api/payment/payments/verify", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
          }),
        });

        // 4. Redirect to success page
        window.location.href = "/payment/success";
      },
    };

    const rzp = new Razorpay(options);
    rzp.open();
  };

  return <button onClick={handlePayment}>Subscribe</button>;
};
```

## Data Models

### Plan

```javascript
{
    "_id": ObjectId,
    "name": "Starter",
    "slug": "starter",
    "description": "...",
    "price_paise": 99900,  // Amount in paise (₹999.00)
    "interviews_allowed": 5,  // -1 for unlimited
    "validity_days": 30,
    "features": ["..."],
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
    "razorpay_order_id": "order_...",
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
    "amount_paise": 4900,
    "currency": "inr",
    "status": "succeeded",  // pending, processing, succeeded, failed, refunded
    "razorpay_order_id": "order_...",
    "razorpay_payment_id": "pay_...",
    "razorpay_signature": "...",
    "idempotency_key": "pay_...",
    "refund_amount_paise": 0,
    "created_at": ISODate,
    "completed_at": ISODate
}
```

## Security Considerations

1. **Webhook Verification**: Always verify Razorpay signatures
2. **Payment Verification**: Use `/payments/verify` endpoint after frontend checkout
3. **Never Trust Frontend**: Payment success must come from signature verification
4. **Idempotency**: All operations are idempotent to handle retries
5. **Atomic Operations**: Interview decrement uses MongoDB atomic `$inc`
6. **No Sensitive Data**: API responses exclude internal IDs and full Razorpay responses

## Testing

### Test Mode

Use test mode keys from Razorpay Dashboard (keys starting with `rzp_test_`)

### Test Cards

- Success: `4111 1111 1111 1111` (any future expiry, any CVV)
- UPI: `success@razorpay` for test UPI payments

### Test Webhooks

Use Razorpay's test mode to trigger webhook events from the dashboard.

## Error Codes

| Code                    | Description                       | HTTP Status |
| ----------------------- | --------------------------------- | ----------- |
| `invalid_plan`          | Plan not found or inactive        | 400         |
| `no_subscription`       | No active subscription            | 402         |
| `limit_exceeded`        | Interview limit reached           | 402         |
| `subscription_inactive` | Subscription expired/cancelled    | 400         |
| `invalid_signature`     | Webhook/payment signature invalid | 400         |
| `not_refundable`        | Payment cannot be refunded        | 400         |
| `verification_failed`   | Payment verification failed       | 400         |

## Production Checklist

- [ ] Use live Razorpay keys
- [ ] Set proper webhook URL in Razorpay Dashboard
- [ ] Enable Razorpay fraud protection
- [ ] Set up monitoring for webhook failures
- [ ] Configure proper CORS for production domain
- [ ] Enable HTTPS
- [ ] Set secure JWT secret
- [ ] Configure MongoDB authentication
- [ ] Set up logging and alerting

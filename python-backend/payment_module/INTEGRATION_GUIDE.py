"""
Payment Module Integration Guide

This file shows how to integrate the payment module into your main Flask app.
Copy the relevant sections to your app.py.
"""

# =============================================================================
# STEP 1: Add Import (after other route imports)
# =============================================================================

# Add this to your imports section:
"""
# Import payment module
try:
    from payment_module.routes import payment_bp, init_payment_routes
    PAYMENT_MODULE_AVAILABLE = True
    print("✓ Payment module loaded successfully")
except ImportError as e:
    print(f"⚠ Payment module not available: {e}")
    PAYMENT_MODULE_AVAILABLE = False
"""

# =============================================================================
# STEP 2: Initialize and Register Blueprint (after database connection)
# =============================================================================

# Add this after: db = db_config.connect()
"""
# Initialize payment module
if PAYMENT_MODULE_AVAILABLE:
    try:
        init_payment_routes(db)
        app.register_blueprint(payment_bp)
        print("✓ Payment routes registered at /api/payment")
    except Exception as e:
        print(f"⚠ Failed to initialize payment module: {e}")
"""

# =============================================================================
# STEP 3: Update .env file
# =============================================================================

# Add these to your .env file:
"""
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_secret_here

# Payment URLs
FRONTEND_URL=http://localhost:3000
PAYMENT_SUCCESS_URL=http://localhost:3000/payment/success
PAYMENT_CANCEL_URL=http://localhost:3000/payment/cancel
"""

# =============================================================================
# STEP 4: Install Required Packages
# =============================================================================

# Add to requirements.txt:
"""
stripe>=5.0.0
PyJWT>=2.0.0
"""

# Install:
# pip install stripe PyJWT

# =============================================================================
# STEP 5: Test the Integration
# =============================================================================

# After starting your server, test with:
"""
# Get all plans
curl http://localhost:5000/api/payment/plans

# Health check
curl http://localhost:5000/api/payment/health
"""

# =============================================================================
# EXAMPLE: Updated app.py blueprint registration section
# =============================================================================

EXAMPLE_CODE = """
# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(job_bp)
app.register_blueprint(application_bp)
app.register_blueprint(file_bp)
app.register_blueprint(practice_bp)

# Register CV routes
cv_bp = create_cv_routes(collections)
app.register_blueprint(cv_bp, url_prefix='/api/cv')

# Register payment module
if PAYMENT_MODULE_AVAILABLE:
    try:
        init_payment_routes(db)
        app.register_blueprint(payment_bp)
        print("✓ Payment routes registered")
    except Exception as e:
        print(f"⚠ Payment module error: {e}")
"""

# =============================================================================
# FRONTEND INTEGRATION
# =============================================================================

FRONTEND_EXAMPLE = """
// Get plans
const response = await fetch('/api/payment/plans');
const { data } = await response.json();
const plans = data.plans;

// Initiate payment
const paymentResponse = await fetch('/api/payment/payments/initiate', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ plan_id: selectedPlanId })
});

const { data: paymentData } = await paymentResponse.json();
// Redirect to Stripe checkout
window.location.href = paymentData.checkout_url;

// After payment success, check subscription
const subResponse = await fetch('/api/payment/subscriptions/me', {
    headers: { 'Authorization': `Bearer ${token}` }
});
const { data: subData } = await subResponse.json();
console.log('Interviews remaining:', subData.subscription.interviews_remaining);

// Before starting interview, check validity
const checkResponse = await fetch('/api/payment/subscriptions/check', {
    headers: { 'Authorization': `Bearer ${token}` }
});
const { data: checkData } = await checkResponse.json();
if (!checkData.can_interview) {
    alert('Please purchase a plan to conduct interviews');
    return;
}

// When starting interview, decrement count
const useResponse = await fetch('/api/payment/interviews/use', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
});
const { data: useData } = await useResponse.json();
if (!useData.success) {
    alert(useData.error);
    return;
}
"""

if __name__ == "__main__":
    print("This is an integration guide. See the code comments for instructions.")

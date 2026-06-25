# Testing Guide for Authentication Features

This guide will help you test all the new authentication features.

## Prerequisites

Before testing, ensure:

- ✅ Backend is running on `http://localhost:8080` (or port 5000)
- ✅ Environment variables are configured in `.env`
- ✅ MongoDB is running
- ✅ Mailgun credentials are set (or `REQUIRE_EMAIL_VERIFICATION=false`)

## Test 1: Email Verification Flow

### Using Postman or cURL:

#### 1.1 Register a new user

```bash
curl -X POST http://localhost:8080/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "password": "password123",
    "confirmPassword": "password123",
    "userType": "candidate"
  }'
```

**Expected Response:**

```json
{
  "message": "User registered successfully. Please check your email to verify your account.",
  "token": "jwt_token_here",
  "email_verification_required": true,
  "user": {
    "id": "user_id",
    "name": "Test User",
    "email": "test@example.com",
    "user_type": "candidate",
    "email_verified": false
  }
}
```

#### 1.2 Check your email

If using Mailgun sandbox:

- Go to Mailgun Dashboard → Logs
- Find the verification email
- Copy the verification token from the URL

#### 1.3 Verify email

```bash
curl -X POST http://localhost:8080/api/verify-email \
  -H "Content-Type: application/json" \
  -d '{
    "token": "PASTE_TOKEN_HERE"
  }'
```

**Expected Response:**

```json
{
  "message": "Email verified successfully",
  "user": {
    "id": "user_id",
    "name": "Test User",
    "email": "test@example.com",
    "user_type": "candidate",
    "email_verified": true
  }
}
```

#### 1.4 Try to login

```bash
curl -X POST http://localhost:8080/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "userType": "candidate"
  }'
```

**Expected Response:**

```json
{
  "message": "Logged in successfully",
  "token": "jwt_token_here",
  "user": {
    "id": "user_id",
    "name": "Test User",
    "email": "test@example.com",
    "user_type": "candidate",
    "email_verified": true
  }
}
```

## Test 2: Resend Verification Email

```bash
curl -X POST http://localhost:8080/api/resend-verification \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com"
  }'
```

**Expected Response:**

```json
{
  "message": "Verification email sent successfully"
}
```

## Test 3: Password Reset Flow

#### 3.1 Request password reset

```bash
curl -X POST http://localhost:8080/api/forgot-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com"
  }'
```

**Expected Response:**

```json
{
  "message": "If your email is registered, you will receive a password reset link"
}
```

#### 3.2 Check email for reset link

- Check your email or Mailgun logs
- Copy the reset token from the URL

#### 3.3 Reset password

```bash
curl -X POST http://localhost:8080/api/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "PASTE_RESET_TOKEN_HERE",
    "password": "newpassword123",
    "confirmPassword": "newpassword123"
  }'
```

**Expected Response:**

```json
{
  "message": "Password reset successfully"
}
```

#### 3.4 Login with new password

```bash
curl -X POST http://localhost:8080/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "newpassword123",
    "userType": "candidate"
  }'
```

**Expected Response:** Login successful with new password.

## Test 4: Google OAuth

### Testing with Frontend:

1. Set up Google OAuth button in your React app (see SETUP_GUIDE.md)
2. Click "Sign in with Google"
3. Authorize with Google account
4. Check network tab - should see POST to `/api/google-oauth`
5. User should be logged in automatically

### Testing with Postman:

This is more complex as you need a valid Google ID token. Best tested through frontend.

**Alternative: Test with invalid token**

```bash
curl -X POST http://localhost:8080/api/google-oauth \
  -H "Content-Type: application/json" \
  -d '{
    "token": "invalid_token",
    "userType": "candidate"
  }'
```

**Expected Response:**

```json
{
  "error": "Invalid Google token"
}
```

## Test 5: Get Current User Info

```bash
curl -X GET http://localhost:8080/api/me \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE"
```

**Expected Response:**

```json
{
  "id": "user_id",
  "name": "Test User",
  "email": "test@example.com",
  "user_type": "candidate",
  "email_verified": true,
  "auth_provider": "local"
}
```

## Test 6: Edge Cases

### 6.1 Try to login before email verification

With `REQUIRE_EMAIL_VERIFICATION=true`:

```bash
curl -X POST http://localhost:8080/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "unverified@example.com",
    "password": "password123",
    "userType": "candidate"
  }'
```

**Expected Response (403):**

```json
{
  "error": "Please verify your email before logging in",
  "email_verification_required": true
}
```

### 6.2 Try to use expired verification token

Wait 24 hours or manually expire token in database.

```bash
curl -X POST http://localhost:8080/api/verify-email \
  -H "Content-Type: application/json" \
  -d '{
    "token": "expired_token"
  }'
```

**Expected Response (400):**

```json
{
  "error": "Verification token has expired"
}
```

### 6.3 Try to reset password for OAuth user

First create a user via Google OAuth, then:

```bash
curl -X POST http://localhost:8080/api/forgot-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "google-user@example.com"
  }'
```

**Expected Response (400):**

```json
{
  "error": "Cannot reset password for Google accounts"
}
```

### 6.4 Try to verify already verified email

```bash
curl -X POST http://localhost:8080/api/resend-verification \
  -H "Content-Type: application/json" \
  -d '{
    "email": "already-verified@example.com"
  }'
```

**Expected Response (400):**

```json
{
  "error": "Email is already verified"
}
```

## Test 7: Testing Without Email (Development Mode)

Set in `.env`:

```env
REQUIRE_EMAIL_VERIFICATION=false
```

Restart backend, then:

1. Register new user
2. Should be able to login immediately without verification
3. `email_verified` will be `true` in response

## Test 8: Migration Script

Test with existing database:

```bash
cd python-backend
python migrate_auth_fields.py
```

**Expected Output:**

```
============================================================
User Migration Script - Authentication Features
============================================================

⚠️  This will update existing user records. Continue? (yes/no): yes
🔄 Starting user migration...
Database: hrtech
✅ Updated user: user1@example.com
✅ Updated user: user2@example.com

✨ Migration completed successfully!
📊 Total users updated: 2

📈 Database Summary:
   Total users: 5
   Verified users: 5
   Local auth users: 5
   Google auth users: 0
```

## Test 9: Email Content

Check that emails look good:

1. Register new user
2. Check Mailgun logs or your email inbox
3. Verify email contains:
   - ✅ Professional formatting
   - ✅ Clear "Verify Email" button
   - ✅ Working link
   - ✅ Expiry information
   - GenHire branding

Do the same for password reset email.

## Test 10: Database Verification

Check MongoDB directly:

```bash
# Connect to MongoDB
mongo

# Use your database
use hrtech

# Check a user document
db.users.findOne({email: "test@example.com"})
```

**Expected fields:**

```javascript
{
  _id: ObjectId("..."),
  name: "Test User",
  email: "test@example.com",
  password: "$2b$...",  // Hashed
  user_type: "candidate",
  email_verified: true,
  auth_provider: "local",
  created_at: ISODate("..."),
  updated_at: ISODate("...")
  // verification_token and expires should be removed after verification
}
```

## Test 11: Billing Smoke Test (Candidate + Recruiter)

Use the billing smoke script to quickly validate role isolation and billing endpoints after subscription changes.

### 11.1 Set environment variables

```bash
export SMOKE_BASE_URL="http://localhost:5000"
export SMOKE_RECRUITER_TOKEN="<recruiter_jwt_token>"
export SMOKE_CANDIDATE_TOKEN="<candidate_jwt_token>"
```

On Windows PowerShell:

```powershell
$env:SMOKE_BASE_URL="http://localhost:5000"
$env:SMOKE_RECRUITER_TOKEN="<recruiter_jwt_token>"
$env:SMOKE_CANDIDATE_TOKEN="<candidate_jwt_token>"
```

### 11.2 Run the script

```bash
cd python-backend
python scripts/billing_smoke_test.py
```

### 11.3 What it verifies

- Recruiter sees only recruiter plans from `/api/payment/plans`
- Candidate sees candidate plans from `/api/payment/plans`
- Both roles can access `/api/payment/subscriptions/me` and `/api/payment/payments/history`
- Recruiter-only endpoint guard works: candidate blocked on `/api/recruiter/cost-statistics`
- Candidate-only endpoint guard works: recruiter blocked on `/api/candidate/cost-statistics`

### 11.4 Expected result

- Script prints `PASS` for each check
- Final line prints: `SUMMARY: PASS`

If it fails, inspect the failing endpoint response and verify the token belongs to the intended user role.

## Test Checklist

Use this checklist to verify everything works:

- [ ] User registration sends verification email
- [ ] Verification link works correctly
- [ ] User can login after verification
- [ ] User cannot login before verification (if enabled)
- [ ] Resend verification email works
- [ ] Password reset request sends email
- [ ] Password reset link works correctly
- [ ] User can login with new password
- [ ] Password change confirmation email sent
- [ ] Google OAuth login works
- [ ] Google OAuth creates new user if doesn't exist
- [ ] Google OAuth links to existing email
- [ ] Expired tokens are rejected
- [ ] Invalid tokens are rejected
- [ ] Migration script works for existing users
- [ ] Email templates look professional
- [ ] All error messages are appropriate
- [ ] Development mode (no verification) works

## Common Issues and Solutions

### Issue: Emails not received

**Solutions:**

- Check Mailgun dashboard logs
- Verify MAILGUN_API_KEY and MAILGUN_DOMAIN
- For sandbox: add recipient to authorized list
- Check spam folder

### Issue: "Invalid Google token"

**Solutions:**

- Verify GOOGLE_CLIENT_ID matches in backend and frontend
- Check Google Console authorized origins include your frontend URL
- Ensure token is fresh (Google tokens expire quickly)

### Issue: "Please verify your email before logging in"

**Solutions:**

- Check email for verification link
- Or set REQUIRE_EMAIL_VERIFICATION=false
- Or run migration script for existing users

### Issue: Token expired

**Solutions:**

- Request new verification/reset email
- Tokens expire after 24h (verification) or 1h (reset)

## Performance Testing

Test with multiple users:

```bash
# Register 10 users
for i in {1..10}; do
  curl -X POST http://localhost:8080/api/register \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"Test User $i\",
      \"email\": \"test$i@example.com\",
      \"password\": \"password123\",
      \"confirmPassword\": \"password123\",
      \"userType\": \"candidate\"
    }"
done
```

Check:

- All emails sent successfully
- No timeouts
- Database handles concurrent writes

## Security Testing

Test security features:

1. **Token Reuse**: Try to verify email twice with same token → Should fail
2. **Token Guessing**: Try random tokens → Should fail
3. **Email Enumeration**: Reset password for non-existent email → Generic message
4. **Password Strength**: Try weak passwords → Should be validated
5. **Rate Limiting**: Make many reset requests → Consider adding rate limiting

## Success Criteria

✅ All tests pass  
✅ No errors in backend logs  
✅ Emails received and formatted correctly  
✅ Existing users still work  
✅ New features work as expected  
✅ Security measures in place

## Need Help?

If tests fail:

1. Check backend logs for errors
2. Verify environment variables
3. Check Mailgun dashboard logs
4. Review AUTH_FEATURES.md documentation
5. Check IMPLEMENTATION_SUMMARY.md

Happy testing! 🚀

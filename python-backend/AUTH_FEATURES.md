# Authentication Enhancement - Email Verification, Password Reset & Google OAuth

This document describes the new authentication features added to HR Tech's Python backend.

## Features Implemented

### 1. Email Verification

- New users must verify their email address after registration
- Verification emails are sent via Mailgun
- Verification tokens expire after 24 hours
- Users can request a new verification email if needed
- Login is blocked until email is verified (configurable)

### 2. Password Reset (Forgot Password)

- Users can request a password reset link via email
- Reset tokens expire after 1 hour for security
- Users receive confirmation email after password change
- OAuth users (Google) cannot reset passwords

### 3. Google OAuth Integration

- Users can sign in/sign up using their Google account
- Google accounts are automatically email-verified
- Existing local accounts can be linked to Google OAuth
- Works in development mode with Google OAuth 2.0

## New API Endpoints

### Email Verification

#### POST `/api/verify-email`

Verify user's email address using the token from the verification email.

**Request Body:**

```json
{
  "token": "verification_token_from_email"
}
```

**Response (200):**

```json
{
  "message": "Email verified successfully",
  "user": {
    "id": "user_id",
    "name": "User Name",
    "email": "user@example.com",
    "user_type": "candidate",
    "email_verified": true
  }
}
```

#### POST `/api/resend-verification`

Resend verification email to user.

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Response (200):**

```json
{
  "message": "Verification email sent successfully"
}
```

### Password Reset

#### POST `/api/forgot-password`

Request a password reset email.

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Response (200):**

```json
{
  "message": "If your email is registered, you will receive a password reset link"
}
```

#### POST `/api/reset-password`

Reset password using the token from the reset email.

**Request Body:**

```json
{
  "token": "reset_token_from_email",
  "password": "new_password",
  "confirmPassword": "new_password"
}
```

**Response (200):**

```json
{
  "message": "Password reset successfully"
}
```

### Google OAuth

#### POST `/api/google-oauth`

Authenticate or create user with Google OAuth token.

**Request Body:**

```json
{
  "token": "google_id_token",
  "userType": "candidate"
}
```

**Response (200):**

```json
{
  "message": "Logged in successfully with Google",
  "token": "jwt_token",
  "user": {
    "id": "user_id",
    "name": "User Name",
    "email": "user@example.com",
    "user_type": "candidate",
    "email_verified": true,
    "auth_provider": "google"
  }
}
```

## Modified Endpoints

### POST `/api/register`

Now returns additional fields:

**Response (201):**

```json
{
  "message": "User registered successfully. Please check your email to verify your account.",
  "token": "jwt_token",
  "email_verification_required": true,
  "user": {
    "id": "user_id",
    "name": "User Name",
    "email": "user@example.com",
    "user_type": "candidate",
    "email_verified": false
  }
}
```

### POST `/api/login`

Now checks email verification status:

**Response (403) - if email not verified:**

```json
{
  "error": "Please verify your email before logging in",
  "email_verification_required": true
}
```

### GET `/api/me`

Now returns additional fields:

**Response (200):**

```json
{
  "id": "user_id",
  "name": "User Name",
  "email": "user@example.com",
  "user_type": "candidate",
  "email_verified": true,
  "auth_provider": "local"
}
```

## Environment Variables

Add these variables to your `.env` file:

```env
# Email Verification Configuration
REQUIRE_EMAIL_VERIFICATION=true

# Mailgun Configuration (for sending emails)
MAILGUN_API_KEY=your-mailgun-api-key
MAILGUN_DOMAIN=your-mailgun-domain.com
MAILGUN_FROM_EMAIL=noreply@your-mailgun-domain.com

# Frontend URL (for email links)
FRONTEND_URL=http://localhost:5173

# Google OAuth Configuration (for Google Sign-In)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
```

### Configuration Details

- **REQUIRE_EMAIL_VERIFICATION**: Set to `false` to disable email verification requirement
- **MAILGUN_API_KEY**: Your Mailgun API key from the Mailgun dashboard
- **MAILGUN_DOMAIN**: Your verified Mailgun domain
- **MAILGUN_FROM_EMAIL**: The email address to send emails from
- **FRONTEND_URL**: Your React frontend URL (used for email links)
- **GOOGLE_CLIENT_ID**: Your Google OAuth 2.0 Client ID from Google Cloud Console

## Setting Up Mailgun

1. Sign up at [mailgun.com](https://www.mailgun.com/)
2. Verify your domain or use the sandbox domain for testing
3. Get your API key from the dashboard
4. Add the credentials to your `.env` file

## Setting Up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API
4. Go to "Credentials" and create an OAuth 2.0 Client ID
5. Add authorized JavaScript origins:
   - `http://localhost:5173` (for local development)
   - Your production frontend URL
6. Add authorized redirect URIs:
   - `http://localhost:5173` (for local development)
   - Your production frontend URL
7. Copy the Client ID and add it to your `.env` file

### Frontend Integration (React)

Install Google OAuth library:

```bash
npm install @react-oauth/google
```

Wrap your app with GoogleOAuthProvider:

```jsx
import { GoogleOAuthProvider } from "@react-oauth/google";

<GoogleOAuthProvider clientId="your-google-client-id">
  <App />
</GoogleOAuthProvider>;
```

Use GoogleLogin component:

```jsx
import { GoogleLogin } from "@react-oauth/google";

<GoogleLogin
  onSuccess={(credentialResponse) => {
    // Send credentialResponse.credential to backend
    fetch("http://localhost:8080/api/google-oauth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: credentialResponse.credential,
        userType: "candidate",
      }),
    });
  }}
  onError={() => {
    console.log("Login Failed");
  }}
/>;
```

## Database Changes

The following fields are added to the user collection:

- `email_verified` (boolean): Whether the user's email is verified
- `verification_token` (string): Token for email verification
- `verification_token_expires` (datetime): Expiry time for verification token
- `reset_token` (string): Token for password reset
- `reset_token_expires` (datetime): Expiry time for reset token
- `auth_provider` (string): Authentication provider ('local' or 'google')
- `google_id` (string): Google user ID for OAuth users

## Installing New Dependencies

Run this command to install the new packages:

```bash
pip install google-auth-oauthlib==1.2.1
```

Note: The `requests` package is already installed, so no additional installation needed for Mailgun integration.

## Security Features

1. **Token Expiration**:

   - Verification tokens expire after 24 hours
   - Reset tokens expire after 1 hour

2. **Password Requirements**:

   - Minimum 6 characters (can be increased)

3. **Security Best Practices**:

   - Password reset doesn't reveal if email exists
   - OAuth users cannot reset passwords
   - Email verification can be disabled for development

4. **Email Notifications**:
   - Users receive confirmation after password change
   - Verification emails have clear expiry information

## Backward Compatibility

The implementation maintains backward compatibility:

1. **Existing Users**: Existing users without `email_verified` field will still be able to login
2. **Optional Verification**: Email verification can be disabled by setting `REQUIRE_EMAIL_VERIFICATION=false`
3. **Existing Workflows**: All existing authentication workflows continue to work

## Email Templates

The email service includes professional HTML email templates for:

1. **Verification Email**: Welcome message with verification link
2. **Password Reset Email**: Security notice with reset link
3. **Password Changed Confirmation**: Notification of successful password change

All emails include:

- HR Tech branding
- Clear call-to-action buttons
- Plain text fallback
- Security warnings where appropriate
- Responsive design

## Error Handling

The implementation includes comprehensive error handling:

- Invalid or expired tokens
- Missing required fields
- Email already verified
- User not found
- Google OAuth errors
- Email sending failures

## Testing

### Test Email Verification:

1. Register a new user
2. Check your email for verification link
3. Click the link or send POST request to `/api/verify-email` with the token
4. Try to login - should succeed after verification

### Test Password Reset:

1. Click "Forgot Password" on login page
2. Enter your email
3. Check your email for reset link
4. Click the link or send POST request to `/api/reset-password` with the token and new password
5. Login with new password

### Test Google OAuth:

1. Click "Sign in with Google" button
2. Authorize the app
3. Backend receives the token and creates/logs in user
4. User is automatically email-verified

## Development Mode

For development without email verification:

```env
REQUIRE_EMAIL_VERIFICATION=false
```

This allows testing without setting up Mailgun.

## Production Considerations

1. **Email Deliverability**: Use a verified domain in Mailgun
2. **Rate Limiting**: Consider adding rate limiting for password reset requests
3. **HTTPS**: Ensure all email links use HTTPS in production
4. **Google OAuth**: Add production URLs to Google Console
5. **Email Templates**: Customize email templates to match your brand

## Support

For issues or questions:

- Check the logs for error messages
- Verify environment variables are set correctly
- Ensure Mailgun domain is verified
- Verify Google OAuth credentials are correct

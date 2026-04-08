# Quick Setup Guide for New Authentication Features

## Step 1: Install New Dependencies

```bash
cd python-backend
pip install google-auth-oauthlib==1.2.1
```

Note: `requests` package is already installed in your requirements.txt

## Step 2: Configure Environment Variables

Add these to your `python-backend/.env` file:

```env
# Email Verification Configuration (set to false for testing without emails)
REQUIRE_EMAIL_VERIFICATION=true

# Mailgun Configuration
MAILGUN_API_KEY=your-mailgun-api-key
MAILGUN_DOMAIN=your-mailgun-domain.com
MAILGUN_FROM_EMAIL=noreply@your-mailgun-domain.com

# Frontend URL (for email verification and reset links)
FRONTEND_URL=http://localhost:5173

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
```

## Step 3: Get Mailgun Credentials

1. Sign up at https://www.mailgun.com/
2. For testing, use the sandbox domain (no verification needed)
3. Get your API key from Settings → API Keys
4. Use the sandbox domain like `sandboxXXXXX.mailgun.org`

## Step 4: Get Google OAuth Credentials

1. Go to https://console.cloud.google.com/
2. Create a project or select existing
3. Go to "APIs & Services" → "Credentials"
4. Click "Create Credentials" → "OAuth client ID"
5. Select "Web application"
6. Add authorized JavaScript origins:
   - `http://localhost:5173`
7. Add authorized redirect URIs:
   - `http://localhost:5173`
8. Copy the Client ID

## Step 5: Frontend Integration (React)

### Install Google OAuth package:

```bash
cd react-frontend
npm install @react-oauth/google
```

### Update your main App file (src/App.jsx or src/index.js):

```jsx
import { GoogleOAuthProvider } from "@react-oauth/google";

// Wrap your app
<GoogleOAuthProvider clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID}>
  <App />
</GoogleOAuthProvider>;
```

### Create .env file in react-frontend:

```env
REACT_APP_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
```

### Add Google Login Button to your Login/Register page:

```jsx
import { GoogleLogin } from "@react-oauth/google";

<GoogleLogin
  onSuccess={(credentialResponse) => {
    // Send to your backend
    fetch("http://localhost:8080/api/google-oauth", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        token: credentialResponse.credential,
        userType: "candidate", // or 'recruiter'
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.token) {
          // Save token and user data
          localStorage.setItem("token", data.token);
          // Update your auth context
          // Navigate to dashboard
        }
      })
      .catch((error) => console.error("Error:", error));
  }}
  onError={() => {
    console.log("Login Failed");
  }}
  theme="outline"
  size="large"
  text="continue_with"
/>;
```

### Create Email Verification Page (src/pages/VerifyEmail.jsx):

```jsx
import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";

function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState("verifying");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const token = searchParams.get("token");

    if (token) {
      fetch("http://localhost:8080/api/verify-email", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.message) {
            setStatus("success");
            setMessage(data.message);
            setTimeout(() => navigate("/login"), 3000);
          } else {
            setStatus("error");
            setMessage(data.error || "Verification failed");
          }
        })
        .catch(() => {
          setStatus("error");
          setMessage("An error occurred during verification");
        });
    }
  }, [searchParams, navigate]);

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="card bg-base-100 shadow-xl w-96">
        <div className="card-body items-center text-center">
          {status === "verifying" && (
            <>
              <span className="loading loading-spinner loading-lg"></span>
              <h2 className="card-title">Verifying Email...</h2>
            </>
          )}
          {status === "success" && (
            <>
              <svg
                className="w-16 h-16 text-success"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
              <h2 className="card-title text-success">Success!</h2>
              <p>{message}</p>
              <p className="text-sm text-gray-500">Redirecting to login...</p>
            </>
          )}
          {status === "error" && (
            <>
              <svg
                className="w-16 h-16 text-error"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
              <h2 className="card-title text-error">Error</h2>
              <p>{message}</p>
              <button
                className="btn btn-primary"
                onClick={() => navigate("/login")}
              >
                Go to Login
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default VerifyEmail;
```

### Create Forgot Password Page (src/pages/ForgotPassword.jsx):

```jsx
import { useState } from "react";
import { Link } from "react-router-dom";

function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    setError("");

    try {
      const response = await fetch(
        "http://localhost:8080/api/forgot-password",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email }),
        }
      );

      const data = await response.json();

      if (response.ok) {
        setMessage(data.message);
        setEmail("");
      } else {
        setError(data.error || "Failed to send reset email");
      }
    } catch (err) {
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="card bg-base-100 shadow-xl w-96">
        <div className="card-body">
          <h2 className="card-title justify-center mb-4">Forgot Password</h2>
          <p className="text-sm text-gray-600 mb-4">
            Enter your email address and we'll send you a link to reset your
            password.
          </p>

          {message && (
            <div className="alert alert-success">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="stroke-current shrink-0 h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>{message}</span>
            </div>
          )}

          {error && (
            <div className="alert alert-error">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="stroke-current shrink-0 h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-control">
              <label className="label">
                <span className="label-text">Email</span>
              </label>
              <input
                type="email"
                placeholder="your@email.com"
                className="input input-bordered"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-control mt-6">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? "Sending..." : "Send Reset Link"}
              </button>
            </div>
          </form>

          <div className="text-center mt-4">
            <Link to="/login" className="link link-primary text-sm">
              Back to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ForgotPassword;
```

### Create Reset Password Page (src/pages/ResetPassword.jsx):

```jsx
import { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";

function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const token = searchParams.get("token");

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    setMessage("");
    setError("");

    try {
      const response = await fetch("http://localhost:8080/api/reset-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          token,
          password,
          confirmPassword,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setMessage(data.message);
        setTimeout(() => navigate("/login"), 3000);
      } else {
        setError(data.error || "Failed to reset password");
      }
    } catch (err) {
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="card bg-base-100 shadow-xl w-96">
        <div className="card-body">
          <h2 className="card-title justify-center mb-4">Reset Password</h2>

          {message && (
            <div className="alert alert-success">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="stroke-current shrink-0 h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>{message}</span>
            </div>
          )}

          {error && (
            <div className="alert alert-error">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="stroke-current shrink-0 h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-control">
              <label className="label">
                <span className="label-text">New Password</span>
              </label>
              <input
                type="password"
                placeholder="Enter new password"
                className="input input-bordered"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>

            <div className="form-control mt-4">
              <label className="label">
                <span className="label-text">Confirm Password</span>
              </label>
              <input
                type="password"
                placeholder="Confirm new password"
                className="input input-bordered"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>

            <div className="form-control mt-6">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading || !token}
              >
                {loading ? "Resetting..." : "Reset Password"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default ResetPassword;
```

### Add Routes to your Router:

```jsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import VerifyEmail from "./pages/VerifyEmail";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";

<Routes>
  {/* ... other routes */}
  <Route path="/verify-email" element={<VerifyEmail />} />
  <Route path="/forgot-password" element={<ForgotPassword />} />
  <Route path="/reset-password" element={<ResetPassword />} />
</Routes>;
```

## Step 6: Testing

### Test Email Verification:

1. Set `REQUIRE_EMAIL_VERIFICATION=true` in backend .env
2. Register a new user
3. Check your email (or check Mailgun dashboard logs if using sandbox)
4. Click verification link or copy token and use it

### Test Password Reset:

1. Go to `/forgot-password`
2. Enter your email
3. Check email for reset link
4. Click link and enter new password

### Test Google OAuth:

1. Add Google button to login page
2. Click button
3. Sign in with Google account
4. Should create user and login automatically

## Step 7: Development Mode (Skip Email Verification)

For testing without email setup:

```env
REQUIRE_EMAIL_VERIFICATION=false
```

This allows users to login immediately after registration.

## Step 8: Start Your Application

```bash
# Backend
cd python-backend
python app.py

# Frontend (in another terminal)
cd react-frontend
npm start
```

## Important Notes

1. **Mailgun Sandbox**: For testing, Mailgun sandbox only sends to authorized recipients. Add your email in Mailgun dashboard under "Authorized Recipients"

2. **Google OAuth Testing**: Google OAuth works in development with `http://localhost:5173`. No HTTPS required for localhost.

3. **Email Verification**: Users cannot login until they verify their email (if REQUIRE_EMAIL_VERIFICATION=true)

4. **Backward Compatibility**: Existing users without email verification will still work

## Troubleshooting

**Email not sending?**

- Check Mailgun credentials
- Add recipient to authorized list (sandbox mode)
- Check Mailgun logs in dashboard

**Google OAuth not working?**

- Verify Client ID is correct
- Check authorized origins in Google Console
- Ensure frontend has correct Client ID in .env

**Email verification blocking login?**

- Set `REQUIRE_EMAIL_VERIFICATION=false` for testing
- Check if user's `email_verified` field is true in database

## Next Steps

1. Customize email templates in `python-backend/services/email_service.py`
2. Add rate limiting for password reset requests
3. Implement email change functionality
4. Add more OAuth providers (Facebook, GitHub, etc.)
5. Add 2FA (Two-Factor Authentication)

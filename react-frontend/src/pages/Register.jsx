import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import styles from "./Login.module.css";

const Register = () => {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const userType = "candidate"; // Candidates register here, recruiters use /recruiter-signup
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccessMessage("");
    if (!name.trim() || !email.trim() || !password || !confirmPassword) {
      setError("All fields are required");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setIsLoading(true);

    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          password,
          confirmPassword,
          userType,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Registration failed");
      }

      // Build success message based on verification requirements
      let message = "Account created successfully!";
      if (data.email_verification_required) {
        message += " Please check your email and verify your account.";
      }
      if (data.account_verification_required) {
        message += " Your recruiter account is pending admin verification. You'll have limited access until approved.";
      }

      // Check if email verification is required
      if (data.email_verification_required) {
        setSuccessMessage(message);
        // Clear form
        setName("");
        setEmail("");
        setPassword("");
        setConfirmPassword("");
        // Don't auto-login, user must verify email first
      } else {
        // Store token and user data with user type, verification status, and permissions
        localStorage.setItem(process.env.REACT_APP_TOKEN_KEY, data.token);
        localStorage.setItem(
          process.env.REACT_APP_USER_KEY,
          JSON.stringify({ 
            ...data.user, 
            userType: data.user.user_type || userType,
            isVerified: data.user.is_verified,
            permissions: data.user.permissions || []
          })
        );

        // Navigate to candidate dashboard
        navigate("/");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    setIsLoading(true);
    setError("");
    setSuccessMessage("");

    try {
      const response = await fetch(`${process.env.REACT_APP_API_BASE}/google-oauth`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          token: credentialResponse.credential,
          userType: userType,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Google sign up failed");
      }

      // Store token and user data with verification status and permissions
      localStorage.setItem(process.env.REACT_APP_TOKEN_KEY, data.token);
      localStorage.setItem(
        process.env.REACT_APP_USER_KEY,
        JSON.stringify({
          ...data.user,
          userType: data.user.user_type,
          isVerified: data.user.is_verified,
          permissions: data.user.permissions || []
        })
      );

      // Navigate to candidate dashboard
      navigate("/");
    } catch (error) {
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleError = () => {
    setError("Google sign up failed. Please try again.");
  };

  return (
    <div className={styles.loginContainer}>
      <div className={styles.loginCard}>
        <div className={styles.logoSection}>
          <h1>SmartHire Portal</h1>
          <p>Create your account to access your dashboard.</p>
        </div>

        {/* User Type Selection Tabs */}
        <div className={styles.userTypeTabs}>
          <button
            type="button"
            className={`${styles.tabButton} ${styles.activeTab}`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style={{ width: "16px", height: "16px" }}>
              <path d="M10 8a3 3 0 100-6 3 3 0 000 6zM3.465 14.493a1.23 1.23 0 00.41 1.412A9.957 9.957 0 0010 18c2.31 0 4.438-.784 6.131-2.1.43-.333.604-.903.408-1.41a7.002 7.002 0 00-13.074.003z" />
            </svg>
            Candidate
          </button>
          <button
            type="button"
            className={styles.tabButton}
            onClick={() => navigate("/recruiter-signup")}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style={{ width: "16px", height: "16px" }}>
              <path fillRule="evenodd" d="M6 3.75A2.75 2.75 0 018.75 1h2.5A2.75 2.75 0 0114 3.75v.443c.572.055 1.14.122 1.706.2C17.053 4.582 18 5.75 18 7.07v3.469c0 1.126-.694 2.191-1.83 2.54-1.952.599-4.024.921-6.17.921s-4.219-.322-6.17-.921C2.694 12.73 2 11.665 2 10.539V7.07c0-1.321.947-2.489 2.294-2.676A41.047 41.047 0 016 4.193V3.75zm6.5 0v.325a41.622 41.622 0 00-5 0V3.75c0-.69.56-1.25 1.25-1.25h2.5c.69 0 1.25.56 1.25 1.25zM10 10a1 1 0 00-1 1v.01a1 1 0 001 1h.01a1 1 0 001-1V11a1 1 0 00-1-1H10z" clipRule="evenodd" />
              <path d="M3 15.055v-.684c.126.053.255.1.39.142 2.092.642 4.313.987 6.61.987 2.297 0 4.518-.345 6.61-.987.135-.041.264-.089.39-.142v.684c0 1.347-.985 2.53-2.363 2.686a41.454 41.454 0 01-9.274 0C3.985 17.585 3 16.402 3 15.055z" />
            </svg>
            Recruiter
          </button>
        </div>

        <form className={styles.loginForm} onSubmit={handleSubmit}>
          {successMessage && (
            <div className={styles.successMessage}>
              {successMessage}
            </div>
          )}

          {error && <div className={styles.errorMessage}>{error}</div>}

          <div className={styles.inputGroup}>
            <label htmlFor="name">Full Name</label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter your full name"
              required
            />
          </div>

          <div className={styles.inputGroup}>
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
            />
          </div>

          <div className={styles.inputGroup}>
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Create a password"
              required
            />
          </div>

          <div className={styles.inputGroup}>
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter your password"
              required
            />
          </div>

          <button type="submit" className={styles.loginButton} disabled={isLoading}>
            {isLoading ? "Creating account..." : "Create Candidate Account"}
          </button>
        </form>

        <div className={styles.oauthSection}>
          <div className={styles.divider}>
            <span>or sign up with</span>
          </div>
          <div className={styles.googleButtonWrapper}>
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              theme="outline"
              size="large"
              text="signup_with"
              width="100%"
            />
          </div>
        </div>

        <div className={styles.registerSection}>
          <p>
            Already have an account? <Link to="/login">Log in</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;
import AuthShell from "../components/AuthShell";
import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useGoogleLogin } from "@react-oauth/google";
import styles from "./Login.module.css";
import { setToken, setUser } from "shared/utils/session";
import { authPost } from "features/auth/api/authApi";

const STRENGTH_LEVELS = [
  { label: "Too short", color: "#ef4444" },
  { label: "Weak",      color: "#f97316" },
  { label: "Fair",      color: "#eab308" },
  { label: "Strong",    color: "#22c55e" },
];

function getPasswordStrength(pwd) {
  if (!pwd || pwd.length < 8) return 0;
  const types = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^a-zA-Z0-9]/].filter(r => r.test(pwd)).length;
  if (types <= 1) return 1;
  if (types === 2 || pwd.length < 12) return 2;
  return 3;
}

function getStrengthHint(pwd) {
  if (!pwd) return "";
  if (pwd.length < 8) return "Use at least 8 characters";
  const missing = [];
  if (!/[A-Z]/.test(pwd)) missing.push("uppercase letter");
  if (!/[0-9]/.test(pwd)) missing.push("number");
  if (!/[^a-zA-Z0-9]/.test(pwd)) missing.push("symbol");
  if (missing.length) return `Add a ${missing.slice(0, 2).join(" or ")} to strengthen`;
  return "";
}

const Register = () => {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
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
      const response = await authPost("/register", {
          name: name.trim(),
          email: email.trim(),
          password,
          confirmPassword,
          userType,
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
        setToken(data.token);
        setUser({ 
            ...data.user, 
            userType: data.user.user_type || userType,
            isVerified: data.user.is_verified,
            permissions: data.user.permissions || []
          });

        // Navigate to candidate dashboard
        navigate("/dashboard");
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
      const response = await authPost("/google-oauth", {
          token: credentialResponse.credential,
          userType: userType,
        });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Google sign up failed");
      }

      // Store token and user data with verification status and permissions
      setToken(data.token);
      setUser({
          ...data.user,
          userType: data.user.user_type,
          isVerified: data.user.is_verified,
          permissions: data.user.permissions || []
        });

      // Navigate to candidate dashboard
      navigate("/dashboard");
    } catch (error) {
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleError = () => {
    setError("Google sign up failed. Please try again.");
  };

  const googleRegister = useGoogleLogin({
    onSuccess: (t) => handleGoogleSuccess({ credential: t.access_token }),
    onError: handleGoogleError,
  });

  return (
    <AuthShell description="Build your profile, explore roles and prepare with AI interviews and role-based mock online assessments.">
      <div className={`${styles.loginCard} ${styles.signupCard}`}>
        <div className={styles.logoSection}>
          <span className={styles.formEyebrow}>YOUR NEXT CHAPTER STARTS HERE</span>
          <h1>Create your account.</h1>
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
              autoComplete="name"
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
              autoComplete="email"
              required
            />
          </div>

          <div className={styles.inputGroup}>
            <label htmlFor="password">Password</label>
            <div className={styles.passwordInputWrapper}>
              <input
                type={showPassword ? "text" : "password"}
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a password"
                autoComplete="new-password"
                required
              />
              <button
                type="button"
                className={styles.passwordToggle}
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M3.28 2.22a.75.75 0 00-1.06 1.06l14.5 14.5a.75.75 0 101.06-1.06l-1.745-1.745a10.029 10.029 0 003.3-4.38 1.651 1.651 0 000-1.185A10.004 10.004 0 009.999 3a9.956 9.956 0 00-4.744 1.194L3.28 2.22zM7.752 6.69l1.092 1.092a2.5 2.5 0 013.374 3.373l1.091 1.092a4 4 0 00-5.557-5.557z" clipRule="evenodd" />
                    <path d="M10.748 13.93l2.523 2.523a9.987 9.987 0 01-3.27.547c-4.258 0-7.894-2.66-9.337-6.41a1.651 1.651 0 010-1.186A10.007 10.007 0 012.839 6.02L6.07 9.252a4 4 0 004.678 4.678z" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" />
                    <path fillRule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            </div>
            {password && (() => {
              const level = getPasswordStrength(password);
              const { label, color } = STRENGTH_LEVELS[level];
              const hint = getStrengthHint(password);
              return (
                <div className={styles.strengthMeter} role="status" aria-live="polite">
                  <div className={styles.strengthBar}>
                    {STRENGTH_LEVELS.map((_, i) => (
                      <div
                        key={i}
                        className={styles.strengthSegment}
                        style={{ background: i <= level ? color : undefined }}
                      />
                    ))}
                  </div>
                  <div className={styles.strengthRow}>
                    {hint && <span className={styles.strengthHint}>{hint}</span>}
                    <span className={styles.strengthLabel} style={{ color }}>{label}</span>
                  </div>
                </div>
              );
            })()}
          </div>

          <div className={styles.inputGroup}>
            <label htmlFor="confirmPassword">Confirm Password</label>
            <div className={styles.passwordInputWrapper}>
              <input
                type={showConfirmPassword ? "text" : "password"}
                id="confirmPassword"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                required
              />
              <button
                type="button"
                className={styles.passwordToggle}
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                aria-label={showConfirmPassword ? "Hide password" : "Show password"}
              >
                {showConfirmPassword ? (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M3.28 2.22a.75.75 0 00-1.06 1.06l14.5 14.5a.75.75 0 101.06-1.06l-1.745-1.745a10.029 10.029 0 003.3-4.38 1.651 1.651 0 000-1.185A10.004 10.004 0 009.999 3a9.956 9.956 0 00-4.744 1.194L3.28 2.22zM7.752 6.69l1.092 1.092a2.5 2.5 0 013.374 3.373l1.091 1.092a4 4 0 00-5.557-5.557z" clipRule="evenodd" />
                    <path d="M10.748 13.93l2.523 2.523a9.987 9.987 0 01-3.27.547c-4.258 0-7.894-2.66-9.337-6.41a1.651 1.651 0 010-1.186A10.007 10.007 0 012.839 6.02L6.07 9.252a4 4 0 004.678 4.678z" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" />
                    <path fillRule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            </div>
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
            <button
              type="button"
              onClick={() => googleRegister()}
              className={styles.googleBtn}
            >
              <svg viewBox="0 0 24 24" width="18" height="18">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Sign up with Google
            </button>
          </div>
        </div>

        <div className={styles.registerSection}>
          <p>
            Already have an account? <Link to="/login">Log in</Link>
          </p>
        </div>
      </div>
    </AuthShell>
  );
};

export default Register;
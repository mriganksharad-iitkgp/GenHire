import React, { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import styles from "./Login.module.css";

const STRENGTH_LEVELS = [
  { label: "Too short", color: "#e53e3e" },
  { label: "Weak",      color: "#dd6b20" },
  { label: "Fair",      color: "#d69e2e" },
  { label: "Strong",    color: "#38a169" },
];

function getPasswordStrength(pwd) {
  if (pwd.length < 8) return 0;
  let score = 0;
  if (/[a-z]/.test(pwd)) score++;
  if (/[A-Z]/.test(pwd)) score++;
  if (/[0-9]/.test(pwd)) score++;
  if (/[^a-zA-Z0-9]/.test(pwd)) score++;
  if (score <= 1) return 1;
  if (score === 2) return 2;
  return 3;
}

function getStrengthHint(pwd) {
  if (pwd.length < 8) return "Add more characters";
  if (!/[A-Z]/.test(pwd)) return "Add uppercase letters";
  if (!/[0-9]/.test(pwd)) return "Add numbers";
  if (!/[^a-zA-Z0-9]/.test(pwd)) return "Add symbols for extra strength";
  return "";
}

const ResetPassword = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const token = searchParams.get("token");

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long");
      return;
    }

    setIsLoading(true);
    setMessage("");
    setError("");

    try {
      const response = await fetch(
        `${process.env.REACT_APP_API_BASE}/reset-password`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            token,
            password,
            confirmPassword,
          }),
        }
      );

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
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div className={styles.loginContainer}>
        <div className={styles.loginCard}>
          <div className={styles.logoSection}>
            <h1>Invalid Link</h1>
            <p>This password reset link is invalid or has expired.</p>
          </div>
          <button
            className={styles.loginButton}
            onClick={() => navigate("/forgot-password")}
          >
            Request New Link
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.loginContainer}>
      <div className={styles.loginCard}>
        <div className={styles.logoSection}>
          <h1>Reset Password</h1>
          <p>Enter your new password below.</p>
        </div>

        {message && (
          <div
            className={styles.successMessage}
            style={{
              backgroundColor: "#d1fae5",
              color: "#065f46",
              padding: "1rem",
              borderRadius: "8px",
              marginBottom: "1rem",
              border: "1px solid #10b981",
            }}
          >
            <strong>✓ </strong>
            {message}
            <p style={{ marginTop: "0.5rem", fontSize: "0.9rem" }}>
              Redirecting to login...
            </p>
          </div>
        )}

        {error && <div className={styles.errorMessage}>{error}</div>}

        <form className={styles.loginForm} onSubmit={handleSubmit}>
          <div className={styles.inputGroup}>
            <label htmlFor="password">New Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter new password"
              required
              minLength={8}
            />
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
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              required
              minLength={8}
            />
          </div>

          <button
            type="submit"
            className={styles.loginButton}
            disabled={isLoading}
          >
            {isLoading ? "Resetting..." : "Reset Password"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ResetPassword;

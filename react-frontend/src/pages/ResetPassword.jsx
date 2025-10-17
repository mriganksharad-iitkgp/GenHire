import React, { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import styles from "./Login.module.css";

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

    if (password.length < 6) {
      setError("Password must be at least 6 characters long");
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
              minLength={6}
            />
            <small style={{ color: "#666", fontSize: "0.85rem" }}>
              Minimum 6 characters
            </small>
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
              minLength={6}
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


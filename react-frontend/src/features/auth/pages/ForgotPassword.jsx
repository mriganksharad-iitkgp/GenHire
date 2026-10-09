import AuthShell from "features/auth/components/AuthShell";
import React, { useState } from "react";
import { Link } from "react-router-dom";
import styles from "./Login.module.css";
import { authPost } from "features/auth/api/authApi";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage("");
    setError("");

    try {
      const response = await authPost("/forgot-password", { email });

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
      setIsLoading(false);
    }
  };

  return (
    <AuthShell title="Your workspace awaits." accent="Continue with confidence." description="Manage your account access and return to your hiring or interview workspace.">
      <div className={`${styles.loginCard} ${styles.signupCard}`}>
        <div className={styles.logoSection}>
          <h1>Reset your password</h1>
          <p>
            Enter your email address and we'll send you a link to reset your
            password.
          </p>
        </div>

        {message && (
          <div className={styles.successMessage}>
            {message}
          </div>
        )}

        {error && <div className={styles.errorMessage}>{error}</div>}

        <form className={styles.loginForm} onSubmit={handleSubmit}>
          <div className={styles.inputGroup}>
            <label htmlFor="email">Email Address</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              autoComplete="email"
              required
            />
          </div>

          <button
            type="submit"
            className={styles.loginButton}
            disabled={isLoading}
          >
            {isLoading ? "Sending..." : "Send reset link"}
          </button>
        </form>

        <div className={styles.registerSection}>
          <p>
            Remember your password? <Link to="/login">Return to sign in</Link>
          </p>
        </div>
      </div>
    </AuthShell>
  );
};

export default ForgotPassword;


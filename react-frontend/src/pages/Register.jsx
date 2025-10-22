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
  const [userType, setUserType] = useState("candidate"); // 'candidate' or 'recruiter'
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

      // Check if email verification is required
      if (data.email_verification_required) {
        setSuccessMessage(
          "Account created successfully! Please check your email and verify your account before logging in."
        );
        // Clear form
        setName("");
        setEmail("");
        setPassword("");
        setConfirmPassword("");
        // Don't auto-login, user must verify email first
      } else {
        // Store token and user data with user type (consistent with Login)
        localStorage.setItem(process.env.REACT_APP_TOKEN_KEY, data.token);
        localStorage.setItem(
          process.env.REACT_APP_USER_KEY,
          JSON.stringify({ ...data.user, userType })
        );

        // Navigate based on user type
        if (userType === "recruiter") {
          navigate("/recruiter-dashboard");
        } else {
          navigate("/");
        }
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

      // Store token and user data
      localStorage.setItem(process.env.REACT_APP_TOKEN_KEY, data.token);
      localStorage.setItem(
        process.env.REACT_APP_USER_KEY,
        JSON.stringify({
          ...data.user,
          userType: data.user.user_type,
        })
      );

      // Navigate based on user type
      if (data.user.user_type === "recruiter") {
        navigate("/recruiter-dashboard");
      } else {
        navigate("/");
      }
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
          <h1>TechCorp Solutions Portal</h1>
          <p>Create your account to access your dashboard.</p>
        </div>

        {/* User Type Selection Tabs */}
        <div className={styles.userTypeTabs}>
          <button
            type="button"
            className={`${styles.tabButton} ${userType === "candidate" ? styles.activeTab : ""}`}
            onClick={() => setUserType("candidate")}
          >
            <i className="fa fa-user"></i>
            Candidate
          </button>
          <button
            type="button"
            className={`${styles.tabButton} ${userType === "recruiter" ? styles.activeTab : ""}`}
            onClick={() => setUserType("recruiter")}
          >
            <i className="fa fa-briefcase"></i>
            Recruiter
          </button>
        </div>

        <form className={styles.loginForm} onSubmit={handleSubmit}>
          {successMessage && (
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
              placeholder={`Enter your ${userType} email`}
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
            {isLoading
              ? "Creating account..."
              : `Create Account as ${userType === "candidate" ? "Candidate" : "Recruiter"}`}
          </button>
        </form>

        <div style={{ margin: "1.5rem 0", textAlign: "center", color: "#666" }}>
          <div style={{ display: "flex", alignItems: "center", margin: "1rem 0" }}>
            <div style={{ flex: 1, height: "1px", backgroundColor: "#ddd" }}></div>
            <span style={{ padding: "0 1rem", fontSize: "0.9rem" }}>OR</span>
            <div style={{ flex: 1, height: "1px", backgroundColor: "#ddd" }}></div>
          </div>

          <div style={{ display: "flex", justifyContent: "center" }}>
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              theme="outline"
              size="large"
              text="signup_with"
              width="300"
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
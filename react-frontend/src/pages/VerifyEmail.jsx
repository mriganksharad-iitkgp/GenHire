import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import styles from "./Login.module.css";

const VerifyEmail = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState("verifying");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const token = searchParams.get("token");

    if (!token) {
      setStatus("error");
      setMessage("No verification token provided");
      return;
    }

    // Verify email with backend
    fetch(`${process.env.REACT_APP_API_BASE}/verify-email`, {
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
  }, [searchParams, navigate]);

  return (
    <div className={styles.loginContainer}>
      <div className={styles.loginCard}>
        <div className={styles.logoSection}>
          <h1>Email Verification</h1>
        </div>

        <div style={{ textAlign: "center", padding: "2rem 0" }}>
          {status === "verifying" && (
            <>
              <div className={styles.spinner}></div>
              <h2 style={{ marginTop: "1rem" }}>Verifying Email...</h2>
              <p>Please wait while we verify your email address.</p>
            </>
          )}

          {status === "success" && (
            <>
              <div style={{ fontSize: "4rem", color: "#10b981" }}>✓</div>
              <h2 style={{ color: "#10b981", marginTop: "1rem" }}>
                Success!
              </h2>
              <p>{message}</p>
              <p style={{ fontSize: "0.9rem", color: "#666", marginTop: "1rem" }}>
                Redirecting to login...
              </p>
            </>
          )}

          {status === "error" && (
            <>
              <div style={{ fontSize: "4rem", color: "#ef4444" }}>✗</div>
              <h2 style={{ color: "#ef4444", marginTop: "1rem" }}>Error</h2>
              <p>{message}</p>
              <button
                className={styles.loginButton}
                onClick={() => navigate("/login")}
                style={{ marginTop: "1.5rem" }}
              >
                Go to Login
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default VerifyEmail;


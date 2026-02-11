import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle, Home, FileText, Sparkles } from "lucide-react";
import styles from "./PaymentSuccess.module.css";

const PaymentSuccess = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [showConfetti, setShowConfetti] = useState(true);

  const sessionId = searchParams.get("session_id");

  useEffect(() => {
    const timer = setTimeout(() => setShowConfetti(false), 3000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className={styles.container}>
      {/* Animated Background Elements */}
      <div className={styles.backgroundElements}>
        <div className={styles.blob1}></div>
        <div className={styles.blob2}></div>
        <div className={styles.blob3}></div>
      </div>

      {/* Confetti Animation */}
      {showConfetti && (
        <div className={styles.confettiContainer}>
          {[...Array(50)].map((_, i) => (
            <div
              key={i}
              className={styles.confettiItem}
              style={{
                left: `${Math.random() * 100}%`,
                top: `-${Math.random() * 20}%`,
                animationDelay: `${Math.random() * 2}s`,
                animationDuration: `${2 + Math.random() * 2}s`,
              }}
            >
              <Sparkles
                size={12 + Math.random() * 12}
                style={{
                  color: [
                    "#FFD700",
                    "#00FF00",
                    "#00CED1",
                    "#FF69B4",
                    "#FFA500",
                  ][Math.floor(Math.random() * 5)],
                }}
              />
            </div>
          ))}
        </div>
      )}

      {/* Main Card */}
      <div className={styles.card}>
        {/* Success Icon */}
        <div className={styles.iconWrapper}>
          <div className={styles.iconPing}>
            <div className={styles.iconPingCircle}></div>
          </div>
          <div className={styles.iconCircle}>
            <div className={styles.iconBackground}>
              <CheckCircle className={styles.icon} strokeWidth={2.5} />
            </div>
          </div>
        </div>

        {/* Success Message */}
        <h1 className={styles.title}>Payment Successful!</h1>
        <p className={styles.subtitle}>Thank you for your purchase!</p>
        <p className={styles.description}>
          Your transaction has been completed successfully. A confirmation email
          will be sent to you shortly.
        </p>

        {/* Transaction Details */}
        {sessionId && (
          <div className={styles.transactionBox}>
            <p className={styles.transactionLabel}>Transaction ID</p>
            <p className={styles.transactionId}>{sessionId}</p>
          </div>
        )}

        {/* Action Buttons */}
        <div className={styles.buttonGroup}>
          <button
            onClick={() => navigate("/")}
            className={styles.primaryButton}
          >
            <Home className={styles.buttonIcon} />
            Go to Dashboard
          </button>
          <button
            onClick={() => navigate("/applications")}
            className={styles.secondaryButton}
          >
            <FileText className={styles.buttonIcon} />
            View Applications
          </button>
        </div>

        {/* Footer Note */}
        <p className={styles.footer}>
          Need help? Contact our{" "}
          <a href="/support" className={styles.supportLink}>
            support team
          </a>
        </p>
      </div>
    </div>
  );
};

export default PaymentSuccess;

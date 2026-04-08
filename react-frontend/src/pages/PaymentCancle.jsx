import React from "react";
import { useNavigate } from "react-router-dom";
import { XCircle, Home, RefreshCw, HelpCircle } from "lucide-react";
import styles from "./PaymentCancle.module.css";

const PaymentCancel = () => {
  const navigate = useNavigate();

  return (
    <div className={styles.container}>
      {/* Animated Background Elements */}
      <div className={styles.backgroundElements}>
        <div className={styles.blob1}></div>
        <div className={styles.blob2}></div>
        <div className={styles.blob3}></div>
      </div>

      {/* Main Card */}
      <div className={styles.card}>
        {/* Cancel Icon */}
        <div className={styles.iconWrapper}>
          <div className={styles.iconPing}>
            <div className={styles.iconPulseCircle}></div>
          </div>
          <div className={styles.iconCircle}>
            <div className={styles.iconBackground}>
              <XCircle className={styles.icon} strokeWidth={2.5} />
            </div>
          </div>
        </div>

        {/* Cancel Message */}
        <h1 className={styles.title}>Payment Cancelled</h1>
        <p className={styles.subtitle}>Your payment was not completed</p>
        <p className={styles.description}>
          Don't worry! No charges have been made to your account. You can try
          again or return to the dashboard.
        </p>

        {/* Info Box */}
        <div className={styles.infoBox}>
          <div className={styles.infoContent}>
            <HelpCircle className={styles.infoIcon} />
            <div>
              <p className={styles.infoTitle}>Why was my payment cancelled?</p>
              <ul className={styles.infoList}>
                <li>• You chose to cancel the transaction</li>
                <li>• The session may have timed out</li>
                <li>• There might be an issue with your payment method</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className={styles.buttonGroup}>
          <button onClick={() => navigate(-1)} className={styles.primaryButton}>
            <RefreshCw className={styles.buttonIcon} />
            Try Again
          </button>
          <button
            onClick={() => navigate("/")}
            className={styles.secondaryButton}
          >
            <Home className={styles.buttonIcon} />
            Go to Dashboard
          </button>
        </div>

        {/* Footer Note */}
        <p className={styles.footer}>
          Having trouble?{" "}
          <a href="/support" className={styles.supportLink}>
            Contact support
          </a>{" "}
          for assistance
        </p>
      </div>
    </div>
  );
};

export default PaymentCancel;

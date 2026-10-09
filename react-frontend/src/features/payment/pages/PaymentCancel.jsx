import React from "react";
import { useNavigate } from "react-router-dom";
import { XCircle, Home, RefreshCw, HelpCircle } from "lucide-react";
import { getUser } from "shared/utils/session";
import styles from "./PaymentCancel.module.css";

const PaymentCancel = () => {
  const navigate = useNavigate();
  const user = getUser(); const recruiter = (user?.userType || user?.user_type) === "recruiter";
  const dashboard = !user ? "/login" : recruiter ? "/recruiter/dashboard" : (user.userType || user.user_type) === "admin" ? "/admin" : "/dashboard";

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
          The checkout was not completed. Review your wallet history before trying again. If you see a bank debit, check its status with your payment provider.
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
          <button onClick={() => navigate(!user ? "/login" : recruiter ? "/recruiter/subscription" : "/candidate/subscription")} className={styles.primaryButton}>
            <RefreshCw className={styles.buttonIcon} />
            Try Again
          </button>
          <button
            onClick={() => navigate(dashboard)}
            className={styles.secondaryButton}
          >
            <Home className={styles.buttonIcon} />
            Return to dashboard
          </button>
        </div>

        {/* Footer Note */}
        <p className={styles.footer}>Review recharge history for the confirmed transaction status.</p>
      </div>
    </div>
  );
};

export default PaymentCancel;

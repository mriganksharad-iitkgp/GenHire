import React from "react";
import { useNavigate } from "react-router-dom";
import styles from "./UpgradeButton.module.css";
import useSubscription from "./useSubscription";

/**
 * UpgradeButton - Navbar component for subscription management
 * Shows current plan status and navigates to subscription page
 */
const UpgradeButton = () => {
  const navigate = useNavigate();
  const {
    subscription,
    loading,
    isFreeTier,
    interviewsRemaining,
    isLowUsage,
    isOutOfInterviews,
  } = useSubscription();

  const handleClick = () => {
    navigate("/subscription");
  };

  // Determine button style based on subscription status
  const getButtonClass = () => {
    if (loading) return styles.loading;
    if (isOutOfInterviews) return styles.critical;
    if (isLowUsage) return styles.warning;
    if (isFreeTier) return styles.freeTier;
    return styles.paidTier;
  };

  // Get status indicator
  const getStatusText = () => {
    if (loading) return "Loading...";
    if (isOutOfInterviews) return "No interviews left";
    if (subscription?.is_unlimited) return "Unlimited";
    return `${interviewsRemaining} left`;
  };

  return (
    <button
      className={`${styles.upgradeButton} ${getButtonClass()}`}
      onClick={handleClick}
      disabled={loading}
    >
      <div className={styles.buttonContent}>
        <div className={styles.iconWrapper}>
          {loading ? (
            <div className={styles.spinner}></div>
          ) : isFreeTier ? (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2z" />
            </svg>
          ) : (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2z" />
            </svg>
          )}
        </div>
        <div className={styles.textWrapper}>
          <span className={styles.planName}>
            {loading ? "Plan" : subscription?.plan?.name || "Free Tier"}
          </span>
          <span className={styles.statusText}>{getStatusText()}</span>
        </div>
        {(isFreeTier || isLowUsage) && !loading && (
          <div className={styles.upgradeBadge}>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="12" y1="19" x2="12" y2="5" />
              <polyline points="5 12 12 5 19 12" />
            </svg>
          </div>
        )}
      </div>
    </button>
  );
};

export default UpgradeButton;

import React from "react";
import styles from "./SubscriptionBanner.module.css";

/**
 * SubscriptionBanner - Shows current subscription status and usage
 * Displays plan info, interviews remaining, and upgrade prompt
 */
const SubscriptionBanner = ({
  subscription,
  onUpgrade,
  loading = false,
  compact = false,
}) => {
  if (loading) {
    return (
      <div
        className={`${styles.banner} ${styles.loading} ${
          compact ? styles.compact : ""
        }`}
      >
        <div className={styles.loadingPulse}>
          <div className={styles.loadingBar}></div>
          <div className={styles.loadingBar} style={{ width: "60%" }}></div>
        </div>
      </div>
    );
  }

  // Default to free tier if no subscription
  const planName = subscription?.plan?.name || "Free Tier";
  const creditsRemaining = Number(
    subscription?.credits_remaining ?? subscription?.interviews_remaining ?? 2,
  );
  const creditsAllowed = Number(
    subscription?.credits_allocated ?? subscription?.interviews_allowed ?? 2,
  );
  const interviewsRemaining = subscription?.interviews_remaining ?? 2;
  const interviewsAllowed = subscription?.interviews_allowed ?? 2;
  const isUnlimited = subscription?.is_unlimited || false;
  const expiresAt = subscription?.expires_at;
  const isFreeTier = !subscription || planName.toLowerCase().includes("free");

  // Calculate usage percentage
  const usagePercent = isUnlimited
    ? 0
    : Math.max(
        0,
        Math.min(
          100,
          ((creditsAllowed - creditsRemaining) / Math.max(creditsAllowed, 1)) *
            100,
        ),
      );
  const lowThreshold = Math.max(5, Math.ceil(creditsAllowed * 0.1));
  const isLowUsage = !isUnlimited && creditsRemaining <= lowThreshold;
  const isOutOfInterviews = !isUnlimited && creditsRemaining <= 0;

  // Format expiry date
  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div
      className={`${styles.banner} ${
        isFreeTier ? styles.freeTier : styles.paidTier
      } ${isLowUsage ? styles.lowUsage : ""} ${
        isOutOfInterviews ? styles.outOfInterviews : ""
      } ${compact ? styles.compact : ""}`}
    >
      <div className={styles.planInfo}>
        <div className={styles.planHeader}>
          <div className={styles.planBadge}>
            {isFreeTier ? (
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
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
            <span className={styles.planName}>{planName}</span>
          </div>
          {expiresAt && (
            <span className={styles.expiryDate}>
              Expires: {formatDate(expiresAt)}
            </span>
          )}
        </div>

        <div className={styles.usageSection}>
          <div className={styles.usageInfo}>
            <span className={styles.usageLabel}>Credits</span>
            <span className={styles.usageValue}>
              {isUnlimited ? (
                <>
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className={styles.infinityIcon}
                  >
                    <path d="M18.178 8c5.096 0 5.096 8 0 8-5.095 0-7.133-8-12.739-8-4.585 0-4.585 8 0 8 5.606 0 7.644-8 12.74-8z" />
                  </svg>
                  Unlimited
                </>
              ) : (
                <>
                  <strong>{creditsRemaining}</strong>
                  <span className={styles.usageDivider}>/</span>
                  {creditsAllowed}
                </>
              )}
            </span>
          </div>

          {!isUnlimited && (
            <div className={styles.progressBar}>
              <div
                className={styles.progressFill}
                style={{ width: `${100 - usagePercent}%` }}
              />
            </div>
          )}
        </div>
      </div>

      {(isFreeTier || isLowUsage) && (
        <div className={styles.ctaSection}>
          {isOutOfInterviews ? (
            <p className={styles.ctaText}>
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              You've used all credits. Upgrade to continue.
            </p>
          ) : isLowUsage ? (
            <p className={styles.ctaText}>
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              Running low on credits
            </p>
          ) : (
            <p className={styles.ctaText}>
              Unlock more usage credits with our Recruiter Max plan
            </p>
          )}
          <button className={styles.upgradeButton} onClick={onUpgrade}>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="12" y1="19" x2="12" y2="5" />
              <polyline points="5 12 12 5 19 12" />
            </svg>
            Upgrade Plan
          </button>
        </div>
      )}
    </div>
  );
};

export default SubscriptionBanner;

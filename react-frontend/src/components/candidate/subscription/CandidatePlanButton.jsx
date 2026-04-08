import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../recruiter/subscription/UpgradeButton.module.css";
import useCandidateSubscription from "./useCandidateSubscription";

const CandidatePlanButton = () => {
  const navigate = useNavigate();
  const {
    subscription,
    loading,
    isFreeTier,
    creditsRemaining,
    isLowUsage,
    isOutOfInterviews,
  } = useCandidateSubscription();

  const effectiveCreditsRemaining =
    isFreeTier && creditsRemaining <= 0
      ? Math.max(0, subscription?.plan?.monthly_credits ?? 250)
      : creditsRemaining;
  const isDepletedPaidPlan = isOutOfInterviews && !isFreeTier;

  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      console.log("[CandidatePlanButton] render-state", {
        loading,
        planName: subscription?.plan?.name,
        planSlug: subscription?.plan?.slug,
        monthlyCredits: subscription?.plan?.monthly_credits,
        creditsRemaining,
        effectiveCreditsRemaining,
        isFreeTier,
        isLowUsage,
        isOutOfInterviews,
        isDepletedPaidPlan,
      });
    }
  }, [
    loading,
    subscription,
    creditsRemaining,
    effectiveCreditsRemaining,
    isFreeTier,
    isLowUsage,
    isOutOfInterviews,
    isDepletedPaidPlan,
  ]);

  const handleClick = () => navigate("/candidate/subscription");

  const getButtonClass = () => {
    if (loading) return styles.loading;
    if (isDepletedPaidPlan) return styles.critical;
    if (isLowUsage) return styles.warning;
    if (isFreeTier) return styles.freeTier;
    return styles.paidTier;
  };

  const getStatusText = () => {
    if (loading) return "Loading...";
    if (isOutOfInterviews) return "No credits left";
    return `${interviewsRemaining} credits left`;
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

export default CandidatePlanButton;

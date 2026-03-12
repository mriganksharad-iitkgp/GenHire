import { useState, useEffect, useCallback } from "react";
import { getCurrentSubscription } from "../../../services/payment";

/**
 * useSubscription - Custom hook for managing subscription state
 * Provides subscription data, loading state, and refresh functionality
 *
 * @returns {Object} - { subscription, loading, error, refresh, isFreeTier, interviewsRemaining }
 */
const useSubscription = () => {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadSubscription = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const token = localStorage.getItem(
        process.env.REACT_APP_TOKEN_KEY || "companyxyz-token",
      );

      // Prefer recruiter cost-statistics plan data so navbar always matches dashboard credits
      if (token) {
        const costStatsRes = await fetch(
          `${process.env.REACT_APP_API_URL}/api/recruiter/cost-statistics?period=month`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          },
        );

        const costStatsData = await costStatsRes.json().catch(() => null);
        if (
          costStatsRes.ok &&
          costStatsData?.success &&
          costStatsData?.data?.plan
        ) {
          const plan = costStatsData.data.plan;
          const normalizedPlanName = plan?.name || "Free Tier";
          const isUnlimited = (plan?.interviews_allowed || 0) === -1;

          setSubscription({
            plan: {
              name: normalizedPlanName,
              slug: normalizedPlanName.toLowerCase().includes("free")
                ? "free"
                : "paid",
            },
            interviews_remaining: isUnlimited
              ? -1
              : Math.max(0, Number(plan?.interviews_remaining ?? 0)),
            interviews_allowed: isUnlimited
              ? -1
              : Number(plan?.interviews_allowed ?? 2),
            interviews_used: Number(plan?.interviews_used ?? 0),
            is_unlimited: isUnlimited,
            status: "active",
            expires_at: plan?.expires_at || null,
          });
          return;
        }
      }

      const response = await getCurrentSubscription();

      if (response?.data?.subscription) {
        setSubscription(response.data.subscription);
      } else if (response?.subscription) {
        setSubscription(response.subscription);
      } else {
        // Default to free tier if no subscription found
        setSubscription(getDefaultFreeTier());
      }
    } catch (err) {
      console.error("Error loading subscription:", err);
      setError(err.message || "Failed to load subscription");
      // Default to free tier on error
      setSubscription(getDefaultFreeTier());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSubscription();
  }, [loadSubscription]);

  // Helper to get default free tier
  const getDefaultFreeTier = () => ({
    plan: { name: "Free Tier", slug: "free" },
    interviews_remaining: 2,
    interviews_allowed: 2,
    interviews_used: 0,
    is_unlimited: false,
    status: "active",
  });

  // Computed properties
  const isFreeTier = !subscription || subscription?.plan?.slug === "free";
  const interviewsRemaining = subscription?.interviews_remaining ?? 2;
  const interviewsAllowed = subscription?.interviews_allowed ?? 2;
  const isLowUsage = !subscription?.is_unlimited && interviewsRemaining <= 2;
  const isOutOfInterviews =
    !subscription?.is_unlimited && interviewsRemaining <= 0;

  return {
    subscription,
    loading,
    error,
    refresh: loadSubscription,
    update: setSubscription,
    isFreeTier,
    interviewsRemaining,
    interviewsAllowed,
    isLowUsage,
    isOutOfInterviews,
  };
};

export default useSubscription;

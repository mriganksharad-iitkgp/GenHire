import { useState, useEffect, useCallback } from "react";
import { getCurrentSubscription } from "features/payment/api";

/**
 * useSubscription - Custom hook for managing subscription state
 * Provides subscription data, loading state, and refresh functionality
 *
 * @returns {Object} - { subscription, loading, error, refresh, isFreeTier, creditsRemaining }
 */
const useSubscription = () => {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadSubscription = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await getCurrentSubscription();
      const wallet = response?.data?.wallet || null;
      const subscriptionLike =
        response?.data?.subscription || response?.subscription || null;

      if (subscriptionLike || wallet) {
        setSubscription({
          ...(subscriptionLike || {}),
          plan: {
            name:
              subscriptionLike?.plan?.name ||
              wallet?.latest_recharge?.plan_name ||
              "Recharge Wallet",
            slug:
              subscriptionLike?.plan?.slug ||
              wallet?.latest_recharge?.plan_slug ||
              "wallet",
            monthly_credits:
              subscriptionLike?.plan?.monthly_credits ||
              wallet?.latest_recharge?.recharge_credits ||
              0,
          },
          credits_remaining: Number(
            subscriptionLike?.credits_remaining ?? wallet?.credits_balance ?? 0,
          ),
          credits_allocated: Number(
            subscriptionLike?.credits_allocated ?? wallet?.total_credited ?? 0,
          ),
          credits_used: Number(
            subscriptionLike?.credits_used ?? wallet?.total_debited ?? 0,
          ),
          interviews_remaining: Number(
            subscriptionLike?.interviews_remaining ??
              wallet?.credits_balance ??
              0,
          ),
          interviews_allowed: Number(
            subscriptionLike?.interviews_allowed ?? wallet?.total_credited ?? 0,
          ),
          interviews_used: Number(
            subscriptionLike?.interviews_used ?? wallet?.total_debited ?? 0,
          ),
          is_unlimited: false,
          status: "active",
          expires_at: null,
        });
      } else {
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
    plan: { name: "Recharge Wallet", slug: "wallet" },
    credits_remaining: 0,
    credits_allocated: 0,
    credits_used: 0,
    interviews_remaining: 0,
    interviews_allowed: 0,
    interviews_used: 0,
    is_unlimited: false,
    status: "active",
  });

  // Computed properties
  const isFreeTier = false;
  const creditsRemaining =
    subscription?.credits_remaining ?? subscription?.interviews_remaining ?? 2;
  const creditsAllowed =
    subscription?.credits_allocated ?? subscription?.interviews_allowed ?? 2;
  const interviewsRemaining = subscription?.interviews_remaining ?? 2;
  const interviewsAllowed = subscription?.interviews_allowed ?? 2;
  const isLowUsage =
    !subscription?.is_unlimited &&
    creditsRemaining <= Math.max(5, Math.ceil(creditsAllowed * 0.1));
  const isOutOfInterviews =
    !subscription?.is_unlimited && creditsRemaining <= 0;

  return {
    subscription,
    loading,
    error,
    refresh: loadSubscription,
    update: setSubscription,
    isFreeTier,
    creditsRemaining,
    creditsAllowed,
    interviewsRemaining,
    interviewsAllowed,
    isLowUsage,
    isOutOfInterviews,
  };
};

export default useSubscription;

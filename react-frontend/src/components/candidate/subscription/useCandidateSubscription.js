import { useState, useEffect, useCallback } from "react";
import { getCurrentSubscription } from "../../../services/payment";

const debugCandidateCredits = (...args) => {
  if (process.env.NODE_ENV !== "production") {
    console.log("[CandidateSubscription]", ...args);
  }
};

const getDefaultFreeTier = () => ({
  plan: { name: "Recharge Wallet", slug: "candidate-wallet" },
  credits_remaining: 0,
  credits_allocated: 0,
  credits_used: 0,
  monthly_credits: 0,
  is_unlimited: false,
  status: "active",
});

const normalizeCandidatePlan = (plan) => {
  const monthlyCredits = Number(
    plan?.monthly_credits ?? plan?.credits_allocated ?? 0,
  );
  const creditsUsed = Number(plan?.credits_used ?? 0);
  const rawRemaining = Number(
    plan?.credits_remaining ?? monthlyCredits - creditsUsed,
  );
  const isFreePlan = false;

  return {
    plan: {
      name: plan?.name || "Recharge Wallet",
      slug: String(plan?.slug || plan?.name || "candidate-wallet")
        .toLowerCase()
        .includes("candidate")
        ? String(plan?.slug || plan?.name || "")
            .toLowerCase()
            .replace(/\s+/g, "-")
        : "candidate-wallet",
      monthly_credits: monthlyCredits,
    },
    credits_remaining: Math.max(
      0,
      isFreePlan && creditsUsed === 0
        ? Math.max(monthlyCredits, rawRemaining)
        : rawRemaining,
    ),
    credits_allocated: monthlyCredits,
    credits_used: creditsUsed,
    is_unlimited: false,
    status: "active",
  };
};

const useCandidateSubscription = () => {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadSubscription = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await getCurrentSubscription();
      const wallet = response?.data?.wallet || null;
      const apiSub = response?.data?.subscription || response?.subscription;
      debugCandidateCredits("subscription:response", {
        hasSubscription: Boolean(apiSub),
        raw: apiSub || null,
      });

      if (apiSub || wallet) {
        const normalized = normalizeCandidatePlan({
          ...apiSub,
          name:
            apiSub?.plan?.name ||
            wallet?.latest_recharge?.plan_name ||
            "Recharge Wallet",
          slug:
            apiSub?.plan?.slug ||
            wallet?.latest_recharge?.plan_slug ||
            "candidate-wallet",
          monthly_credits:
            apiSub?.plan?.monthly_credits ||
            wallet?.latest_recharge?.recharge_credits ||
            0,
          credits_remaining:
            apiSub?.credits_remaining ?? wallet?.credits_balance ?? 0,
          credits_allocated:
            apiSub?.credits_allocated ?? wallet?.total_credited ?? 0,
          credits_used: apiSub?.credits_used ?? wallet?.total_debited ?? 0,
        });
        setSubscription(normalized);
      } else {
        debugCandidateCredits("fallback:defaultFreeTier");
        setSubscription(getDefaultFreeTier());
      }
    } catch (err) {
      debugCandidateCredits("loadSubscription:error", err);
      setError(err.message || "Failed to load candidate subscription");
      setSubscription(getDefaultFreeTier());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSubscription();
  }, [loadSubscription]);

  const creditsRemaining = subscription?.credits_remaining ?? 0;
  const creditsAllowed = subscription?.credits_allocated ?? 0;
  const monthlyCredits =
    subscription?.plan?.monthly_credits ??
    subscription?.credits_allocated ??
    subscription?.credits_remaining ??
    0;
  const isFreeTier =
    !subscription ||
    subscription?.plan?.slug === "candidate-wallet" ||
    String(subscription?.plan?.name || "")
      .toLowerCase()
      .includes("wallet");
  const isLowUsage =
    creditsRemaining <= Math.max(5, Math.ceil(creditsAllowed * 0.1));
  const isOutOfInterviews = creditsRemaining <= 0;

  useEffect(() => {
    debugCandidateCredits("resolved-state", {
      loading,
      error,
      plan: subscription?.plan || null,
      creditsRemaining,
      creditsAllowed,
      monthlyCredits,
      isFreeTier,
      isLowUsage,
      isOutOfInterviews,
    });
  }, [
    loading,
    error,
    subscription,
    creditsRemaining,
    creditsAllowed,
    monthlyCredits,
    isFreeTier,
    isLowUsage,
    isOutOfInterviews,
  ]);

  return {
    subscription,
    loading,
    error,
    refresh: loadSubscription,
    update: setSubscription,
    isFreeTier,
    creditsRemaining,
    creditsAllowed,
    monthlyCredits,
    isLowUsage,
    isOutOfInterviews,
  };
};

export default useCandidateSubscription;

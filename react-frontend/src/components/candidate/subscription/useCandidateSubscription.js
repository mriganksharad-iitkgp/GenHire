import { useState, useEffect, useCallback } from "react";
import { getCurrentSubscription } from "../../../services/payment";

const debugCandidateCredits = (...args) => {
  if (process.env.NODE_ENV !== "production") {
    console.log("[CandidateSubscription]", ...args);
  }
};

const getDefaultFreeTier = () => ({
  plan: { name: "Free Tier", slug: "candidate-free" },
  credits_remaining: 250,
  credits_allocated: 250,
  credits_used: 0,
  monthly_credits: 250,
  is_unlimited: false,
  status: "active",
});

const normalizeCandidatePlan = (plan) => {
  const monthlyCredits = Number(
    plan?.monthly_credits ?? plan?.credits_allocated ?? 250,
  );
  const creditsUsed = Number(plan?.credits_used ?? 0);
  const rawRemaining = Number(
    plan?.credits_remaining ?? monthlyCredits - creditsUsed,
  );
  const isFreePlan = String(plan?.name || "")
    .toLowerCase()
    .includes("free");

  return {
    plan: {
      name: plan?.name || "Free Tier",
      slug: String(plan?.name || "free")
        .toLowerCase()
        .includes("candidate")
        ? String(plan?.name || "")
            .toLowerCase()
            .replace(/\s+/g, "-")
        : "candidate-free",
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

      const token = localStorage.getItem(
        process.env.REACT_APP_TOKEN_KEY || "companyxyz-token",
      );
      debugCandidateCredits("loadSubscription:start", {
        hasToken: Boolean(token),
      });

      if (token) {
        const statsRes = await fetch(
          `${process.env.REACT_APP_API_URL}/api/candidate/cost-statistics`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          },
        );

        const statsData = await statsRes.json().catch(() => null);
        debugCandidateCredits("cost-statistics:response", {
          ok: statsRes.ok,
          status: statsRes.status,
          plan: statsData?.data?.plan || null,
        });

        if (statsRes.ok && statsData?.success && statsData?.data?.plan) {
          const normalized = normalizeCandidatePlan(statsData.data.plan);
          debugCandidateCredits("cost-statistics:normalized", normalized);
          setSubscription(normalized);
          return;
        }
      }

      const response = await getCurrentSubscription();
      const apiSub = response?.data?.subscription || response?.subscription;
      debugCandidateCredits("subscription:response", {
        hasSubscription: Boolean(apiSub),
        raw: apiSub || null,
      });

      if (apiSub?.plan?.slug?.startsWith("candidate-")) {
        setSubscription(apiSub);
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
    subscription?.plan?.slug === "candidate-free" ||
    String(subscription?.plan?.name || "")
      .toLowerCase()
      .includes("free");
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

import { useState, useEffect, useCallback } from "react";
import { getCurrentSubscription } from "../../../services/payment";

const getDefaultFreeTier = () => ({
  plan: { name: "Free Tier", slug: "candidate-free" },
  interviews_remaining: 2,
  interviews_allowed: 2,
  interviews_used: 0,
  is_unlimited: false,
  status: "active",
});

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
        if (statsRes.ok && statsData?.success && statsData?.data?.plan) {
          const plan = statsData.data.plan;
          setSubscription({
            plan: {
              name: plan.name || "Free Tier",
              slug: String(plan.name || "free")
                .toLowerCase()
                .includes("candidate")
                ? String(plan.name || "")
                    .toLowerCase()
                    .replace(/\s+/g, "-")
                : "candidate-free",
            },
            interviews_remaining: Math.max(
              0,
              Number(plan.interviews_remaining ?? 0),
            ),
            interviews_allowed: Number(plan.interviews_allowed ?? 2),
            interviews_used: Number(plan.interviews_used ?? 0),
            is_unlimited: false,
            status: "active",
          });
          return;
        }
      }

      const response = await getCurrentSubscription();
      const apiSub = response?.data?.subscription || response?.subscription;
      if (apiSub?.plan?.slug?.startsWith("candidate-")) {
        setSubscription(apiSub);
      } else {
        setSubscription(getDefaultFreeTier());
      }
    } catch (err) {
      setError(err.message || "Failed to load candidate subscription");
      setSubscription(getDefaultFreeTier());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSubscription();
  }, [loadSubscription]);

  const interviewsRemaining = subscription?.interviews_remaining ?? 2;
  const interviewsAllowed = subscription?.interviews_allowed ?? 2;
  const isFreeTier =
    !subscription ||
    subscription?.plan?.slug === "candidate-free" ||
    String(subscription?.plan?.name || "")
      .toLowerCase()
      .includes("free");
  const isLowUsage = interviewsRemaining <= 5;
  const isOutOfInterviews = interviewsRemaining <= 0;

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

export default useCandidateSubscription;

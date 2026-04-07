import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../../components/Navbar";
import styles from "../recruiter/RecruiterCostStatistics.module.css";
import {
  addMonths,
  buildContinuousMonthlySeries,
  clampMonthRange,
  getMaxMonthToAllowed,
} from "../../utils/monthRange";

const API_BASE_URL = process.env.REACT_APP_API_URL;

const CandidateCostStatistics = () => {
  const [loading, setLoading] = useState(true);
  const [costData, setCostData] = useState(null);
  const [error, setError] = useState(null);
  const [monthFrom, setMonthFrom] = useState("");
  const [monthTo, setMonthTo] = useState("");
  const navigate = useNavigate();

  const generateFallbackData = () => ({
    candidate: {
      name: "Candidate",
      email: "",
      joinedDate: new Date().toISOString().slice(0, 10),
    },
    plan: {
      name: "Free Tier",
      credits_allocated: 0,
      credits_remaining: 0,
      credits_used: 0,
      plan_credits_remaining: 0,
      free_credits_remaining: 0,
    },
    monthlyUsage: [],
    recentActivity: [],
    summary: {
      totalPracticeSessions: 0,
      completedPracticeSessions: 0,
      totalPracticeCreditsUsed: 0,
      avgInterviewScore: 0,
    },
  });

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const token = localStorage.getItem(
          process.env.REACT_APP_TOKEN_KEY || "companyxyz-token",
        );

        if (!token) {
          setError("Please login to view your usage dashboard");
          setLoading(false);
          return;
        }

        const response = await fetch(
          `${API_BASE_URL}/api/candidate/cost-statistics`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          },
        );

        const data = await response.json();
        if (data.success) {
          let mergedData = data.data;

          const hasExpiry = Boolean(data?.data?.plan?.expires_at);
          const isPaidPlan = !String(data?.data?.plan?.name || "")
            .toLowerCase()
            .includes("free");

          // Fallback: hydrate expires_at from active subscription endpoint when cost-stats payload misses it.
          if (!hasExpiry && isPaidPlan) {
            try {
              const subRes = await fetch(
                `${API_BASE_URL}/api/payment/subscriptions/me`,
                {
                  headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                  },
                },
              );
              const subData = await subRes.json().catch(() => null);
              const fallbackExpiry = subData?.data?.subscription?.expires_at;
              if (fallbackExpiry) {
                mergedData = {
                  ...data.data,
                  plan: {
                    ...(data.data?.plan || {}),
                    expires_at: fallbackExpiry,
                  },
                };
              }
            } catch (e) {
              // Keep original payload if fallback fetch fails.
            }
          }

          setCostData(mergedData);
        } else {
          setCostData(generateFallbackData());
        }
      } catch (err) {
        console.error("Error fetching candidate usage data:", err);
        setCostData(generateFallbackData());
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const safeData = costData || generateFallbackData();
  const plan = safeData.plan || {};

  const creditsAllocated = Number(plan.credits_allocated ?? 0) || 0;
  const creditsUsed = Number(plan.credits_used ?? 0) || 0;
  const creditsRemaining = Math.max(
    0,
    Number(plan.credits_remaining ?? 0) || 0,
  );
  const planCreditsRemaining = Math.max(
    0,
    Number(plan.plan_credits_remaining ?? 0) || 0,
  );
  const freeCreditsRemaining = Math.max(
    0,
    Number(plan.free_credits_remaining ?? 0) || 0,
  );
  const isFreeTier = String(plan.name || "")
    .toLowerCase()
    .includes("free");
  const planMonthlyCredits = !isFreeTier
    ? Math.max(0, Number(plan.plan_credits_allocated ?? 0))
    : creditsAllocated;
  const displayedMonthlyCredits = planMonthlyCredits;
  const usagePercentage =
    creditsAllocated > 0
      ? Math.min(100, Math.round((creditsUsed / creditsAllocated) * 100))
      : 0;
  const isNearLimit = usagePercentage >= 80;
  const expiresAt = plan.expires_at;
  const daysUntilExpiry = (() => {
    if (!expiresAt) return null;
    const expDate = new Date(expiresAt);
    const now = new Date();
    const diff = Math.ceil((expDate - now) / (1000 * 60 * 60 * 24));
    return diff > 0 ? diff : 0;
  })();

  const monthlySeries = useMemo(() => {
    const series = safeData.monthlyUsage || [];
    return [...series]
      .map((item) => ({
        month: item.month,
        credits_used: Number(item.credits_used || 0),
      }))
      .sort((a, b) => String(a.month).localeCompare(String(b.month)));
  }, [safeData.monthlyUsage]);

  const currentMonthKey = new Date().toISOString().slice(0, 7);

  const maxMonthToAllowed = useMemo(() => {
    return getMaxMonthToAllowed(monthFrom, currentMonthKey);
  }, [monthFrom, currentMonthKey]);

  const handleMonthFromChange = (nextFrom) => {
    setMonthFrom(nextFrom);

    if (!nextFrom) return;

    const autoTo = addMonths(nextFrom, 2);
    const cappedAutoTo = autoTo < currentMonthKey ? autoTo : currentMonthKey;
    setMonthTo(cappedAutoTo);
  };

  useEffect(() => {
    const defaultFrom = addMonths(currentMonthKey, -2);
    if (!monthFrom) setMonthFrom(defaultFrom);
    if (!monthTo) setMonthTo(currentMonthKey);
  }, [monthFrom, monthTo, currentMonthKey]);

  useEffect(() => {
    if (!monthFrom || !monthTo) return;

    const nextMonthTo = clampMonthRange(monthFrom, monthTo, currentMonthKey);
    if (nextMonthTo !== monthTo) {
      setMonthTo(nextMonthTo);
    }
  }, [monthFrom, monthTo, currentMonthKey]);

  const filteredMonthlySeries = useMemo(() => {
    const from = monthFrom || addMonths(currentMonthKey, -2);
    const to = monthTo || currentMonthKey;
    return buildContinuousMonthlySeries(monthlySeries, from, to);
  }, [monthlySeries, monthFrom, monthTo, currentMonthKey]);

  const maxMonthlyUsage = Math.max(
    ...filteredMonthlySeries.map((item) => item.credits_used),
    1,
  );

  const selectedRangeTotal = filteredMonthlySeries.reduce(
    (sum, item) => sum + item.credits_used,
    0,
  );

  const selectedRangeAvg = filteredMonthlySeries.length
    ? (selectedRangeTotal / filteredMonthlySeries.length).toFixed(1)
    : "0.0";

  const formatMonthLabel = (monthKey) => {
    const [year, month] = String(monthKey || currentMonthKey)
      .split("-")
      .map(Number);
    const date = new Date(year, (month || 1) - 1, 1);
    return date.toLocaleDateString("en-US", {
      month: "short",
      year: "2-digit",
    });
  };

  const circumference = 2 * Math.PI * 54;
  const ringOffset = circumference - (usagePercentage / 100) * circumference;

  if (loading) {
    return (
      <>
        <Navbar userType="candidate" />
        <div className={styles.pageWrapper}>
          <div className={styles.loadingContainer}>
            <div className={styles.loadingSpinner}></div>
            <p>Loading your practice usage dashboard...</p>
          </div>
        </div>
      </>
    );
  }

  if (error || !costData) {
    return (
      <>
        <Navbar userType="candidate" />
        <div className={styles.pageWrapper}>
          <div className={styles.errorContainer}>
            <p>{error || "Please login to view your usage dashboard"}</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar userType="candidate" />
      <div className={styles.pageWrapper}>
        <div className={styles.usageDashboard}>
          <div className={styles.pageHeader}>
            <div className={styles.headerContent}>
              <h1>Practice Cost Statistics</h1>
              <p>
                Welcome, {safeData.candidate?.name || "Candidate"} —{" "}
                {plan.name || "Free Tier"} Plan
              </p>
            </div>
          </div>

          <div className={styles.overviewCards}>
            <div className={styles.overviewCard}>
              <div
                className={styles.overviewIcon}
                style={{
                  background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                }}
              >
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="white"
                  strokeWidth="2"
                >
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>
                  Practice Credits Used
                </span>
                <span className={styles.overviewValue}>
                  {safeData.summary?.totalPracticeCreditsUsed || 0}
                </span>
              </div>
            </div>
            <div className={styles.overviewCard}>
              <div
                className={styles.overviewIcon}
                style={{
                  background: "linear-gradient(135deg, #10b981, #34d399)",
                }}
              >
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="white"
                  strokeWidth="2"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Completed</span>
                <span className={styles.overviewValue}>
                  {safeData.summary?.completedPracticeSessions || 0}
                </span>
              </div>
            </div>
            <div className={styles.overviewCard}>
              <div
                className={styles.overviewIcon}
                style={{
                  background: "linear-gradient(135deg, #f59e0b, #fbbf24)",
                }}
              >
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="white"
                  strokeWidth="2"
                >
                  <path d="M12 20h9" />
                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
                </svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>
                  Avg Interview Score
                </span>
                <span className={styles.overviewValue}>
                  {safeData.summary?.avgInterviewScore || 0}
                </span>
              </div>
            </div>
            <div className={styles.overviewCard}>
              <div
                className={styles.overviewIcon}
                style={{
                  background: "linear-gradient(135deg, #8b5cf6, #a78bfa)",
                }}
              >
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="white"
                  strokeWidth="2"
                >
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>
                  {daysUntilExpiry !== null ? "Expires In" : "Plan"}
                </span>
                <span className={styles.overviewValue}>
                  {daysUntilExpiry !== null
                    ? `${daysUntilExpiry} days`
                    : plan.name || "Free Tier"}
                </span>
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.interviewCreditsCard}>
              <div className={styles.creditsLeft}>
                <h2>Practice Credits</h2>
                <p className={styles.creditsSubtitle}>
                  {plan.name || "Free Tier"} —{" "}
                  {isFreeTier
                    ? `${creditsAllocated} free credits available`
                    : `${displayedMonthlyCredits} credits/month`}
                </p>

                <div className={styles.creditsNumbers}>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>
                      {creditsUsed}
                    </span>
                    <span className={styles.creditsStatLabel}>Used</span>
                  </div>
                  <div className={styles.creditsDivider}></div>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>
                      {creditsRemaining}
                    </span>
                    <span className={styles.creditsStatLabel}>Remaining</span>
                  </div>
                  <div className={styles.creditsDivider}></div>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>
                      {creditsAllocated}
                    </span>
                    <span className={styles.creditsStatLabel}>Total</span>
                  </div>
                </div>

                <div className={styles.creditBreakdownRow}>
                  <div className={styles.creditBreakdownItem}>
                    <span>Plan credits left</span>
                    <strong>{planCreditsRemaining}</strong>
                  </div>
                  <div className={styles.creditBreakdownItem}>
                    <span>Free credits left (lifetime)</span>
                    <strong>{freeCreditsRemaining}</strong>
                  </div>
                </div>

                {expiresAt && (
                  <div className={styles.renewalInfo}>
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                    Expires on{" "}
                    {new Date(expiresAt).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                    {daysUntilExpiry !== null && (
                      <span> ({daysUntilExpiry} days left)</span>
                    )}
                  </div>
                )}

                {isNearLimit && (
                  <div className={styles.upgradePrompt}>
                    <div className={styles.upgradeText}>
                      <strong>Running low on practice credits!</strong>
                      <p>
                        You've used {usagePercentage}% of{" "}
                        {isFreeTier
                          ? "your lifetime free credits"
                          : "your monthly credits"}
                        . Upgrade to continue.
                      </p>
                    </div>
                    <button
                      className={styles.upgradeBtn}
                      onClick={() => navigate("/candidate/subscription")}
                    >
                      Upgrade Plan
                    </button>
                  </div>
                )}
              </div>

              <div className={styles.creditsRight}>
                <div className={styles.ringContainer}>
                  <svg className={styles.ringChart} viewBox="0 0 120 120">
                    <circle
                      cx="60"
                      cy="60"
                      r="54"
                      fill="none"
                      stroke="#e2e8f0"
                      strokeWidth="12"
                    />
                    <circle
                      cx="60"
                      cy="60"
                      r="54"
                      fill="none"
                      stroke={
                        usagePercentage >= 90
                          ? "#ef4444"
                          : usagePercentage >= 70
                            ? "#f59e0b"
                            : "#6366f1"
                      }
                      strokeWidth="12"
                      strokeLinecap="round"
                      strokeDasharray={circumference}
                      strokeDashoffset={ringOffset}
                      transform="rotate(-90 60 60)"
                      style={{ transition: "stroke-dashoffset 1s ease" }}
                    />
                  </svg>
                  <div className={styles.ringCenter}>
                    <span className={styles.ringValue}>{creditsRemaining}</span>
                    <span className={styles.ringLabel}>remaining</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Monthly Credit Analytics</h2>
              <p>Select a month range to analyze your credit usage trend</p>
            </div>
            <div className={styles.trendCard}>
              <div className={styles.monthFiltersRow}>
                <div className={styles.monthFilterGroup}>
                  <label htmlFor="monthFrom">From</label>
                  <input
                    id="monthFrom"
                    type="month"
                    value={monthFrom}
                    onChange={(e) => handleMonthFromChange(e.target.value)}
                    max={currentMonthKey}
                  />
                </div>
                <div className={styles.monthFilterGroup}>
                  <label htmlFor="monthTo">To</label>
                  <input
                    id="monthTo"
                    type="month"
                    value={monthTo}
                    onChange={(e) => setMonthTo(e.target.value)}
                    min={monthFrom || undefined}
                    max={maxMonthToAllowed || undefined}
                  />
                </div>

                <div className={styles.rangeSummary}>
                  <div>
                    <span>Total</span>
                    <strong>{selectedRangeTotal} credits</strong>
                  </div>
                  <div>
                    <span>Avg / month</span>
                    <strong>{selectedRangeAvg} credits</strong>
                  </div>
                </div>
              </div>

              <div className={styles.barChart}>
                {filteredMonthlySeries.map((item, i) => {
                  const total = item.credits_used || 0;
                  const barHeight =
                    maxMonthlyUsage > 0 ? (total / maxMonthlyUsage) * 100 : 0;
                  return (
                    <div key={i} className={styles.barColumn}>
                      <div className={styles.barValue}>{total}</div>
                      <div className={styles.barTrack}>
                        <div
                          className={styles.barFill}
                          style={{ height: `${Math.max(barHeight, 4)}%` }}
                        ></div>
                      </div>
                      <div className={styles.barLabel}>
                        {formatMonthLabel(item.month)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.planInfoCard}>
              <div className={styles.planInfoLeft}>
                <div className={styles.planBadge}>
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                  </svg>
                  Current Plan: {plan.name || "Free Tier"}
                </div>
                <p className={styles.planDescription}>
                  Track your practice credit usage and upgrade anytime for more
                  credits.
                </p>
              </div>
              <button
                className={styles.managePlanBtn}
                onClick={() => navigate("/candidate/subscription")}
              >
                Upgrade Plan
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default CandidateCostStatistics;

import PortalPageHeader from "shared/components/ui/PortalPageHeader";
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "shared/components/layout/Navbar";
import styles from "features/recruiter/pages/RecruiterCostStatistics.module.css";
import { getToken } from "shared/utils/session";
import { request } from "shared/api/client";
import {
  addMonths,
  buildContinuousMonthlySeries,
  clampMonthRange,
  getMaxMonthToAllowed,
} from "shared/utils/monthRange";


const CandidateCostStatistics = () => {
  const [loading, setLoading] = useState(true);
  const [costData, setCostData] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [monthFrom, setMonthFrom] = useState("");
  const [monthTo, setMonthTo] = useState("");
  const navigate = useNavigate();

  const emptyUsageModel = () => ({
    candidate: {
      name: "Candidate",
      email: "",
      joinedDate: new Date().toISOString().slice(0, 10),
    },
    plan: {
      name: "Candidate Wallet",
      credits_allocated: 0,
      credits_remaining: 0,
      credits_used: 0,
      plan_credits_remaining: 0,
      free_credits_remaining: 0,
    },
    monthlyUsage: [],
    recentActivity: [],
    rechargeHistory: [],
    summary: {
      totalPracticeSessions: 0,
      completedPracticeSessions: 0,
      totalPracticeCreditsUsed: 0,
      avgInterviewScore: 0,
    },
  });

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const token = getToken();
        if (!token) {
          setError("Please login to view your usage dashboard");
          setLoading(false);
          return;
        }

        const data = await request("/candidate/cost-statistics", { signal:controller.signal });
        if (cancelled) return;
        if (!data?.success || !data.data || typeof data.data !== "object" || Array.isArray(data.data)) {
          throw new Error("Usage data is unavailable.");
        }
        setCostData(data.data);
      } catch (err) {
        if (cancelled) return;
        setError(err.status === 401 ? "Your session has expired. Please sign in again." : controller.signal.aborted ? "Loading your usage data took too long. Please retry." : "We could not load your usage data. Please retry.");
      } finally {
        clearTimeout(timeout);
        if (!cancelled) setLoading(false);
      }
    };

    fetchData();
    return () => { cancelled = true; clearTimeout(timeout); controller.abort(); };
  }, [attempt]);

  const safeData = costData || emptyUsageModel();
  const plan = safeData.plan || {};

  const creditsAllocated = Number(plan.credits_allocated ?? 0) || 0;
  const creditsUsed = Number(plan.credits_used ?? 0) || 0;
  const creditsRemaining = Math.max(
    0,
    Number(plan.credits_remaining ?? 0) || 0,
  );
  const signupBonusCredits = Number(plan.signup_bonus_credits ?? 100);
  const signupBonusGranted = Boolean(plan.signup_bonus_granted);
  const planCreditsRemaining = Math.max(
    0,
    Number(plan.plan_credits_remaining ?? 0) || 0,
  );
  const planMonthlyCredits = Math.max(0, Number(plan.plan_credits_allocated ?? creditsAllocated ?? 0));
  const displayedMonthlyCredits = planMonthlyCredits;
  const usagePercentage =
    creditsAllocated > 0
      ? Math.min(100, Math.round((creditsUsed / creditsAllocated) * 100))
      : 0;
  const isNearLimit = usagePercentage >= 80;

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
    return date.toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata",
      month: "short",
      year: "2-digit",
    });
  };

  const circumference = 2 * Math.PI * 54;
  const ringOffset = circumference - (usagePercentage / 100) * circumference;
  const activityRows = useMemo(() => {
    return (safeData?.recentActivity || []).filter((row) => {
      const txType = String(row?.transaction_type || "");
      const delta = Number(row?.delta_credits || 0);
      return txType === "practice_interview" && delta < 0;
    });
  }, [safeData?.recentActivity]);
  const rechargeRows = useMemo(
    () => safeData?.rechargeHistory || [],
    [safeData?.rechargeHistory],
  );

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
          <section className={styles.errorContainer} role="alert"><h2>Unable to load usage</h2><p>{error || "Please sign in to view your usage dashboard."}</p>{getToken() ? <button onClick={() => setAttempt(value => value + 1)}>Retry</button> : <button onClick={() => navigate("/login")}>Sign in</button>}</section>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar userType="candidate" />
      <div className={styles.pageWrapper}>
        <div className={styles.usageDashboard}>
          <PortalPageHeader title="Cost statistics" eyebrow="Your candidate wallet" icon="fa-line-chart" subtitle="Track your practice credits, wallet balance and usage over time." />

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
                  Signup Bonus
                </span>
                <span className={styles.overviewValue}>
                  {signupBonusGranted
                    ? `${signupBonusCredits} credits`
                    : "Pending"}
                </span>
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.interviewCreditsCard}>
              <div className={styles.creditsLeft}>
                <h2>Practice Credits</h2>
                <p className={styles.creditsSubtitle}>
                  {plan.name || "Candidate Wallet"} - {displayedMonthlyCredits.toLocaleString("en-IN")} total credits allocated, non-expiring
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
                    <span>Wallet balance</span>
                    <strong>{planCreditsRemaining}</strong>
                  </div>
                  <div className={styles.creditBreakdownItem}>
                    <span>Signup bonus</span>
                    <strong>{signupBonusGranted ? signupBonusCredits : 0}</strong>
                  </div>
                </div>

                <div className={styles.renewalInfo}>Credits are non-expiring in wallet mode.</div>

                {isNearLimit && (
                  <div className={styles.upgradePrompt}>
                    <div className={styles.upgradeText}>
                      <strong>Running low on practice credits!</strong>
                      <p>
                        Your wallet is getting low. Recharge to continue practice sessions.
                      </p>
                    </div>
                    <button
                      className={styles.upgradeBtn}
                      onClick={() => navigate("/candidate/subscription")}
                    >
                      Recharge Wallet
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
            <div className={styles.sectionHeader}>
              <h2>Recent Credit Activity</h2>
              <p>Real wallet transactions only. No synthetic or estimated rows.</p>
            </div>
            <div className={styles.activityTableSection}>
              {activityRows && activityRows.length > 0 ? (
                <table className={styles.activityTable}>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Activity Type</th>
                      <th>Credits Deducted</th>
                      <th>Remaining Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activityRows.map((activity) => (
                      <tr key={activity.id}>
                        <td className={styles.activityTimestamp}>
                          {activity.timestamp}
                        </td>
                        <td className={styles.activityAction}>
                          {activity.activity_type || activity.action}
                        </td>
                        <td className={styles.creditCost}>
                          {activity.credits_deducted ??
                            Math.abs(Number(activity.delta_credits || 0))}
                        </td>
                        <td className={styles.creditCost}>
                          {activity.remaining_balance ?? activity.balance_after ?? 0}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className={styles.emptyState}>
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2m0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8m.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z" />
                  </svg>
                  <p>
                    No wallet transactions yet. Recharge or use practice to see activity.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Recharge History</h2>
              <p>Wallet credit additions, including migration recharges.</p>
            </div>
            <div className={styles.activityTableSection}>
              {rechargeRows && rechargeRows.length > 0 ? (
                <table className={styles.activityTable}>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Type</th>
                      <th>Credits Added</th>
                      <th>Balance After</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rechargeRows.map((activity) => (
                      <tr key={activity.id}>
                        <td className={styles.activityTimestamp}>
                          {activity.timestamp}
                        </td>
                        <td className={styles.activityAction}>
                          {activity.activity_type || activity.action}
                        </td>
                        <td className={styles.creditCost}>
                          {activity.credits_added ?? Number(activity.delta_credits || 0)}
                        </td>
                        <td className={styles.creditCost}>
                          {activity.remaining_balance ?? activity.balance_after ?? 0}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className={styles.emptyState}>
                  <p>No recharges yet.</p>
                </div>
              )}
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
                  Current Wallet: {plan.name || "Candidate Wallet"}
                </div>
                <p className={styles.planDescription}>
                  Recharge packs are non-expiring. Practice interview deductions are fixed and visible in this activity feed.
                </p>
              </div>
              <button
                className={styles.managePlanBtn}
                onClick={() => navigate("/candidate/subscription")}
              >
                Recharge Wallet
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

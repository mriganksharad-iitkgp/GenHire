import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "shared/components/layout/Navbar";
import styles from "./RecruiterCostStatistics.module.css";
import { getToken } from "shared/utils/session";
import { authedFetch } from "shared/api/client";
import {
  addMonths,
  buildContinuousMonthlySeries,
  clampMonthRange,
  getMaxMonthToAllowed,
} from "shared/utils/monthRange";

const API_BASE_URL = process.env.REACT_APP_API_URL;

const RecruiterCostStatistics = () => {
  const [loading, setLoading] = useState(true);
  const [costData, setCostData] = useState(null);
  const [error, setError] = useState(null);
  const [monthFrom, setMonthFrom] = useState("");
  const [monthTo, setMonthTo] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
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

        const response = await authedFetch(
          `${API_BASE_URL}/api/recruiter/cost-statistics?period=month`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          },
        );

        const data = await response.json();

        if (data.success) {
          setCostData(data.data);
        } else {
          setCostData(generateFallbackData());
        }
      } catch (err) {
        if (err.status !== 401) {
          setCostData(generateFallbackData());
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const generateFallbackData = () => {
    const today = new Date();

    return {
      recruiter: {
        name: "New Recruiter",
        email: "",
        company: "Your Company",
        joinedDate: today.toISOString().split("T")[0],
      },
      plan: {
        name: "Recruiter Wallet",
        interviews_allowed: 0,
        interviews_remaining: 0,
        interviews_used: 0,
        credits_allocated: 0,
        credits_remaining: 0,
        credits_used: 0,
        expires_at: null,
      },
      usageHistory: [],
      recentActivity: [],
      rechargeHistory: [],
      summary: {
        totalJobs: 0,
        totalApplicants: 0,
        totalInterviews: 0,
        activeJobs: 0,
      },
      monthlyPipeline: [],
    };
  };

  const safeCostData = costData || generateFallbackData();

  // Plan & interview data
  const plan = safeCostData.plan || {};
  const interviewsAllowed = Number(
    plan.credits_allocated ?? plan.interviews_allowed ?? 0,
  );
  const interviewsUsed = Number(plan.credits_used ?? plan.interviews_used ?? 0);
  const interviewsRemaining = Math.max(
    0,
    Number(plan.credits_remaining ?? plan.interviews_remaining ?? 0),
  );
  const signupBonusCredits = Number(plan.signup_bonus_credits ?? 100);
  const signupBonusGranted = Boolean(plan.signup_bonus_granted);
  const planCreditsRemaining = interviewsRemaining;
  const planName = plan.name || "Recruiter Wallet";
  const displayedMonthlyInterviews = interviewsAllowed;
  const usagePercentage =
    interviewsAllowed > 0
      ? Math.min(100, Math.round((interviewsUsed / interviewsAllowed) * 100))
      : 0;
  const isNearLimit = interviewsAllowed > 0 && interviewsRemaining <= Math.max(100, Math.ceil(interviewsAllowed * 0.1));


  // Usage history (source data)
  const usageHistory = useMemo(
    () => costData?.usageHistory || [],
    [costData?.usageHistory],
  );
  const currentMonthKey = new Date().toISOString().slice(0, 7);

  const monthlySeries = useMemo(() => {
    const monthlyMap = new Map();

    usageHistory.forEach((entry) => {
      const monthKey = String(entry?.month || "").slice(0, 7);
      if (!monthKey) return;
      const current = monthlyMap.get(monthKey) || 0;
      monthlyMap.set(monthKey, current + Number(entry.interviews || 0));
    });

    return Array.from(monthlyMap.entries())
      .map(([month, interviews]) => ({ month, interviews }))
      .sort((a, b) => a.month.localeCompare(b.month));
  }, [usageHistory]);

  useEffect(() => {
    if (!monthlySeries.length) return;

    const firstMonth = monthlySeries[0].month;
    const defaultTo =
      addMonths(firstMonth, 2) < currentMonthKey
        ? addMonths(firstMonth, 2)
        : currentMonthKey;

    if (!monthFrom) setMonthFrom(firstMonth);
    if (!monthTo) setMonthTo(defaultTo);
  }, [monthlySeries, monthFrom, monthTo, currentMonthKey]);

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
    if (!monthFrom || !monthTo) return;

    const nextMonthTo = clampMonthRange(monthFrom, monthTo, currentMonthKey);
    if (nextMonthTo !== monthTo) {
      setMonthTo(nextMonthTo);
    }
  }, [monthFrom, monthTo, currentMonthKey]);

  const filteredMonthlySeries = useMemo(() => {
    if (!monthlySeries.length) return [];

    const from = monthFrom || monthlySeries[0].month;
    const to = monthTo || monthlySeries[monthlySeries.length - 1].month;
    return buildContinuousMonthlySeries(monthlySeries, from, to);
  }, [monthlySeries, monthFrom, monthTo]);

  const maxMonthlyUsage = Math.max(
    ...filteredMonthlySeries.map((item) => item.interviews),
    1,
  );

  const selectedRangeTotal = filteredMonthlySeries.reduce(
    (sum, item) => sum + item.interviews,
    0,
  );

  const selectedRangeAvg = filteredMonthlySeries.length
    ? (selectedRangeTotal / filteredMonthlySeries.length).toFixed(1)
    : "0.0";

  const formatMonthLabel = (monthKey) => {
    const [year, month] = monthKey.split("-").map(Number);
    const date = new Date(year, month - 1, 1);
    return date.toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata",
      month: "short",
      year: "2-digit",
    });
  };

  const activityRows = useMemo(() => {
    return (costData?.recentActivity || []).filter((row) => {
      const txType = String(row?.transaction_type || "");
      const delta = Number(row?.delta_credits || 0);
      return (
        (txType === "ai_jd_generation" ||
          txType === "real_interview_recruiter") &&
        delta < 0
      );
    });
  }, [costData?.recentActivity]);
  const rechargeRows = useMemo(
    () => costData?.rechargeHistory || [],
    [costData?.rechargeHistory],
  );

  if (loading) {
    return (
      <>
        <Navbar userType="recruiter" />
        <div className={styles.pageWrapper}>
          <div className={styles.loadingContainer}>
            <div className={styles.loadingSpinner}></div>
            <p>Loading your usage dashboard...</p>
          </div>
        </div>
      </>
    );
  }

  if (error || !costData) {
    return (
      <>
        <Navbar userType="recruiter" />
        <div className={styles.pageWrapper}>
          <div className={styles.errorContainer}>
            <p>{error || "Please login to view your usage dashboard"}</p>
          </div>
        </div>
      </>
    );
  }

  // Interview usage ring
  const circumference = 2 * Math.PI * 54;
  const ringOffset = circumference - (usagePercentage / 100) * circumference;

  return (
    <>
      <Navbar userType="recruiter" />
      <div className={styles.pageWrapper}>
        <div className={styles.usageDashboard}>
          {/* Page Header */}
          <div className={styles.pageHeader}>
            <div className={styles.headerContent}>
              <h1>Usage Dashboard</h1>
              <p>
                Welcome, {costData.recruiter?.name || "Recruiter"} - {planName}
              </p>
            </div>
          </div>

          {/* Overview Cards */}
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
                  <rect x="2" y="3" width="20" height="14" rx="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Active Jobs</span>
                <span className={styles.overviewValue}>
                  {costData.summary?.activeJobs || 0}
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
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Total Applicants</span>
                <span className={styles.overviewValue}>
                  {costData.summary?.totalApplicants || 0}
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
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>
                  Interviews (Last Month)
                </span>
                <span className={styles.overviewValue}>
                  {costData.summary?.totalInterviews || 0}
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

          {/* Interview Credits Section */}
          <div className={styles.section}>
            <div className={styles.interviewCreditsCard}>
              <div className={styles.creditsLeft}>
                <h2>Wallet Credits</h2>
                <p className={styles.creditsSubtitle}>
                  {planName} - {displayedMonthlyInterviews.toLocaleString("en-IN")} total credits allocated, non-expiring
                </p>

                <div className={styles.creditsNumbers}>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>
                      {interviewsUsed}
                    </span>
                    <span className={styles.creditsStatLabel}>Used</span>
                  </div>
                  <div className={styles.creditsDivider}></div>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>
                      {interviewsRemaining}
                    </span>
                    <span className={styles.creditsStatLabel}>Remaining</span>
                  </div>
                  <div className={styles.creditsDivider}></div>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>
                      {interviewsAllowed}
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
                      <strong>Running low on interview credits!</strong>
                      <p>
                        Your wallet is getting low. Recharge now to continue AI JD generation and real interviews.
                      </p>
                    </div>
                    <button
                      className={styles.upgradeBtn}
                      onClick={() => navigate("/recruiter/subscription")}
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
                    <>
                      <span className={styles.ringValue}>{interviewsRemaining}</span>
                      <span className={styles.ringLabel}>remaining</span>
                    </>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Activity Table */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Recent Credit Activity</h2>
              <p>
                Real wallet transactions only. No synthetic or estimated rows.
              </p>
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
                    No wallet transactions yet. Recharge or use interviews to see activity.
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

          {/* Monthly Interview Analytics */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Monthly Credit Analytics</h2>
              <p>Select a month range to analyze credit debits and trend</p>
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
                    <strong>{selectedRangeTotal}</strong>
                  </div>
                  <div>
                    <span>Avg / month</span>
                    <strong>{selectedRangeAvg}</strong>
                  </div>
                </div>
              </div>

              <div className={styles.barChart}>
                {filteredMonthlySeries.map((item, i) => {
                  const total = item.interviews || 0;
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

          {/* Plan Info + Upgrade CTA */}
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
                  Current Wallet: {planName}
                </div>
                <p className={styles.planDescription}>
                  Recharge packs are non-expiring. Credits are deducted at fixed rates for AI JD generation and real interviews.
                </p>
              </div>
              <button
                className={styles.managePlanBtn}
                onClick={() => navigate("/recruiter/subscription")}
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

export default RecruiterCostStatistics;

import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../../components/Navbar";
import styles from "../recruiter/RecruiterCostStatistics.module.css";

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
      interviews_allowed: 2,
      interviews_remaining: 2,
      interviews_used: 0,
      plan_interviews_remaining: 0,
      free_interviews_remaining: 2,
    },
    monthlyUsage: [],
    recentActivity: [],
    summary: {
      totalPracticeInterviews: 0,
      completedPracticeInterviews: 0,
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
          setCostData(data.data);
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

  const interviewsAllowed = plan.interviews_allowed || 2;
  const interviewsUsed = plan.interviews_used || 0;
  const interviewsRemaining = Math.max(0, plan.interviews_remaining ?? 2);
  const planCreditsRemaining = Math.max(0, plan.plan_interviews_remaining ?? 0);
  const freeCreditsRemaining = Math.max(0, plan.free_interviews_remaining ?? 0);
  const usagePercentage =
    interviewsAllowed > 0
      ? Math.min(100, Math.round((interviewsUsed / interviewsAllowed) * 100))
      : 0;
  const isNearLimit = usagePercentage >= 80;

  const monthlySeries = useMemo(() => {
    const series = safeData.monthlyUsage || [];
    return [...series]
      .map((item) => ({ month: item.month, interviews: Number(item.interviews || 0) }))
      .sort((a, b) => String(a.month).localeCompare(String(b.month)));
  }, [safeData.monthlyUsage]);

  const currentMonthKey = new Date().toISOString().slice(0, 7);

  useEffect(() => {
    if (!monthlySeries.length) {
      setMonthFrom(currentMonthKey);
      setMonthTo(currentMonthKey);
      return;
    }

    if (!monthFrom) setMonthFrom(monthlySeries[0].month);
    if (!monthTo) setMonthTo(monthlySeries[monthlySeries.length - 1].month);
  }, [monthlySeries, monthFrom, monthTo, currentMonthKey]);

  const filteredMonthlySeries = useMemo(() => {
    if (!monthlySeries.length) return [{ month: currentMonthKey, interviews: interviewsUsed }];
    return monthlySeries.filter(
      (item) => item.month >= (monthFrom || item.month) && item.month <= (monthTo || item.month),
    );
  }, [monthlySeries, monthFrom, monthTo, currentMonthKey, interviewsUsed]);

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
    const [year, month] = String(monthKey || currentMonthKey).split("-").map(Number);
    const date = new Date(year, (month || 1) - 1, 1);
    return date.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
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
                Welcome, {safeData.candidate?.name || "Candidate"} — {plan.name || "Free Tier"} Plan
              </p>
            </div>
          </div>

          <div className={styles.overviewCards}>
            <div className={styles.overviewCard}>
              <div className={styles.overviewIcon} style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Practice Interviews</span>
                <span className={styles.overviewValue}>{safeData.summary?.totalPracticeInterviews || 0}</span>
              </div>
            </div>
            <div className={styles.overviewCard}>
              <div className={styles.overviewIcon} style={{ background: "linear-gradient(135deg, #10b981, #34d399)" }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Completed</span>
                <span className={styles.overviewValue}>{safeData.summary?.completedPracticeInterviews || 0}</span>
              </div>
            </div>
            <div className={styles.overviewCard}>
              <div className={styles.overviewIcon} style={{ background: "linear-gradient(135deg, #f59e0b, #fbbf24)" }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Avg Interview Score</span>
                <span className={styles.overviewValue}>{safeData.summary?.avgInterviewScore || 0}</span>
              </div>
            </div>
            <div className={styles.overviewCard}>
              <div className={styles.overviewIcon} style={{ background: "linear-gradient(135deg, #8b5cf6, #a78bfa)" }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Plan</span>
                <span className={styles.overviewValue}>{plan.name || "Free Tier"}</span>
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.interviewCreditsCard}>
              <div className={styles.creditsLeft}>
                <h2>Practice Credits</h2>
                <p className={styles.creditsSubtitle}>{plan.name || "Free Tier"} — {interviewsAllowed} practice interviews/month</p>

                <div className={styles.creditsNumbers}>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>{interviewsUsed}</span>
                    <span className={styles.creditsStatLabel}>Used</span>
                  </div>
                  <div className={styles.creditsDivider}></div>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>{interviewsRemaining}</span>
                    <span className={styles.creditsStatLabel}>Remaining</span>
                  </div>
                  <div className={styles.creditsDivider}></div>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>{interviewsAllowed}</span>
                    <span className={styles.creditsStatLabel}>Total</span>
                  </div>
                </div>

                <div className={styles.creditBreakdownRow}>
                  <div className={styles.creditBreakdownItem}>
                    <span>Plan credits left</span>
                    <strong>{planCreditsRemaining}</strong>
                  </div>
                  <div className={styles.creditBreakdownItem}>
                    <span>Free credits left (this month)</span>
                    <strong>{freeCreditsRemaining}</strong>
                  </div>
                </div>

                {isNearLimit && (
                  <div className={styles.upgradePrompt}>
                    <div className={styles.upgradeText}>
                      <strong>Running low on practice credits!</strong>
                      <p>You've used {usagePercentage}% of your monthly practice interviews. Upgrade to continue.</p>
                    </div>
                    <button className={styles.upgradeBtn} onClick={() => navigate("/candidate/subscription")}>
                      Upgrade Plan
                    </button>
                  </div>
                )}
              </div>

              <div className={styles.creditsRight}>
                <div className={styles.ringContainer}>
                  <svg className={styles.ringChart} viewBox="0 0 120 120">
                    <circle cx="60" cy="60" r="54" fill="none" stroke="#e2e8f0" strokeWidth="12" />
                    <circle
                      cx="60"
                      cy="60"
                      r="54"
                      fill="none"
                      stroke={usagePercentage >= 90 ? "#ef4444" : usagePercentage >= 70 ? "#f59e0b" : "#6366f1"}
                      strokeWidth="12"
                      strokeLinecap="round"
                      strokeDasharray={circumference}
                      strokeDashoffset={ringOffset}
                      transform="rotate(-90 60 60)"
                      style={{ transition: "stroke-dashoffset 1s ease" }}
                    />
                  </svg>
                  <div className={styles.ringCenter}>
                    <span className={styles.ringValue}>{interviewsRemaining}</span>
                    <span className={styles.ringLabel}>remaining</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Monthly Practice Analytics</h2>
              <p>Select a month range to analyze your practice trend</p>
            </div>
            <div className={styles.trendCard}>
              <div className={styles.monthFiltersRow}>
                <div className={styles.monthFilterGroup}>
                  <label htmlFor="monthFrom">From</label>
                  <input
                    id="monthFrom"
                    type="month"
                    value={monthFrom}
                    onChange={(e) => setMonthFrom(e.target.value)}
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
                    max={currentMonthKey}
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
                  const barHeight = maxMonthlyUsage > 0 ? (total / maxMonthlyUsage) * 100 : 0;
                  return (
                    <div key={i} className={styles.barColumn}>
                      <div className={styles.barValue}>{total}</div>
                      <div className={styles.barTrack}>
                        <div
                          className={styles.barFill}
                          style={{ height: `${Math.max(barHeight, 4)}%` }}
                        ></div>
                      </div>
                      <div className={styles.barLabel}>{formatMonthLabel(item.month)}</div>
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
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                  Current Plan: {plan.name || "Free Tier"}
                </div>
                <p className={styles.planDescription}>
                  Track your monthly practice interview usage and upgrade anytime for more interview attempts.
                </p>
              </div>
              <button className={styles.managePlanBtn} onClick={() => navigate("/candidate/subscription")}>
                Upgrade Plan
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default CandidateCostStatistics;

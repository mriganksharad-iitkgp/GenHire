import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../../components/Navbar";
import styles from "./RecruiterCostStatistics.module.css";

const API_BASE_URL = process.env.REACT_APP_API_URL;

const RecruiterCostStatistics = () => {
  const [loading, setLoading] = useState(true);
  const [costData, setCostData] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const token = localStorage.getItem(process.env.REACT_APP_TOKEN_KEY || "token");
        if (!token) {
          setError("Please login to view your usage dashboard");
          setLoading(false);
          return;
        }

        const response = await fetch(
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
        console.error("Error fetching usage data:", err);
        setCostData(generateFallbackData());
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const generateFallbackData = () => {
    const today = new Date();
    const weekAgo = (weeksBack) => {
      const date = new Date(today);
      date.setDate(date.getDate() - weeksBack * 7);
      return date.toISOString().split("T")[0];
    };

    return {
      recruiter: {
        name: "New Recruiter",
        email: "",
        company: "Your Company",
        joinedDate: today.toISOString().split("T")[0],
      },
      plan: {
        name: "Free Tier",
        interviews_allowed: 2,
        interviews_remaining: 2,
        interviews_used: 0,
        expires_at: null,
      },
      usageHistory: [
        { date: weekAgo(5), week: "Week 1", interviews: 0 },
        { date: weekAgo(4), week: "Week 2", interviews: 0 },
        { date: weekAgo(3), week: "Week 3", interviews: 0 },
        { date: weekAgo(2), week: "Week 4", interviews: 0 },
        { date: weekAgo(1), week: "Week 5", interviews: 0 },
        { date: weekAgo(0), week: "Week 6", interviews: 0 },
      ],
      recentActivity: [],
      summary: {
        totalJobs: 0,
        totalApplicants: 0,
        totalInterviews: 0,
        activeJobs: 0,
      },
    };
  };

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

  // Plan & interview data
  const plan = costData.plan || {};
  const interviewsAllowed = plan.interviews_allowed || 2;
  const interviewsUsed = plan.interviews_used || 0;
  const interviewsRemaining = Math.max(0, plan.interviews_remaining ?? 2);
  const isUnlimited = interviewsAllowed === -1;
  const usagePercentage = isUnlimited ? 0 : (interviewsAllowed > 0 ? Math.min(100, Math.round((interviewsUsed / interviewsAllowed) * 100)) : 0);
  const isNearLimit = !isUnlimited && usagePercentage >= 80;
  const planName = plan.name || "Free Tier";
  const expiresAt = plan.expires_at;

  // Calculate days until renewal
  const daysUntilRenewal = (() => {
    if (!expiresAt) return null;
    const expDate = new Date(expiresAt);
    const now = new Date();
    const diff = Math.ceil((expDate - now) / (1000 * 60 * 60 * 24));
    return diff > 0 ? diff : 0;
  })();

  // Usage history for the bar chart
  const usageHistory = costData.usageHistory || [];
  const maxWeeklyUsage = Math.max(
    ...usageHistory.map(w => w.interviews || 0),
    1
  );

  // Interview usage ring
  const circumference = 2 * Math.PI * 54;
  const ringOffset = isUnlimited ? 0 : circumference - (usagePercentage / 100) * circumference;

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
                Welcome, {costData.recruiter?.name || "Recruiter"} — {planName} Plan
              </p>
            </div>
          </div>

          {/* Overview Cards */}
          <div className={styles.overviewCards}>
            <div className={styles.overviewCard}>
              <div className={styles.overviewIcon} style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Active Jobs</span>
                <span className={styles.overviewValue}>{costData.summary?.activeJobs || 0}</span>
              </div>
            </div>
            <div className={styles.overviewCard}>
              <div className={styles.overviewIcon} style={{ background: 'linear-gradient(135deg, #10b981, #34d399)' }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Total Applicants</span>
                <span className={styles.overviewValue}>{costData.summary?.totalApplicants || 0}</span>
              </div>
            </div>
            <div className={styles.overviewCard}>
              <div className={styles.overviewIcon} style={{ background: 'linear-gradient(135deg, #f59e0b, #fbbf24)' }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>Interviews (Last Month)</span>
                <span className={styles.overviewValue}>{costData.summary?.totalInterviews || 0}</span>
              </div>
            </div>
            <div className={styles.overviewCard}>
              <div className={styles.overviewIcon} style={{ background: 'linear-gradient(135deg, #8b5cf6, #a78bfa)' }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              </div>
              <div className={styles.overviewInfo}>
                <span className={styles.overviewLabel}>{daysUntilRenewal !== null ? 'Renewal In' : 'Plan'}</span>
                <span className={styles.overviewValue}>{daysUntilRenewal !== null ? `${daysUntilRenewal} days` : planName}</span>
              </div>
            </div>
          </div>

          {/* Interview Credits Section */}
          <div className={styles.section}>
            <div className={styles.interviewCreditsCard}>
              <div className={styles.creditsLeft}>
                <h2>Interview Credits</h2>
                <p className={styles.creditsSubtitle}>{planName} — {isUnlimited ? 'Unlimited interviews' : `${interviewsAllowed} interviews/month`}</p>
                
                <div className={styles.creditsNumbers}>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>{interviewsUsed}</span>
                    <span className={styles.creditsStatLabel}>Used</span>
                  </div>
                  <div className={styles.creditsDivider}></div>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>{isUnlimited ? '∞' : interviewsRemaining}</span>
                    <span className={styles.creditsStatLabel}>Remaining</span>
                  </div>
                  <div className={styles.creditsDivider}></div>
                  <div className={styles.creditsStat}>
                    <span className={styles.creditsStatValue}>{isUnlimited ? '∞' : interviewsAllowed}</span>
                    <span className={styles.creditsStatLabel}>Total</span>
                  </div>
                </div>

                {expiresAt && (
                  <div className={styles.renewalInfo}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    Renews on {new Date(expiresAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                    {daysUntilRenewal !== null && <span> ({daysUntilRenewal} days left)</span>}
                  </div>
                )}

                {isNearLimit && (
                  <div className={styles.upgradePrompt}>
                    <div className={styles.upgradeText}>
                      <strong>Running low on interview credits!</strong>
                      <p>You've used {usagePercentage}% of your monthly interviews. Upgrade to get more.</p>
                    </div>
                    <button
                      className={styles.upgradeBtn}
                      onClick={() => navigate("/recruiter/subscription")}
                    >
                      Upgrade Plan
                    </button>
                  </div>
                )}
              </div>

              <div className={styles.creditsRight}>
                <div className={styles.ringContainer}>
                  <svg className={styles.ringChart} viewBox="0 0 120 120">
                    <circle cx="60" cy="60" r="54" fill="none" stroke="#e2e8f0" strokeWidth="12" />
                    {!isUnlimited && (
                      <circle
                        cx="60" cy="60" r="54" fill="none"
                        stroke={usagePercentage >= 90 ? '#ef4444' : usagePercentage >= 70 ? '#f59e0b' : '#6366f1'}
                        strokeWidth="12"
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={ringOffset}
                        transform="rotate(-90 60 60)"
                        style={{ transition: 'stroke-dashoffset 1s ease' }}
                      />
                    )}
                  </svg>
                  <div className={styles.ringCenter}>
                    {isUnlimited ? (
                      <>
                        <span className={styles.ringValue}>∞</span>
                        <span className={styles.ringLabel}>Unlimited</span>
                      </>
                    ) : (
                      <>
                        <span className={styles.ringValue}>{interviewsRemaining}</span>
                        <span className={styles.ringLabel}>remaining</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Weekly Usage Trend */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Weekly Interview Trend</h2>
              <p>Your interview activity over the past 6 weeks</p>
            </div>
            <div className={styles.trendCard}>
              <div className={styles.barChart}>
                {usageHistory.map((week, i) => {
                  const total = week.interviews || 0;
                  const barHeight = maxWeeklyUsage > 0 ? (total / maxWeeklyUsage) * 100 : 0;
                  return (
                    <div key={i} className={styles.barColumn}>
                      <div className={styles.barValue}>{total}</div>
                      <div className={styles.barTrack}>
                        <div
                          className={styles.barFill}
                          style={{ height: `${Math.max(barHeight, 4)}%` }}
                        ></div>
                      </div>
                      <div className={styles.barLabel}>{week.week}</div>
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
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                  Current Plan: {planName}
                </div>
                <p className={styles.planDescription}>
                  {planName === 'Free Tier'
                    ? 'Get started with 2 interviews. Upgrade to unlock more interviews and advanced features.'
                    : planName.includes('Pro')
                      ? 'You have 100 interviews per month with advanced analytics and priority support.'
                      : planName.includes('Enterprise')
                        ? 'Unlimited interviews with custom integrations, dedicated support, and SLA guarantee.'
                        : 'Manage your subscription to get the most out of SmartHire.'}
                </p>
              </div>
              <button
                className={styles.managePlanBtn}
                onClick={() => navigate("/recruiter/subscription")}
              >
                {planName === 'Free Tier' || planName.includes('Pro') ? 'Upgrade Plan' : 'Manage Plan'}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default RecruiterCostStatistics;

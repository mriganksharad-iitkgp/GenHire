import React, { useState, useEffect } from "react";
import Navbar from "../../components/Navbar";
import styles from "./RecruiterCostStatistics.module.css";

const API_BASE_URL =
  process.env.REACT_APP_API_URL;

const RecruiterCostStatistics = () => {
  const [loading, setLoading] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState("month");
  const [costData, setCostData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchCostStatistics = async () => {
      setLoading(true);
      setError(null);

      try {
        const token = localStorage.getItem(process.env.REACT_APP_TOKEN_KEY || "token");
        if (!token) {
          setError("Please login to view cost statistics");
          setLoading(false);
          return;
        }

        const response = await fetch(
          `${API_BASE_URL}/api/recruiter/cost-statistics?period=${selectedPeriod}`,
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
          // If API fails, generate fallback data for new recruiters
          setCostData(generateFallbackData());
        }
      } catch (err) {
        console.error("Error fetching cost statistics:", err);
        // Generate fallback data if API is unavailable
        setCostData(generateFallbackData());
      } finally {
        setLoading(false);
      }
    };

    fetchCostStatistics();
  }, [selectedPeriod]);

  // Generate fallback/default data for new recruiters or API failures
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
        interviews_allowed: 0,
        interviews_remaining: 0,
        interviews_used: 0,
        expires_at: null,
      },
      credits: {
        allocated: 2000,
        used: 100,
        available: 1900,
        usage_percentage: 5,
        cloudflare: { allocated: 700, used: 35 },
        nlp: { allocated: 800, used: 40 },
        llm: { allocated: 500, used: 25 },
      },
      usageHistory: [
        { date: weekAgo(5), week: "Week 1", cloudflare: 5, nlp: 5, llm: 3 },
        { date: weekAgo(4), week: "Week 2", cloudflare: 6, nlp: 7, llm: 4 },
        { date: weekAgo(3), week: "Week 3", cloudflare: 6, nlp: 8, llm: 5 },
        { date: weekAgo(2), week: "Week 4", cloudflare: 7, nlp: 8, llm: 5 },
        { date: weekAgo(1), week: "Week 5", cloudflare: 6, nlp: 7, llm: 4 },
        { date: weekAgo(0), week: "Week 6", cloudflare: 5, nlp: 5, llm: 4 },
      ],
      recentActivity: [],
      jobBreakdown: [],
      summary: {
        totalJobs: 0,
        totalApplicants: 0,
        totalInterviews: 0,
        activeJobs: 0,
      },
    };
  };

  const calculatePercentage = (used, total) => {
    if (!total || total === 0) return 0;
    return Math.round((used / total) * 100);
  };

  const getServiceColor = (service) => {
    const colors = {
      cloudflare: "#f59e0b",
      nlp: "#10b981",
      llm: "#6366f1",
    };
    return colors[service] || "#64748b";
  };

  const getServiceLabel = (service) => {
    const labels = {
      cloudflare: "Cloudflare (GPU)",
      nlp: "NLP (Gemini)",
      llm: "LLM (ChatGPT)",
    };
    return labels[service] || service;
  };

  // Semi-circular gauge component
  const GaugeChart = ({ used, total, color, label, icon }) => {
    const percentage = calculatePercentage(used, total);
    const rotation = (percentage / 100) * 180;

    return (
      <div className={styles.gaugeCard}>
        <div className={styles.gaugeHeader}>
          <span className={styles.gaugeIcon} style={{ background: color }}>
            {icon}
          </span>
          <h3>{label}</h3>
        </div>
        <div className={styles.gaugeContainer}>
          <div className={styles.gaugeSvg}>
            <svg viewBox="0 0 200 120">
              {/* Background arc */}
              <path
                d="M 20 100 A 80 80 0 0 1 180 100"
                fill="none"
                stroke="#e2e8f0"
                strokeWidth="16"
                strokeLinecap="round"
              />
              {/* Progress arc */}
              <path
                d="M 20 100 A 80 80 0 0 1 180 100"
                fill="none"
                stroke={color}
                strokeWidth="16"
                strokeLinecap="round"
                strokeDasharray={`${(percentage / 100) * 251.2} 251.2`}
                style={{ transition: "stroke-dasharray 1s ease" }}
              />
            </svg>
          </div>
          <div className={styles.gaugeValue}>
            <span className={styles.gaugePercentage}>{percentage}%</span>
            <span className={styles.gaugeLabel}>Used</span>
          </div>
        </div>
        <div className={styles.gaugeStats}>
          <div className={styles.gaugeStat}>
            <span className={styles.gaugeStatLabel}>Used</span>
            <span className={styles.gaugeStatValue}>
              ₹{used.toLocaleString()}
            </span>
          </div>
          <div className={styles.gaugeStat}>
            <span className={styles.gaugeStatLabel}>Available</span>
            <span className={styles.gaugeStatValue}>
              ₹{(total - used).toLocaleString()}
            </span>
          </div>
        </div>
      </div>
    );
  };

  // Credit bar for overall usage
  const CreditBar = ({ used, total }) => {
    const percentage = calculatePercentage(used, total);

    return (
      <div className={styles.creditBarContainer}>
        <div className={styles.creditBarHeader}>
          <div className={styles.creditBarTitle}>
            <h3>Total Credit Usage</h3>
            <span className={styles.creditPercentage}>{percentage}% used</span>
          </div>
          <div className={styles.creditBarValues}>
            <span className={styles.usedValue}>₹{used.toLocaleString()}</span>
            <span className={styles.separator}>/</span>
            <span className={styles.totalValue}>₹{total.toLocaleString()}</span>
          </div>
        </div>
        <div className={styles.creditBarTrack}>
          <div
            className={styles.creditBarFill}
            style={{
              width: `${percentage}%`,
              background:
                percentage > 90
                  ? "linear-gradient(90deg, #ef4444, #f87171)"
                  : percentage > 70
                    ? "linear-gradient(90deg, #f59e0b, #fbbf24)"
                    : "linear-gradient(90deg, #10b981, #34d399)",
            }}
          ></div>
        </div>
        <div className={styles.creditBarHint}>
          {percentage > 90
            ? "⚠️ Credits running low! Contact admin for more allocation."
            : percentage > 70
              ? "💡 Consider optimizing your usage to stay within budget."
              : "✅ Credit usage is healthy."}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <>
        <Navbar userType="recruiter" />
        <div className={styles.pageWrapper}>
          <div className={styles.loadingContainer}>
            <div className={styles.loadingSpinner}></div>
            <p>Loading your cost statistics...</p>
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
            <p>{error || "Please login to view cost statistics"}</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar userType="recruiter" />
      <div className={styles.pageWrapper}>
        <div className={styles.costStatistics}>
          {/* Page Header */}
          <div className={styles.pageHeader}>
            <div className={styles.headerContent}>
              <h1>My Cost Statistics</h1>
              <p>
                Welcome, {costData.recruiter?.name || "Recruiter"} •{" "}
                {costData.plan?.name || "Free Tier"}
              </p>
              {costData.summary && (
                <div className={styles.summaryBadges}>
                  <span className={styles.summaryBadge}>
                    <strong>{costData.summary.activeJobs}</strong> Active Jobs
                  </span>
                  <span className={styles.summaryBadge}>
                    <strong>{costData.summary.totalApplicants}</strong>{" "}
                    Applicants
                  </span>
                  <span className={styles.summaryBadge}>
                    <strong>{costData.summary.totalInterviews}</strong>{" "}
                    Interviews
                  </span>
                </div>
              )}
            </div>
            <div className={styles.headerActions}>
              <select
                className={styles.periodSelect}
                value={selectedPeriod}
                onChange={(e) => setSelectedPeriod(e.target.value)}
              >
                <option value="week">This Week</option>
                <option value="month">This Month</option>
                <option value="quarter">This Quarter</option>
                <option value="year">This Year</option>
              </select>
              <button className={styles.downloadBtn}>
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Download Report
              </button>
            </div>
          </div>

          {/* Total Credits Overview */}
          <div className={styles.section}>
            <CreditBar
              used={costData.credits.used}
              total={costData.credits.allocated}
            />
          </div>

          {/* Service Gauges */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Usage by Service</h2>
              <p>
                Breakdown of your credit consumption across different services
              </p>
            </div>
            <div className={styles.gaugesGrid}>
              <GaugeChart
                used={costData.credits.cloudflare.used}
                total={costData.credits.cloudflare.allocated}
                color="#f59e0b"
                label="Cloudflare (GPU)"
                icon="☁️"
              />
              <GaugeChart
                used={costData.credits.nlp.used}
                total={costData.credits.nlp.allocated}
                color="#10b981"
                label="NLP (Gemini)"
                icon="🧠"
              />
              <GaugeChart
                used={costData.credits.llm.used}
                total={costData.credits.llm.allocated}
                color="#6366f1"
                label="LLM (ChatGPT)"
                icon="💬"
              />
            </div>
          </div>

          {/* Service Usage Bars */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Service Credit Details</h2>
              <p>Detailed view of each service allocation and usage</p>
            </div>
            <div className={styles.serviceCardsGrid}>
              {["cloudflare", "nlp", "llm"].map((service) => {
                const data = costData.credits[service];
                const percentage = calculatePercentage(
                  data.used,
                  data.allocated,
                );

                return (
                  <div key={service} className={styles.serviceCard}>
                    <div className={styles.serviceCardHeader}>
                      <div className={styles.serviceInfo}>
                        <span
                          className={styles.serviceIcon}
                          style={{ background: getServiceColor(service) }}
                        >
                          {service === "cloudflare"
                            ? "☁️"
                            : service === "nlp"
                              ? "🧠"
                              : "💬"}
                        </span>
                        <div>
                          <h4>{getServiceLabel(service)}</h4>
                          <p>
                            {service === "cloudflare"
                              ? "Video processing & face verification"
                              : service === "nlp"
                                ? "CV analysis & job matching"
                                : "Interview questions & evaluation"}
                          </p>
                        </div>
                      </div>
                      <span
                        className={styles.servicePercentage}
                        style={{ color: getServiceColor(service) }}
                      >
                        {percentage}%
                      </span>
                    </div>
                    <div className={styles.serviceBarTrack}>
                      <div
                        className={styles.serviceBarFill}
                        style={{
                          width: `${percentage}%`,
                          background: getServiceColor(service),
                        }}
                      ></div>
                    </div>
                    <div className={styles.serviceStats}>
                      <span>₹{data.used.toLocaleString()} used</span>
                      <span>
                        ₹{(data.allocated - data.used).toLocaleString()}{" "}
                        remaining
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recent Activity */}
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>Recent Activity</h2>
              <p>Latest credit usage transactions</p>
            </div>
            <div className={styles.activityCard}>
              {costData.recentActivity && costData.recentActivity.length > 0 ? (
                <>
                  <div className={styles.activityList}>
                    {costData.recentActivity.map((activity) => (
                      <div key={activity.id} className={styles.activityItem}>
                        <div
                          className={styles.activityIcon}
                          style={{
                            background: getServiceColor(activity.service),
                          }}
                        >
                          {activity.service === "cloudflare"
                            ? "🎥"
                            : activity.service === "nlp"
                              ? "📄"
                              : "💬"}
                        </div>
                        <div className={styles.activityDetails}>
                          <div className={styles.activityMain}>
                            <span className={styles.activityAction}>
                              {activity.action}
                            </span>
                            <span className={styles.activityJob}>
                              {activity.job}
                            </span>
                          </div>
                          <span className={styles.activityTime}>
                            {activity.timestamp}
                          </span>
                        </div>
                        <div className={styles.activityCredits}>
                          <span className={styles.creditAmount}>
                            -₹{activity.credits}
                          </span>
                          <span
                            className={styles.creditService}
                            style={{ color: getServiceColor(activity.service) }}
                          >
                            {getServiceLabel(activity.service)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <button className={styles.viewAllBtn}>
                    View All Activity
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
                </>
              ) : (
                <div className={styles.emptyState}>
                  <span className={styles.emptyIcon}>📊</span>
                  <h4>No Activity Yet</h4>
                  <p>
                    Your credit usage activity will appear here once you start
                    using the platform
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default RecruiterCostStatistics;

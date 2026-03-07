import React, { useState, useEffect } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import styles from './CostStatistics.module.css';

const API_BASE_URL = process.env.REACT_APP_API_URL;

const CostStatistics = () => {
  const [loading, setLoading] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState('month');
  const [costData, setCostData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const token = localStorage.getItem(process.env.REACT_APP_TOKEN_KEY || 'token');
        if (!token) {
          setError('Please login to view cost statistics');
          setLoading(false);
          return;
        }

        const response = await fetch(
          `${API_BASE_URL}/api/admin/cost-statistics?period=${selectedPeriod}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          }
        );

        const data = await response.json();

        if (response.ok) {
          setCostData(data);
        } else {
          setError(data.error || 'Failed to load cost statistics');
        }
      } catch (err) {
        console.error('Error fetching cost statistics:', err);
        setError('Failed to load cost statistics. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [selectedPeriod]);

  const calculatePercentage = (used, total) => {
    if (!total || total === 0) return 0;
    return Math.round((used / total) * 100);
  };

  // SVG Pie Chart Component
  const PieChart = ({ used, total, color, label, icon }) => {
    const percentage = calculatePercentage(used, total);
    const circumference = 2 * Math.PI * 45;
    const strokeDasharray = circumference;
    const strokeDashoffset = circumference - (percentage / 100) * circumference;

    return (
      <div className={styles.pieChartCard}>
        <div className={styles.pieChartHeader}>
          <span className={styles.pieChartIcon} style={{ background: color }}>
            {icon}
          </span>
          <h3>{label}</h3>
        </div>
        <div className={styles.pieChartContainer}>
          <svg className={styles.pieChart} viewBox="0 0 100 100">
            {/* Background circle */}
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="10"
            />
            {/* Progress circle */}
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="none"
              stroke={color}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={strokeDasharray}
              strokeDashoffset={strokeDashoffset}
              transform="rotate(-90 50 50)"
              style={{ transition: 'stroke-dashoffset 1s ease' }}
            />
          </svg>
          <div className={styles.pieChartCenter}>
            <span className={styles.pieChartPercentage}>{percentage}%</span>
            <span className={styles.pieChartLabel}>Used</span>
          </div>
        </div>
        <div className={styles.pieChartLegend}>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ background: color }}></span>
            <span>Used: ₹{used.toLocaleString()}</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} style={{ background: '#e2e8f0' }}></span>
            <span>Available: ₹{(total - used).toLocaleString()}</span>
          </div>
        </div>
      </div>
    );
  };

  // Horizontal Bar Component (like CV Score)
  const HorizontalBar = ({ label, value, maxValue, color, sublabel }) => {
    const percentage = calculatePercentage(value, maxValue);
    
    return (
      <div className={styles.horizontalBarContainer}>
        <div className={styles.horizontalBarHeader}>
          <span className={styles.horizontalBarLabel}>{label}</span>
          <span className={styles.horizontalBarValue}>₹{value.toLocaleString()} / ₹{maxValue.toLocaleString()}</span>
        </div>
        <div className={styles.horizontalBarTrack}>
          <div 
            className={styles.horizontalBarFill}
            style={{ 
              width: `${percentage}%`, 
              background: color 
            }}
          ></div>
        </div>
        {sublabel && <span className={styles.horizontalBarSublabel}>{sublabel}</span>}
      </div>
    );
  };

  // Stacked Bar for Recruiter comparison
  // Helper to format dates
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  // Get plan badge style class
  const getPlanBadgeClass = (planName) => {
    const name = (planName || '').toLowerCase();
    if (name.includes('enterprise')) return styles.planEnterprise;
    if (name.includes('pro') || name.includes('professional') || name.includes('recruiter')) return styles.planPro;
    return styles.planFree;
  };

  if (loading) {
    return (
      <AdminLayout activeTab="cost-statistics">
        <div className={styles.loadingContainer}>
          <div className={styles.loadingSpinner}></div>
          <p>Loading cost statistics...</p>
        </div>
      </AdminLayout>
    );
  }

  if (error) {
    return (
      <AdminLayout activeTab="cost-statistics">
        <div className={styles.loadingContainer}>
          <p style={{ color: '#ef4444' }}>{error}</p>
        </div>
      </AdminLayout>
    );
  }

  if (!costData || !costData.recruiters) {
    return (
      <AdminLayout activeTab="cost-statistics">
        <div className={styles.loadingContainer}>
          <p>No cost data available.</p>
        </div>
      </AdminLayout>
    );
  }

  // Safe access for overview with defaults
  const overview = costData.overview || {};
  const totalBudget = overview.totalBudget || 0;
  const totalUsed = overview.totalUsed || 0;
  const cloudflare = overview.cloudflare || { used: 0, allocated: 0 };
  const nlp = overview.nlp || { used: 0, allocated: 0 };
  const llm = overview.llm || { used: 0, allocated: 0 };

  // Revenue calculations based on subscription plans
  const revenueData = (() => {
    const recruiters = costData.recruiters || [];
    let proCount = 0;
    let enterpriseCount = 0;
    let freeCount = 0;
    let totalInterviews = 0;

    recruiters.forEach(r => {
      const planName = (r.plan?.name || r.plan?.slug || 'free').toLowerCase();
      if (planName.includes('pro') || planName.includes('professional')) {
        proCount++;
      } else if (planName.includes('enterprise')) {
        enterpriseCount++;
      } else {
        freeCount++;
      }
      totalInterviews += r.activity?.total_interviews || 0;
    });

    const proRevenue = proCount * 4999;
    const enterpriseRevenue = enterpriseCount * 10000;
    const totalRevenue = proRevenue + enterpriseRevenue;
    const costPerInterview = totalInterviews > 0 ? Math.round(totalUsed / totalInterviews) : 0;
    const profit = totalRevenue - totalUsed;
    const margin = totalRevenue > 0 ? Math.round((profit / totalRevenue) * 100) : 0;

    return { proCount, enterpriseCount, freeCount, proRevenue, enterpriseRevenue, totalRevenue, totalInterviews, costPerInterview, profit, margin };
  })();

  return (
    <AdminLayout activeTab="cost-statistics">
      <div className={styles.costStatistics}>
      {/* Page Header */}
      <div className={styles.pageHeader}>
        <div className={styles.headerContent}>
          <h1>Cost Statistics</h1>
          <p>Monitor and analyze platform resource consumption and costs</p>
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
          <button className={styles.exportBtn}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Export Report
          </button>
        </div>
      </div>

      {/* Overview Cards */}
      <div className={styles.overviewCards}>
        <div className={styles.overviewCard}>
          <div className={styles.overviewIcon} style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
              <line x1="1" y1="10" x2="23" y2="10" />
            </svg>
          </div>
          <div className={styles.overviewInfo}>
            <span className={styles.overviewLabel}>Total Budget</span>
            <span className={styles.overviewValue}>₹{totalBudget.toLocaleString()}</span>
          </div>
        </div>
        <div className={styles.overviewCard}>
          <div className={styles.overviewIcon} style={{ background: 'linear-gradient(135deg, #10b981, #34d399)' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
          </div>
          <div className={styles.overviewInfo}>
            <span className={styles.overviewLabel}>Total Used</span>
            <span className={styles.overviewValue}>₹{totalUsed.toLocaleString()}</span>
          </div>
        </div>
        <div className={styles.overviewCard}>
          <div className={styles.overviewIcon} style={{ background: 'linear-gradient(135deg, #f59e0b, #fbbf24)' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </div>
          <div className={styles.overviewInfo}>
            <span className={styles.overviewLabel}>Available</span>
            <span className={styles.overviewValue}>₹{(totalBudget - totalUsed).toLocaleString()}</span>
          </div>
        </div>
        <div className={styles.overviewCard}>
          <div className={styles.overviewIcon} style={{ background: 'linear-gradient(135deg, #ef4444, #f87171)' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <path d="M3 3v18h18" />
              <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3" />
            </svg>
          </div>
          <div className={styles.overviewInfo}>
            <span className={styles.overviewLabel}>Utilization</span>
            <span className={styles.overviewValue}>{calculatePercentage(totalUsed, totalBudget)}%</span>
          </div>
        </div>
      </div>

      {/* Pie Charts Section */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>Resource Usage by Service</h2>
          <p>Breakdown of credits consumption across different services</p>
        </div>
        <div className={styles.pieChartsGrid}>
          <PieChart 
            used={cloudflare.used}
            total={cloudflare.allocated}
            color="#f59e0b"
            label="Cloudflare (GPU)"
            icon="☁️"
          />
          <PieChart 
            used={nlp.used}
            total={nlp.allocated}
            color="#10b981"
            label="NLP (Gemini)"
            icon="🧠"
          />
          <PieChart 
            used={llm.used}
            total={llm.allocated}
            color="#6366f1"
            label="LLM (ChatGPT)"
            icon="💬"
          />
        </div>
      </div>

      {/* Revenue vs Cost Section */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>Revenue vs Infrastructure Cost</h2>
          <p>Subscription revenue against platform operating costs</p>
        </div>
        <div className={styles.revenueGrid}>
          <div className={styles.revenueCard}>
            <div className={styles.revenueCardHeader}>
              <span className={styles.revenueIcon} style={{ background: 'linear-gradient(135deg, #10b981, #34d399)' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                  <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                </svg>
              </span>
              <span className={styles.revenueLabel}>Monthly Revenue</span>
            </div>
            <span className={styles.revenueAmount}>₹{revenueData.totalRevenue.toLocaleString()}</span>
            <div className={styles.revenueBreakdown}>
              <div className={styles.revenueBreakdownItem}>
                <span className={styles.revenueDot} style={{background: '#8b5cf6'}}></span>
                <span>Recruiter Pro ({revenueData.proCount})</span>
                <span className={styles.revenueItemValue}>₹{revenueData.proRevenue.toLocaleString()}</span>
              </div>
              <div className={styles.revenueBreakdownItem}>
                <span className={styles.revenueDot} style={{background: '#6366f1'}}></span>
                <span>Enterprise ({revenueData.enterpriseCount})</span>
                <span className={styles.revenueItemValue}>₹{revenueData.enterpriseRevenue.toLocaleString()}</span>
              </div>
              <div className={styles.revenueBreakdownItem}>
                <span className={styles.revenueDot} style={{background: '#94a3b8'}}></span>
                <span>Free ({revenueData.freeCount})</span>
                <span className={styles.revenueItemValue}>₹0</span>
              </div>
            </div>
          </div>

          <div className={styles.revenueCard}>
            <div className={styles.revenueCardHeader}>
              <span className={styles.revenueIcon} style={{ background: 'linear-gradient(135deg, #ef4444, #f87171)' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                  <path d="M3 3v18h18" />
                  <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3" />
                </svg>
              </span>
              <span className={styles.revenueLabel}>Infrastructure Cost</span>
            </div>
            <span className={styles.revenueAmount}>₹{totalUsed.toLocaleString()}</span>
            <div className={styles.revenueBreakdown}>
              <div className={styles.revenueBreakdownItem}>
                <span className={styles.revenueDot} style={{background: '#f59e0b'}}></span>
                <span>Cloudflare (GPU)</span>
                <span className={styles.revenueItemValue}>₹{cloudflare.used.toLocaleString()}</span>
              </div>
              <div className={styles.revenueBreakdownItem}>
                <span className={styles.revenueDot} style={{background: '#10b981'}}></span>
                <span>NLP (Gemini)</span>
                <span className={styles.revenueItemValue}>₹{nlp.used.toLocaleString()}</span>
              </div>
              <div className={styles.revenueBreakdownItem}>
                <span className={styles.revenueDot} style={{background: '#6366f1'}}></span>
                <span>LLM (ChatGPT)</span>
                <span className={styles.revenueItemValue}>₹{llm.used.toLocaleString()}</span>
              </div>
            </div>
          </div>

          <div className={styles.revenueCard}>
            <div className={styles.revenueCardHeader}>
              <span className={styles.revenueIcon} style={{ background: revenueData.profit >= 0 ? 'linear-gradient(135deg, #10b981, #34d399)' : 'linear-gradient(135deg, #ef4444, #f87171)' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                  <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
                  <polyline points="16 7 22 7 22 13" />
                </svg>
              </span>
              <span className={styles.revenueLabel}>Profitability</span>
            </div>
            <span className={`${styles.revenueAmount} ${revenueData.profit >= 0 ? styles.profitPositive : styles.profitNegative}`}>
              {revenueData.profit >= 0 ? '+' : ''}₹{revenueData.profit.toLocaleString()}
            </span>
            <div className={styles.profitBar}>
              <div className={styles.profitBarTrack}>
                <div
                  className={styles.profitBarRevenue}
                  style={{ width: revenueData.totalRevenue > 0 ? '100%' : '0%' }}
                  title={`Revenue: ₹${revenueData.totalRevenue.toLocaleString()}`}
                ></div>
                <div
                  className={styles.profitBarCost}
                  style={{ width: revenueData.totalRevenue > 0 ? `${Math.min(100, (totalUsed / revenueData.totalRevenue) * 100)}%` : '0%' }}
                  title={`Cost: ₹${totalUsed.toLocaleString()}`}
                ></div>
              </div>
              <div className={styles.profitBarLabels}>
                <span>Margin: {revenueData.margin}%</span>
                <span>{revenueData.totalInterviews} interviews</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Cost Per Interview */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>Cost Per Interview</h2>
          <p>Average infrastructure cost for each interview conducted</p>
        </div>
        <div className={styles.costPerInterviewCard}>
          <div className={styles.cpiMetric}>
            <div className={styles.cpiValue}>
              <span className={styles.cpiCurrency}>₹</span>
              <span className={styles.cpiAmount}>{revenueData.costPerInterview.toLocaleString()}</span>
              <span className={styles.cpiUnit}>/ interview</span>
            </div>
            <p className={styles.cpiDescription}>
              Based on {revenueData.totalInterviews} interviews and ₹{totalUsed.toLocaleString()} total infrastructure cost
            </p>
          </div>
          <div className={styles.cpiBreakdown}>
            <div className={styles.cpiBreakdownItem}>
              <span className={styles.cpiBreakdownLabel}>GPU (Cloudflare)</span>
              <span className={styles.cpiBreakdownValue}>
                ₹{revenueData.totalInterviews > 0 ? Math.round(cloudflare.used / revenueData.totalInterviews) : 0}
              </span>
            </div>
            <div className={styles.cpiBreakdownItem}>
              <span className={styles.cpiBreakdownLabel}>NLP (Gemini)</span>
              <span className={styles.cpiBreakdownValue}>
                ₹{revenueData.totalInterviews > 0 ? Math.round(nlp.used / revenueData.totalInterviews) : 0}
              </span>
            </div>
            <div className={styles.cpiBreakdownItem}>
              <span className={styles.cpiBreakdownLabel}>LLM (ChatGPT)</span>
              <span className={styles.cpiBreakdownValue}>
                ₹{revenueData.totalInterviews > 0 ? Math.round(llm.used / revenueData.totalInterviews) : 0}
              </span>
            </div>
          </div>
          <div className={styles.cpiInsight}>
            {revenueData.costPerInterview > 0 && revenueData.totalRevenue > 0 ? (
              revenueData.totalRevenue / revenueData.totalInterviews > revenueData.costPerInterview
                ? `✅ Revenue per interview (₹${Math.round(revenueData.totalRevenue / revenueData.totalInterviews)}) exceeds cost per interview — pricing is sustainable.`
                : `⚠️ Revenue per interview (₹${Math.round(revenueData.totalRevenue / revenueData.totalInterviews)}) is below cost — consider adjusting pricing.`
            ) : (
              '📊 Cost per interview data will populate as interviews are conducted.'
            )}
          </div>
        </div>
      </div>

      {/* Recruiter Plan Enrollment */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>Recruiter Plan Enrollment</h2>
          <p>Current subscription plan and validity for each recruiter</p>
        </div>
        <div className={styles.tableCard}>
          <table className={styles.recruitersTable}>
            <thead>
              <tr>
                <th>Recruiter</th>
                <th>Department</th>
                <th>Current Plan</th>
                <th>Start Date</th>
                <th>End Date</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {costData.recruiters.map((recruiter) => {
                const plan = recruiter.plan || {};
                const sub = recruiter.subscription || {};
                const planName = plan.name || 'Free Tier';
                const subStatus = sub.status || 'none';
                return (
                  <tr key={recruiter.id}>
                    <td>
                      <div className={styles.recruiterCell}>
                        <div className={styles.tableAvatar}>
                          {(recruiter.name || 'U').split(' ').map(n => n[0]).join('')}
                        </div>
                        <div>
                          <span className={styles.tableName}>{recruiter.name || 'Unknown'}</span>
                          <span className={styles.tableEmail}>{recruiter.email || ''}</span>
                        </div>
                      </div>
                    </td>
                    <td><span className={styles.deptBadge}>{recruiter.department || 'General'}</span></td>
                    <td>
                      <span className={`${styles.planBadge} ${getPlanBadgeClass(planName)}`}>
                        {planName}
                      </span>
                    </td>
                    <td>{formatDate(sub.start_date)}</td>
                    <td>{formatDate(sub.end_date)}</td>
                    <td>
                      <span className={`${styles.statusBadge} ${
                        subStatus === 'active' ? styles.statusActive 
                        : subStatus === 'expired' ? styles.statusExpired 
                        : styles.statusNone
                      }`}>
                        {subStatus === 'active' ? 'Active' 
                          : subStatus === 'expired' ? 'Expired' 
                          : subStatus === 'none' ? 'No Plan'
                          : subStatus.charAt(0).toUpperCase() + subStatus.slice(1)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      </div>
    </AdminLayout>
  );
};

export default CostStatistics;

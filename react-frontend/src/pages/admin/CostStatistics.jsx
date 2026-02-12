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
  const RecruiterStackedBar = ({ recruiter, maxValue }) => {
    const cloudflare = recruiter.breakdown?.cloudflare || 0;
    const nlp = recruiter.breakdown?.nlp || 0;
    const llm = recruiter.breakdown?.llm || 0;
    const allocated = recruiter.allocated || maxValue || 1;
    const total = cloudflare + nlp + llm;
    // Calculate width relative to this recruiter's own allocation
    const cloudflareWidth = allocated > 0 ? (cloudflare / allocated) * 100 : 0;
    const nlpWidth = allocated > 0 ? (nlp / allocated) * 100 : 0;
    const llmWidth = allocated > 0 ? (llm / allocated) * 100 : 0;

    return (
      <div className={styles.stackedBarRow}>
        <div className={styles.stackedBarInfo}>
          <div className={styles.recruiterAvatar}>
            {(recruiter.name || 'U').split(' ').map(n => n[0]).join('')}
          </div>
          <div className={styles.recruiterDetails}>
            <span className={styles.recruiterName}>{recruiter.name || 'Unknown'}</span>
            <span className={styles.recruiterDept}>{recruiter.department || 'General'}</span>
          </div>
        </div>
        <div className={styles.stackedBarContainer}>
          <div className={styles.stackedBarTrack}>
            <div 
              className={styles.stackedBarSegment}
              style={{ width: `${cloudflareWidth}%`, background: '#f59e0b' }}
              title={`Cloudflare: ₹${cloudflare.toLocaleString()}`}
            ></div>
            <div 
              className={styles.stackedBarSegment}
              style={{ width: `${nlpWidth}%`, background: '#10b981' }}
              title={`NLP (Gemini): ₹${nlp.toLocaleString()}`}
            ></div>
            <div 
              className={styles.stackedBarSegment}
              style={{ width: `${llmWidth}%`, background: '#6366f1' }}
              title={`LLM (ChatGPT): ₹${llm.toLocaleString()}`}
            ></div>
          </div>
          <span className={styles.stackedBarTotal}>₹{total.toLocaleString()} / ₹{allocated.toLocaleString()}</span>
        </div>
      </div>
    );
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

  const maxRecruiterUsage = costData.recruiters.length > 0 
    ? Math.max(...costData.recruiters.map(r => 
        (r.breakdown?.cloudflare || 0) + (r.breakdown?.nlp || 0) + (r.breakdown?.llm || 0)
      ))
    : 100;

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

      {/* Horizontal Bars Section */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>Service Credit Usage</h2>
          <p>Visual comparison of allocated vs used credits per service</p>
        </div>
        <div className={styles.horizontalBarsCard}>
          <HorizontalBar 
            label="Cloudflare (GPU)"
            value={cloudflare.used}
            maxValue={cloudflare.allocated}
            color="#f59e0b"
            sublabel="Video processing & face verification"
          />
          <HorizontalBar 
            label="NLP (Gemini)"
            value={nlp.used}
            maxValue={nlp.allocated}
            color="#10b981"
            sublabel="CV analysis & job matching"
          />
          <HorizontalBar 
            label="LLM (ChatGPT)"
            value={llm.used}
            maxValue={llm.allocated}
            color="#6366f1"
            sublabel="Interview questions & evaluation"
          />
        </div>
      </div>

      {/* Recruiter Allocations Table */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>Recruiter Credit Allocations</h2>
          <p>Individual credit allocation and usage per recruiter</p>
        </div>
        <div className={styles.tableCard}>
          <table className={styles.recruitersTable}>
            <thead>
              <tr>
                <th>Recruiter</th>
                <th>Department</th>
                <th>Allocated</th>
                <th>Used</th>
                <th>Available</th>
                <th>Usage</th>
              </tr>
            </thead>
            <tbody>
              {costData.recruiters.map((recruiter) => {
                const allocated = recruiter.allocated || 0;
                const used = recruiter.used || 0;
                const percentage = allocated > 0 ? calculatePercentage(used, allocated) : 0;
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
                  <td>₹{allocated.toLocaleString()}</td>
                  <td>₹{used.toLocaleString()}</td>
                  <td>₹{(allocated - used).toLocaleString()}</td>
                  <td>
                    <div className={styles.usageCell}>
                      <div className={styles.usageBar}>
                        <div 
                          className={styles.usageFill}
                          style={{ 
                            width: `${percentage}%`,
                            background: percentage > 90 
                              ? '#ef4444' 
                              : percentage > 70 
                                ? '#f59e0b' 
                                : '#10b981'
                          }}
                        ></div>
                      </div>
                      <span className={styles.usagePercent}>
                        {percentage}%
                      </span>
                    </div>
                  </td>
                </tr>
              )})}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stacked Bar Chart */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2>Recruiter Cost Breakdown</h2>
          <p>Compare service usage across all recruiters</p>
        </div>
        <div className={styles.stackedChartCard}>
          <div className={styles.chartLegend}>
            <div className={styles.legendEntry}>
              <span className={styles.legendColor} style={{ background: '#f59e0b' }}></span>
              <span>Cloudflare (GPU)</span>
            </div>
            <div className={styles.legendEntry}>
              <span className={styles.legendColor} style={{ background: '#10b981' }}></span>
              <span>NLP (Gemini)</span>
            </div>
            <div className={styles.legendEntry}>
              <span className={styles.legendColor} style={{ background: '#6366f1' }}></span>
              <span>LLM (ChatGPT)</span>
            </div>
          </div>
          <div className={styles.stackedBarsContainer}>
            {costData.recruiters.map((recruiter) => (
              <RecruiterStackedBar 
                key={recruiter.id}
                recruiter={recruiter}
                maxValue={maxRecruiterUsage}
              />
            ))}
          </div>
        </div>
      </div>
      </div>
    </AdminLayout>
  );
};

export default CostStatistics;

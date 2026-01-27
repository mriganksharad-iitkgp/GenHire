import React, { useState, useEffect } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import styles from './CostStatistics.module.css';

const CostStatistics = () => {
  const [loading, setLoading] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState('month');
  const [costData, setCostData] = useState(null);

  // Mock data for cost statistics
  const mockCostData = {
    overview: {
      totalBudget: 50000,
      totalUsed: 32450,
      cloudflare: { allocated: 15000, used: 8750 },
      nlp: { allocated: 20000, used: 14200 },
      llm: { allocated: 15000, used: 9500 }
    },
    recruiters: [
      {
        id: 1,
        name: 'Sarah Johnson',
        email: 'sarah.johnson@company.com',
        department: 'Engineering',
        allocated: 5000,
        used: 3850,
        breakdown: { cloudflare: 1200, nlp: 1650, llm: 1000 }
      },
      {
        id: 2,
        name: 'Michael Chen',
        email: 'michael.chen@company.com',
        department: 'Sales',
        allocated: 4500,
        used: 4200,
        breakdown: { cloudflare: 900, nlp: 2100, llm: 1200 }
      },
      {
        id: 3,
        name: 'Emily Davis',
        email: 'emily.davis@company.com',
        department: 'Marketing',
        allocated: 3500,
        used: 2100,
        breakdown: { cloudflare: 600, nlp: 900, llm: 600 }
      },
      {
        id: 4,
        name: 'David Wilson',
        email: 'david.wilson@company.com',
        department: 'Engineering',
        allocated: 6000,
        used: 5450,
        breakdown: { cloudflare: 1500, nlp: 2450, llm: 1500 }
      },
      {
        id: 5,
        name: 'Jessica Brown',
        email: 'jessica.brown@company.com',
        department: 'HR',
        allocated: 4000,
        used: 2850,
        breakdown: { cloudflare: 750, nlp: 1350, llm: 750 }
      },
      {
        id: 6,
        name: 'James Taylor',
        email: 'james.taylor@company.com',
        department: 'Product',
        allocated: 5500,
        used: 4800,
        breakdown: { cloudflare: 1200, nlp: 2200, llm: 1400 }
      }
    ]
  };

  useEffect(() => {
    // Simulate API call
    const fetchData = async () => {
      setLoading(true);
      await new Promise(resolve => setTimeout(resolve, 500));
      setCostData(mockCostData);
      setLoading(false);
    };
    fetchData();
  }, [selectedPeriod]);

  const calculatePercentage = (used, total) => {
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
    const { cloudflare, nlp, llm } = recruiter.breakdown;
    const total = cloudflare + nlp + llm;
    const cloudflareWidth = (cloudflare / maxValue) * 100;
    const nlpWidth = (nlp / maxValue) * 100;
    const llmWidth = (llm / maxValue) * 100;

    return (
      <div className={styles.stackedBarRow}>
        <div className={styles.stackedBarInfo}>
          <div className={styles.recruiterAvatar}>
            {recruiter.name.split(' ').map(n => n[0]).join('')}
          </div>
          <div className={styles.recruiterDetails}>
            <span className={styles.recruiterName}>{recruiter.name}</span>
            <span className={styles.recruiterDept}>{recruiter.department}</span>
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
          <span className={styles.stackedBarTotal}>₹{total.toLocaleString()}</span>
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

  const maxRecruiterUsage = Math.max(...costData.recruiters.map(r => 
    r.breakdown.cloudflare + r.breakdown.nlp + r.breakdown.llm
  ));

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
            <span className={styles.overviewValue}>₹{costData.overview.totalBudget.toLocaleString()}</span>
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
            <span className={styles.overviewValue}>₹{costData.overview.totalUsed.toLocaleString()}</span>
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
            <span className={styles.overviewValue}>₹{(costData.overview.totalBudget - costData.overview.totalUsed).toLocaleString()}</span>
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
            <span className={styles.overviewValue}>{calculatePercentage(costData.overview.totalUsed, costData.overview.totalBudget)}%</span>
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
            used={costData.overview.cloudflare.used}
            total={costData.overview.cloudflare.allocated}
            color="#f59e0b"
            label="Cloudflare (GPU)"
            icon="☁️"
          />
          <PieChart 
            used={costData.overview.nlp.used}
            total={costData.overview.nlp.allocated}
            color="#10b981"
            label="NLP (Gemini)"
            icon="🧠"
          />
          <PieChart 
            used={costData.overview.llm.used}
            total={costData.overview.llm.allocated}
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
            value={costData.overview.cloudflare.used}
            maxValue={costData.overview.cloudflare.allocated}
            color="#f59e0b"
            sublabel="Video processing & face verification"
          />
          <HorizontalBar 
            label="NLP (Gemini)"
            value={costData.overview.nlp.used}
            maxValue={costData.overview.nlp.allocated}
            color="#10b981"
            sublabel="CV analysis & job matching"
          />
          <HorizontalBar 
            label="LLM (ChatGPT)"
            value={costData.overview.llm.used}
            maxValue={costData.overview.llm.allocated}
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
              {costData.recruiters.map((recruiter) => (
                <tr key={recruiter.id}>
                  <td>
                    <div className={styles.recruiterCell}>
                      <div className={styles.tableAvatar}>
                        {recruiter.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div>
                        <span className={styles.tableName}>{recruiter.name}</span>
                        <span className={styles.tableEmail}>{recruiter.email}</span>
                      </div>
                    </div>
                  </td>
                  <td><span className={styles.deptBadge}>{recruiter.department}</span></td>
                  <td>₹{recruiter.allocated.toLocaleString()}</td>
                  <td>₹{recruiter.used.toLocaleString()}</td>
                  <td>₹{(recruiter.allocated - recruiter.used).toLocaleString()}</td>
                  <td>
                    <div className={styles.usageCell}>
                      <div className={styles.usageBar}>
                        <div 
                          className={styles.usageFill}
                          style={{ 
                            width: `${calculatePercentage(recruiter.used, recruiter.allocated)}%`,
                            background: calculatePercentage(recruiter.used, recruiter.allocated) > 90 
                              ? '#ef4444' 
                              : calculatePercentage(recruiter.used, recruiter.allocated) > 70 
                                ? '#f59e0b' 
                                : '#10b981'
                          }}
                        ></div>
                      </div>
                      <span className={styles.usagePercent}>
                        {calculatePercentage(recruiter.used, recruiter.allocated)}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
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

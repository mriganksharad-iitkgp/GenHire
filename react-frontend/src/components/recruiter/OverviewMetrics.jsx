import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';

const OverviewMetrics = ({ jobPostingsCount, applicationsCount, applications = [] }) => {
  // Calculate interviews completed (applications with status "interviewed" or higher)
  const interviewsCompleted = applications.filter(app => {
    const status = String(app.status || '').toLowerCase();
    return status === 'interviewed' || status === 'selected' || status === 'rejected';
  }).length;

  // Calculate selected candidates (applications with status "selected")
  const selectedCandidates = applications.filter(app => {
    const status = String(app.status || '').toLowerCase();
    return status === 'selected';
  }).length;

  return (
    <div className={styles.metricsGrid}>
      <div className={styles.metricCard}>
        <div className={styles.metricHeader}>
          <div className={styles.metricIcon}>
            <i className="fa fa-briefcase"></i>
          </div>
        </div>
        <div className={styles.metricValue}>{jobPostingsCount}</div>
        <p className={styles.metricLabel}>Active Job Postings</p>
      </div>
      <div className={styles.metricCard}>
        <div className={styles.metricHeader}>
          <div className={styles.metricIcon}>
            <i className="fa fa-users"></i>
          </div>
        </div>
        <div className={styles.metricValue}>{applicationsCount}</div>
        <p className={styles.metricLabel}>Total Applicants</p>
      </div>
      <div className={styles.metricCard}>
        <div className={styles.metricHeader}>
          <div className={styles.metricIcon}>
            <i className="fa fa-calendar"></i>
          </div>
        </div>
        <div className={styles.metricValue}>{interviewsCompleted}</div>
        <p className={styles.metricLabel}>Interviews Completed</p>
      </div>
      <div className={styles.metricCard}>
        <div className={styles.metricHeader}>
          <div className={styles.metricIcon}>
            <i className="fa fa-check"></i>
          </div>
        </div>
        <div className={styles.metricValue}>{selectedCandidates}</div>
        <p className={styles.metricLabel}>Selected Candidates</p>
      </div>
    </div>
  );
};

export default OverviewMetrics;

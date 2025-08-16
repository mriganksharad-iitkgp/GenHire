import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';

const OverviewMetrics = ({ jobPostingsCount, applicationsCount }) => (
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
      <div className={styles.metricValue}>0</div>
      <p className={styles.metricLabel}>Interviews Completed</p>
    </div>
    <div className={styles.metricCard}>
      <div className={styles.metricHeader}>
        <div className={styles.metricIcon}>
          <i className="fa fa-check"></i>
        </div>
      </div>
      <div className={styles.metricValue}>0</div>
      <p className={styles.metricLabel}>Selected Candidates</p>
    </div>
  </div>
);

export default OverviewMetrics;

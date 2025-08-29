import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';

export const Tabs = ({ activeTab, onChange }) => (
  <div className={styles.tabNavigation}>
    <div className={styles.tabList}>
      <button 
        className={`${styles.tabButton} ${activeTab === 'overview' ? styles.active : ''}`}
        onClick={() => onChange('overview')}
      >
        <i className="fa fa-dashboard"></i> Overview
      </button>
      <button 
        className={`${styles.tabButton} ${activeTab === 'jobs' ? styles.active : ''}`}
        onClick={() => onChange('jobs')}
      >
        <i className="fa fa-briefcase"></i> Job Postings
      </button>
      <button 
        className={`${styles.tabButton} ${activeTab === 'candidates' ? styles.active : ''}`}
        onClick={() => onChange('candidates')}
      >
        <i className="fa fa-users"></i> Candidates
      </button>
      <button 
        className={`${styles.tabButton} ${activeTab === 'profile' ? styles.active : ''}`}
        onClick={() => onChange('profile')}
      >
        <i className="fa fa-building"></i> Company Profile
      </button>
    </div>
  </div>
);

export default Tabs;

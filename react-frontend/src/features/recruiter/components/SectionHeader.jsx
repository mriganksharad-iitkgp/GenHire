import React from 'react';
import styles from 'features/recruiter/pages/RecruiterDashboard.module.css';

const SectionHeader = ({ title, actions }) => (
  <div className={styles.sectionHeader}>
    <h2>{title}</h2>
    {actions}
  </div>
);

export default SectionHeader;

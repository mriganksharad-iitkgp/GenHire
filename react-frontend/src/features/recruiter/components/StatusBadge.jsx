import React from 'react';
import styles from 'features/recruiter/pages/RecruiterDashboard.module.css';

const StatusBadge = ({ text, color, className }) => (
  <span className={`${styles.statusBadge} ${className || ''}`.trim()} style={color ? { backgroundColor: color } : undefined}>
    {text}
  </span>
);

export default StatusBadge;

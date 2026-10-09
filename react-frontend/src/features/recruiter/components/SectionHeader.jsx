import React from 'react';
import PortalPageHeader from "shared/components/ui/PortalPageHeader";
import styles from 'features/recruiter/pages/RecruiterDashboard.module.css';

const SectionHeader = ({ title, actions, subtitle, icon }) => subtitle ? <PortalPageHeader title={title} subtitle={subtitle} icon={icon} eyebrow="Your hiring workspace" actions={actions} /> : (
  <div className={styles.sectionHeader}>
    <h2>{title}</h2>
    {actions}
  </div>
);

export default SectionHeader;

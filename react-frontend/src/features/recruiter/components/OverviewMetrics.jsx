import React from 'react';
import styles from 'features/recruiter/pages/RecruiterDashboard.module.css';

const OverviewMetrics = ({ jobPostingsCount, applicationsCount, applications = [] }) => {
  // Calculate interviews completed (applications with status "interviewed" or higher)
  // ('selected' is the legacy name for 'screening_cleared')
  const interviewsCompleted = applications.filter(app => {
    if (app.workflow_version_id) return app.workflow?.stages.some(s => s.type === 'screening' && s.state === 'completed');
    const status = String(app.status || '').toLowerCase();
    return status === 'interviewed' || status === 'screening_cleared' || status === 'selected' || (status === 'rejected' && (app.interview_completed || Number.isFinite(app.interview_score)));
  }).length;

  // Calculate candidates who cleared the AI screening round
  const screeningClearedCandidates = applications.filter(app => {
    if (app.workflow_version_id) return app.workflow?.stages.some(s => s.type === 'screening' && s.state === 'completed' && s.outcome === 'cleared');
    const status = String(app.status || '').toLowerCase();
    return status === 'screening_cleared' || status === 'selected';
  }).length;
  const inCompanyRounds = applications.filter(app => app.workflow?.lifecycle === 'active' && app.workflow.stages.find(s => s.stage_id === app.workflow.current_stage_id)?.type === 'company').length;
  const hired = applications.filter(app => app.workflow?.lifecycle === 'hired').length;

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
        <div className={styles.metricValue}>{screeningClearedCandidates}</div>
        <p className={styles.metricLabel}>Screening Cleared</p>
      </div>
      <div className={styles.metricCard}><div className={styles.metricValue}>{inCompanyRounds}</div><p className={styles.metricLabel}>In Company Rounds</p></div>
      <div className={styles.metricCard}><div className={styles.metricValue}>{hired}</div><p className={styles.metricLabel}>Hired</p></div>
    </div>
  );
};

export default OverviewMetrics;

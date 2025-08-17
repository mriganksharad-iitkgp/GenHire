import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';

const RecentActivity = ({ applications }) => (
  <div className={styles.recentActivity}>
    <div className={styles.sectionHeader}>
      <h3 className={styles.sectionTitle}>
        <i className="fa fa-clock-o"></i>
        Recent Activity
      </h3>
    </div>
    <ul className={styles.activityList}>
      {[...applications]
        .sort((a, b) => {
          const getTs = (x) => {
            const t = x?.applied_at || x?.updated_at || x?.created_at || x?.appliedDate || x?.updatedAt || x?.createdAt;
            const ts = t ? Date.parse(t) : NaN;
            return Number.isNaN(ts) ? 0 : ts;
          };
          return getTs(b) - getTs(a);
        })
        .slice(0, 5)
        .map((app) => {
        const timePart = app.applied_at || app.created_at || app.updated_at || 'ts';
        const userPart = app.student_id || app.email || app.student_name || 'user';
        const key = app._id || `${app.job_id || 'job'}-${userPart}-${timePart}`;
        return (
        <li key={key} className={styles.activityItem}>
          <div className={styles.activityIcon}>
            <i className="fa fa-user"></i>
          </div>
          <div className={styles.activityContent}>
            <p className={styles.activityText}>
              {(app.student_name || app.candidate_name)} applied for {app.job_title}
            </p>
            <p className={styles.activityTime}>
              {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : 'Recently'}
            </p>
          </div>
          <span className={`${styles.activityStatus} ${
            app.status === 'pending' ? styles.statusPending :
            app.status === 'shortlisted' ? styles.statusShortlisted :
            app.status === 'interviewed' ? styles.statusInterviewed :
            styles.statusPending
          }`}>
            {app.status || 'PENDING'}
          </span>
        </li>
        );
      })}
      {applications.length === 0 && (
        <li className={styles.emptyState}>
          <i className="fa fa-inbox"></i>
          <h3>No recent activity</h3>
          <p>Applications will appear here as candidates apply to your job postings.</p>
        </li>
      )}
    </ul>
  </div>
);

export default RecentActivity;

import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';

const JobsGrid = ({ jobs, getStatusColor, displayStatus, getCandidatesForJob, onViewDetails, onViewCandidates, onEdit }) => (
  <div className={styles.jobsGrid}>
    {jobs.map((job, idx) => (
      <div key={job._id || job.id || `job-${idx}`} className={styles.jobCard}>
        <div className={styles.jobHeader}>
          <h3>{job.title}</h3>
          <span 
            className={styles.statusBadge}
            style={{ backgroundColor: getStatusColor(job.status) }}
          >
            {displayStatus(job.status)}
          </span>
        </div>
        <div className={styles.jobMeta}>
          <p><i className="fa fa-map-marker"></i> {job.location}</p>
          <p><i className="fa fa-money"></i> {job.salary}</p>
          <p><i className="fa fa-calendar"></i> Deadline: {job.deadline}</p>
        </div>
        <div className={styles.jobProgress}>
          <div className={styles.progressItem}>
            <span className={styles.progressNumber}>{job.applicants}</span>
            <span className={styles.progressLabel}>Applicants</span>
          </div>
          <div className={styles.progressItem}>
            <span className={styles.progressNumber}>{job.interviewed}</span>
            <span className={styles.progressLabel}>Interviewed</span>
          </div>
          <div className={styles.progressItem}>
            <span className={styles.progressNumber}>{job.selected}</span>
            <span className={styles.progressLabel}>Selected</span>
          </div>
          <div className={styles.progressItem}>
            <span className={styles.progressNumber}>{job.rejected}</span>
            <span className={styles.progressLabel}>Rejected</span>
          </div>
        </div>
        <div className={styles.jobActions}>
          <button className={styles.secondaryButton} onClick={() => onViewDetails(job)}>
            <i className="fa fa-eye"></i> View Details
          </button>
          <button className={styles.secondaryButton} onClick={() => onViewCandidates(job)}>
            <i className="fa fa-users"></i> View Candidates ({getCandidatesForJob(job._id || job.id).length})
          </button>
          <button className={styles.secondaryButton} onClick={() => onEdit(job)}>
            <i className="fa fa-edit"></i> Edit
          </button>
        </div>
      </div>
    ))}
  </div>
);

export default JobsGrid;

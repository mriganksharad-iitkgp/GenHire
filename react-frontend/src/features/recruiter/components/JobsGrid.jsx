import React, { useState, useEffect } from 'react';
import styles from 'features/recruiter/pages/RecruiterDashboard.module.css';
import Pagination from 'shared/components/ui/Pagination';

const JobsGrid = ({ jobs, getStatusColor, displayStatus, getCandidatesForJob, onViewDetails, onViewCandidates, onEdit, onInviteCandidates }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 9; // 3x3 grid
  
  // Reset to page 1 when jobs change
  useEffect(() => {
    setCurrentPage(1);
  }, [jobs.length]);
  
  // Pagination logic
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedJobs = jobs.slice(startIndex, endIndex);
  const totalPages = Math.ceil(jobs.length / itemsPerPage);
  
  return (
    <>
      <div className={styles.jobsGrid}>
        {paginatedJobs.map((job, idx) => (
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
            <span className={styles.progressNumber}>{job.screening_cleared ?? job.selected ?? 0}</span>
            <span className={styles.progressLabel}>Screening Cleared</span>
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
          {onInviteCandidates && (
            <button className={styles.secondaryButton} onClick={() => onInviteCandidates(job)}>
              <i className="fa fa-paper-plane"></i> Invite Candidates
            </button>
          )}
        </div>
      </div>
        ))}
      </div>
      
      {/* Pagination */}
      {jobs.length > 0 && totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          totalItems={jobs.length}
          itemsPerPage={itemsPerPage}
        />
      )}
    </>
  );
};

export default JobsGrid;

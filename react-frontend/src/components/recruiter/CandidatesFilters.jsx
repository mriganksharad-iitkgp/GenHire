import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';

const CandidatesFilters = ({ jobPostings, selectedPosition, selectedStatus, onPositionChange, onStatusChange, onClear }) => (
  <div className={styles.candidateFilters}>
    <select 
      className={styles.filterSelect}
      value={selectedPosition}
      onChange={(e) => onPositionChange(e.target.value)}
    >
      <option value="">All Positions</option>
      {jobPostings.map((job, idx) => (
        <option key={job._id || job.id || `jobopt-${idx}`} value={job.title}>{job.title}</option>
      ))}
    </select>
    <select 
      className={styles.filterSelect}
      value={selectedStatus}
      onChange={(e) => onStatusChange(e.target.value)}
    >
      <option value="">All Statuses</option>
      <option value="Pending Interview">Pending Interview</option>
      <option value="Interviewed">Interviewed</option>
      <option value="Selected">Selected</option>
      <option value="Rejected">Rejected</option>
    </select>
    {(selectedPosition || selectedStatus) && (
      <button className={styles.clearFiltersButton} onClick={onClear}>
        <i className="fa fa-times"></i> Clear Filters
      </button>
    )}
  </div>
);

export default CandidatesFilters;

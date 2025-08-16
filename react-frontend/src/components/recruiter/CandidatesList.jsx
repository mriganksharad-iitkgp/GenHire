import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';
import CandidateCard from './CandidateCard';

const CandidatesList = ({ applications, totalCount, selectedPosition, selectedStatus, onClear, displayStatus, updateApplicationStatus, viewInterviewReport }) => (
  <div className={styles.candidatesTable}>
    <div className={styles.candidatesCount}>
      Showing {applications.length} of {totalCount} applications
      {(selectedPosition || selectedStatus) && (
        <span className={styles.filterIndicator}>(filtered)</span>
      )}
    </div>
    {applications.length === 0 ? (
      <div className={styles.noCandidates}>
        <i className="fa fa-users"></i>
        <h3>No applications found</h3>
        <p>{(selectedPosition || selectedStatus) ? 'Try adjusting your filters to see more applications.' : 'No applications have been submitted yet.'}</p>
        {(selectedPosition || selectedStatus) && (
          <button className={styles.secondaryButton} onClick={onClear}>
            <i className="fa fa-refresh"></i> Clear Filters
          </button>
        )}
      </div>
    ) : (
      applications.map((application, idx) => (
        <CandidateCard
          key={application._id || `app-${idx}`}
          application={application}
          displayStatus={displayStatus}
          updateApplicationStatus={updateApplicationStatus}
          viewInterviewReport={viewInterviewReport}
        />
      ))
    )}
  </div>
);

export default CandidatesList;

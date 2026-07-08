import React, { useState, useEffect } from 'react';
import styles from 'features/recruiter/pages/RecruiterDashboard.module.css';
import CandidateCard from './CandidateCard';
import Pagination from 'shared/components/ui/Pagination';

const CandidatesList = ({ applications, totalCount, selectedPosition, selectedStatus, onClear, displayStatus, updateApplicationStatus, viewInterviewReport, viewProctoringReport }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  
  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedPosition, selectedStatus, applications.length]);
  
  // Pagination logic
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedApplications = applications.slice(startIndex, endIndex);
  const totalPages = Math.ceil(applications.length / itemsPerPage);
  
  return (
    <>
      <div className={styles.candidatesTable}>
        <div className={styles.candidatesCount}>
          Showing {Math.min(startIndex + 1, applications.length)}-{Math.min(endIndex, applications.length)} of {applications.length} applications
          {(selectedPosition || selectedStatus) && (
            <span className={styles.filterIndicator}>(filtered from {totalCount} total)</span>
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
          paginatedApplications.map((application, idx) => (
            <CandidateCard
              key={application._id || `app-${idx}`}
              application={application}
              displayStatus={displayStatus}
              updateApplicationStatus={updateApplicationStatus}
              viewInterviewReport={viewInterviewReport}
              viewProctoringReport={viewProctoringReport}
            />
          ))
        )}
      </div>
      
      {/* Pagination */}
      {applications.length > 0 && totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          totalItems={applications.length}
          itemsPerPage={itemsPerPage}
        />
      )}
    </>
  );
};

export default CandidatesList;

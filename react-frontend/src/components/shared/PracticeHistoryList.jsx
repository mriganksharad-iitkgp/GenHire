import React, { useState } from 'react';
import Pagination from '../Pagination';
import styles from './PracticeHistoryList.module.css';

/**
 * Reusable Practice History List Component
 * Used in both candidate Practice page and admin CandidateDetail page
 */
const PracticeHistoryList = ({
  sessions = [],
  isLoading = false,
  onViewReport,
  onViewCV,
  onViewJD,
  itemsPerPage = 5,
  showTitle = true,
  isAdmin = false
}) => {
  const [currentPage, setCurrentPage] = useState(1);

  // Predefined roles for display
  const roles = [
    { id: 'software-engineer', name: 'Software Engineer', icon: 'fa-code' },
    { id: 'data-scientist', name: 'Data Scientist', icon: 'fa-line-chart' },
    { id: 'product-manager', name: 'Product Manager', icon: 'fa-tasks' },
    { id: 'business-analyst', name: 'Business Analyst', icon: 'fa-briefcase' },
    { id: 'fullstack-developer', name: 'Full Stack Developer', icon: 'fa-laptop' },
    { id: 'devops-engineer', name: 'DevOps Engineer', icon: 'fa-server' },
    { id: 'custom', name: 'Custom', icon: 'fa-upload' }
  ];

  // Helper function to get role icon
  const getRoleIcon = (roleId) => {
    const role = roles.find(r => r.id === roleId);
    return role ? role.icon : 'fa-briefcase';
  };

  // Helper function to get role name
  const getRoleName = (roleId) => {
    const role = roles.find(r => r.id === roleId);
    if (role) return role.name;
    // Format role ID to readable name
    return roleId?.split('-').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ') || 'Practice Interview';
  };

  const formatUsd = (value) => {
    const numeric = Number(value || 0);
    return `$${numeric.toFixed(4)}`;
  };

  // Filter for completed/ended sessions
  const completedSessions = sessions.filter(
    session => session.status === 'completed' || session.status === 'ended'
  );

  // Pagination
  const totalPages = Math.ceil(completedSessions.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedSessions = completedSessions.slice(startIndex, startIndex + itemsPerPage);

  if (isLoading) {
    return (
      <div className={styles.container}>
        {showTitle && (
          <h3 className={styles.sectionTitle}>
            <i className="fa fa-history"></i> Practice History
          </h3>
        )}
        <div className={styles.loadingState}>
          <i className="fa fa-spinner fa-spin"></i> Loading practice history...
        </div>
      </div>
    );
  }

  if (completedSessions.length === 0) {
    return (
      <div className={styles.container}>
        {showTitle && (
          <h3 className={styles.sectionTitle}>
            <i className="fa fa-history"></i> Practice History
          </h3>
        )}
        <div className={styles.emptyState}>
          <i className="fa fa-inbox"></i>
          <p>No practice interviews completed yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {showTitle && (
        <h3 className={styles.sectionTitle}>
          <i className="fa fa-history"></i> Practice History ({completedSessions.length})
        </h3>
      )}

      <div className={styles.historyGrid}>
        {paginatedSessions.map((session) => (
          <div 
            key={session.session_id || session._id} 
            className={styles.applicationCard} 
            data-status="ended"
          >
            {/* Card Header */}
            <div className={styles.applicationHeader}>
              <div className={styles.companyAvatar}>
                <div className={styles.practiceLogoWrapper}>
                  <i className={`fa ${getRoleIcon(session.role)}`}></i>
                </div>
              </div>
              <div className={styles.jobTitleWrap}>
                <h3>{getRoleName(session.role)}</h3>
                <div className={styles.companySubtle}>Practice Mode</div>
              </div>
              <div className={styles.headerBadges}>
                <span className={`${styles.statusBadge} ${styles.ended}`}>ENDED</span>
              </div>
            </div>

            {/* Application Details */}
            <div className={styles.applicationDetails}>
              <div className={styles.metaRow}>
                <div className={styles.metaItem}>
                  <i className="fa fa-building"></i>
                  <span>Practice Session</span>
                </div>
                <div className={styles.metaItem}>
                  <i className="fa fa-map-marker"></i>
                  <span>Online</span>
                </div>
                <div className={styles.metaItem}>
                  <i className="fa fa-calendar"></i>
                  <span>Completed {new Date(session.created_at).toLocaleDateString()}</span>
                </div>
              </div>
              <div className={styles.tagsRow}>
                <span className={styles.chip}>
                  <i className="fa fa-history"></i> Practice
                </span>
              </div>
            </div>

            {/* Scores and Actions */}
            <div className={styles.applicationActions}>
              <div className={styles.scoresRow}>
                <div className={styles.scorePill}>
                  <span className={styles.pillLabel}>CV Score</span>
                  <span className={styles.pillValue}>
                    {Math.round((session.cv_score || 0) * 100)}%
                  </span>
                  <div className={styles.miniBar}>
                    <div 
                      style={{ 
                        width: `${Math.round((session.cv_score || 0) * 100)}%`, 
                        backgroundColor: '#3b82f6' 
                      }}
                    ></div>
                  </div>
                </div>
                <div className={styles.scorePill}>
                  <span className={styles.pillLabel}>Interview</span>
                  <span className={styles.pillValue}>{session.interview_score || 0}%</span>
                  <div className={styles.miniBar}>
                    <div 
                      style={{ 
                        width: `${session.interview_score || 0}%`, 
                        backgroundColor: '#10b981' 
                      }}
                    ></div>
                  </div>
                </div>
                <div className={styles.scorePill}>
                  <span className={styles.pillLabel}>Proctoring</span>
                  <span className={styles.pillValue}>{session.proctoring_score || 100}%</span>
                  <div className={styles.miniBar}>
                    <div 
                      style={{ 
                        width: `${session.proctoring_score || 100}%`, 
                        backgroundColor: '#f59e0b' 
                      }}
                    ></div>
                  </div>
                </div>
                {session.calculated_cost_usd !== undefined && session.calculated_cost_usd !== null && (
                  <div className={styles.scorePill}>
                    <span className={styles.pillLabel}>Calculated Cost</span>
                    <span className={styles.pillValue}>{formatUsd(session.calculated_cost_usd)}</span>
                  </div>
                )}
                {session.actual_cost_usd !== undefined && session.actual_cost_usd !== null && (
                  <div className={styles.scorePill}>
                    <span className={styles.pillLabel}>Actual Cost</span>
                    <span className={styles.pillValue}>{formatUsd(session.actual_cost_usd)}</span>
                  </div>
                )}
              </div>

              <div className={styles.actionButtons}>
                {onViewCV && (
                  <button
                    className={styles.cvButton}
                    onClick={() => onViewCV(session)}
                    title="View CV used for this practice"
                  >
                    <i className="fa fa-file-text"></i> View CV
                  </button>
                )}
                {onViewJD && (
                  <button
                    className={styles.detailsButton}
                    onClick={() => onViewJD(session)}
                    title="View job description"
                  >
                    <i className="fa fa-file-text-o"></i> View JD
                  </button>
                )}
                {onViewReport && (
                  <button
                    className={styles.reportButton}
                    onClick={() => onViewReport(session.session_id || session._id)}
                  >
                    <i className="fa fa-file-text-o"></i> Report
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          totalItems={completedSessions.length}
          itemsPerPage={itemsPerPage}
        />
      )}
    </div>
  );
};

export default PracticeHistoryList;

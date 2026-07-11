import React, { useState, useEffect } from 'react';
import Pagination from 'shared/components/ui/Pagination';
import styles from './ApplicationHistoryList.module.css';
import { normalizeStatus, statusLabel } from 'shared/utils/applicationStatus';

/**
 * Reusable Application History List Component
 * Matches the candidate portal design but adds admin functionality
 */
const ApplicationHistoryList = ({
  applications = [],
  isLoading = false,
  onViewDetails,
  onViewCV,
  onViewReport,
  onDeleteApplication,
  onStatusChange,
  itemsPerPage = 8,
  showTitle = true,
  isAdmin = false
}) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [filters, setFilters] = useState({
    search: '',
    status: '',
    sortBy: 'applied_at',
    sortOrder: 'desc'
  });
  const [editingStatus, setEditingStatus] = useState(null); // {appId, newStatus}

  // Filter and sort applications
  const filteredApps = applications
    .filter(app => {
      if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        if (!app.job_title?.toLowerCase().includes(searchLower) && 
            !app.company?.toLowerCase().includes(searchLower)) {
          return false;
        }
      }
      if (filters.status && normalizeStatus(app.status) !== normalizeStatus(filters.status)) {
        return false;
      }
      return true;
    })
    .sort((a, b) => {
      let aVal = a[filters.sortBy];
      let bVal = b[filters.sortBy];
      if (filters.sortBy === 'applied_at') {
        aVal = new Date(aVal || 0).getTime();
        bVal = new Date(bVal || 0).getTime();
      }
      if (filters.sortOrder === 'desc') {
        return bVal > aVal ? 1 : -1;
      }
      return aVal > bVal ? 1 : -1;
    });

  // Pagination
  const totalPages = Math.ceil(filteredApps.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedApps = filteredApps.slice(startIndex, startIndex + itemsPerPage);

  // Reset page on filter change
  useEffect(() => {
    setCurrentPage(1);
  }, [filters.search, filters.status]);

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' });
  };

  const getStatusClass = (status) => {
    return styles[normalizeStatus(status)] || '';
  };

  const formatUsd = (value) => {
    const numeric = Number(value || 0);
    return `$${numeric.toFixed(4)}`;
  };

  const handleStatusUpdate = async (appId, newStatus) => {
    if (onStatusChange) {
      await onStatusChange(appId, newStatus);
    }
    setEditingStatus(null);
  };

  if (isLoading) {
    return (
      <div className={styles.container}>
        {showTitle && (
          <h3 className={styles.sectionTitle}>
            <i className="fa fa-file-text-o"></i> Application History
          </h3>
        )}
        <div className={styles.loadingState}>
          <i className="fa fa-spinner fa-spin"></i> Loading applications...
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {showTitle && (
        <h3 className={styles.sectionTitle}>
          <i className="fa fa-file-text-o"></i> Application History ({applications.length})
        </h3>
      )}

      {/* Filters */}
      {applications.length > 0 && (
        <div className={styles.filtersBar}>
          <div className={styles.searchWrapper}>
            <i className="fa fa-search"></i>
            <input
              type="text"
              placeholder="Search by job title or company..."
              value={filters.search}
              onChange={(e) => setFilters(f => ({ ...f, search: e.target.value }))}
              className={styles.searchInput}
            />
            {filters.search && (
              <button 
                className={styles.clearSearch}
                onClick={() => setFilters(f => ({ ...f, search: '' }))}
              >
                ×
              </button>
            )}
          </div>
          <select
            value={filters.status}
            onChange={(e) => setFilters(f => ({ ...f, status: e.target.value }))}
            className={styles.filterSelect}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="reviewed">Reviewed</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="interviewed">Interviewed</option>
            <option value="screening_cleared">Screening Cleared</option>
            <option value="rejected">Screening Not Cleared</option>
          </select>
          <select
            value={`${filters.sortBy}-${filters.sortOrder}`}
            onChange={(e) => {
              const [sortBy, sortOrder] = e.target.value.split('-');
              setFilters(f => ({ ...f, sortBy, sortOrder }));
            }}
            className={styles.filterSelect}
          >
            <option value="applied_at-desc">Newest First</option>
            <option value="applied_at-asc">Oldest First</option>
            <option value="cv_score-desc">Highest CV Score</option>
            <option value="interview_score-desc">Highest Interview</option>
          </select>
          {(filters.search || filters.status) && (
            <button
              className={styles.clearFiltersBtn}
              onClick={() => setFilters({ search: '', status: '', sortBy: 'applied_at', sortOrder: 'desc' })}
            >
              Clear Filters
            </button>
          )}
        </div>
      )}

      {/* Applications List */}
      {applications.length === 0 ? (
        <div className={styles.emptyState}>
          <i className="fa fa-inbox"></i>
          <p>No applications yet</p>
        </div>
      ) : filteredApps.length === 0 ? (
        <div className={styles.emptyState}>
          <i className="fa fa-search"></i>
          <p>No applications match the current filters</p>
        </div>
      ) : (
        <div className={styles.applicationsList}>
          {paginatedApps.map((app) => (
            <div 
              key={app.id} 
              className={styles.applicationCard} 
              data-status={normalizeStatus(app.status)}
            >
              {/* Card Header */}
              <div className={styles.applicationHeader}>
                <div className={styles.companyAvatar}>
                  {app.company_logo ? (
                    <img src={app.company_logo} alt={app.company} />
                  ) : (
                    <div className={styles.avatarFallback}>
                      {app.company?.charAt(0) || 'C'}
                    </div>
                  )}
                </div>
                <div className={styles.jobTitleWrap}>
                  <h3>{app.job_title || app.position}</h3>
                  <div className={styles.companySubtle}>at {app.company || 'Unknown Company'}</div>
                </div>
                <div className={styles.headerBadges}>
                  {editingStatus?.appId === app.id ? (
                    <select
                      value={editingStatus.newStatus || normalizeStatus(app.status)}
                      onChange={(e) => setEditingStatus({ appId: app.id, newStatus: e.target.value })}
                      className={styles.statusSelect}
                      autoFocus
                    >
                      <option value="pending">Pending</option>
                      <option value="reviewed">Reviewed</option>
                      <option value="shortlisted">Shortlisted</option>
                      <option value="interviewed">Interviewed</option>
                      <option value="screening_cleared">Screening Cleared</option>
                      <option value="rejected">Screening Not Cleared</option>
                    </select>
                  ) : (
                    <span 
                      className={`${styles.statusBadge} ${getStatusClass(app.status)}`}
                      onClick={isAdmin && onStatusChange ? () => setEditingStatus({ appId: app.id, newStatus: app.status }) : undefined}
                      style={isAdmin && onStatusChange ? { cursor: 'pointer' } : {}}
                      title={isAdmin ? 'Click to edit status' : ''}
                    >
                      {statusLabel(app.status).toUpperCase()}
                    </span>
                  )}
                  {editingStatus?.appId === app.id && (
                    <div className={styles.statusEditButtons}>
                      <button 
                        className={styles.statusSaveBtn}
                        onClick={() => handleStatusUpdate(app.id, editingStatus.newStatus)}
                      >
                        ✓
                      </button>
                      <button 
                        className={styles.statusCancelBtn}
                        onClick={() => setEditingStatus(null)}
                      >
                        ✕
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Application Details */}
              <div className={styles.applicationDetails}>
                <div className={styles.metaRow}>
                  <div className={styles.metaItem}>
                    <i className="fa fa-building"></i>
                    <span>{app.company || 'Unknown'}</span>
                  </div>
                  {app.location && (
                    <div className={styles.metaItem}>
                      <i className="fa fa-map-marker"></i>
                      <span>{app.location}</span>
                    </div>
                  )}
                  {app.job_type && (
                    <div className={styles.metaItem}>
                      <i className="fa fa-briefcase"></i>
                      <span>{app.job_type}</span>
                    </div>
                  )}
                  <div className={styles.metaItem}>
                    <i className="fa fa-calendar"></i>
                    <span>Applied {formatDate(app.applied_at)}</span>
                  </div>
                </div>
                {(app.department || app.job_type) && (
                  <div className={styles.tagsRow}>
                    {app.department && (
                      <span className={styles.chip}>
                        <i className="fa fa-sitemap"></i> {app.department}
                      </span>
                    )}
                    {app.job_type && (
                      <span className={styles.chip}>
                        <i className="fa fa-clock-o"></i> {app.job_type}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Scores and Actions */}
              <div className={styles.applicationActions}>
                <div className={styles.scoresRow}>
                  {app.cv_score !== undefined && app.cv_score !== null && (
                    <div className={styles.scorePill}>
                      <span className={styles.pillLabel}>CV Score</span>
                      <span className={styles.pillValue}>{Math.round(app.cv_score)}%</span>
                      <div className={styles.miniBar}>
                        <div style={{ width: `${app.cv_score}%`, backgroundColor: '#3b82f6' }}></div>
                      </div>
                    </div>
                  )}
                  {app.interview_score !== undefined && app.interview_score !== null && (
                    <div className={styles.scorePill}>
                      <span className={styles.pillLabel}>Interview</span>
                      <span className={styles.pillValue}>{Math.round(app.interview_score)}%</span>
                      <div className={styles.miniBar}>
                        <div style={{ width: `${app.interview_score}%`, backgroundColor: '#10b981' }}></div>
                      </div>
                    </div>
                  )}
                  {app.proctoring_score !== undefined && app.proctoring_score !== null && (
                    <div className={styles.scorePill}>
                      <span className={styles.pillLabel}>Proctoring</span>
                      <span className={styles.pillValue}>{Math.round(app.proctoring_score)}%</span>
                      <div className={styles.miniBar}>
                        <div style={{ width: `${app.proctoring_score}%`, backgroundColor: '#f59e0b' }}></div>
                      </div>
                    </div>
                  )}
                  {app.calculated_cost_usd !== undefined && app.calculated_cost_usd !== null && (
                    <div className={styles.scorePill}>
                      <span className={styles.pillLabel}>Calculated Cost</span>
                      <span className={styles.pillValue}>{formatUsd(app.calculated_cost_usd)}</span>
                    </div>
                  )}
                  {app.actual_cost_usd !== undefined && app.actual_cost_usd !== null && (
                    <div className={styles.scorePill}>
                      <span className={styles.pillLabel}>Actual Cost</span>
                      <span className={styles.pillValue}>{formatUsd(app.actual_cost_usd)}</span>
                    </div>
                  )}
                </div>

                <div className={styles.actionButtons}>
                  {onViewCV && (
                    <button
                      className={styles.cvButton}
                      onClick={() => onViewCV(app)}
                      title="View CV"
                    >
                      <i className="fa fa-file-pdf-o"></i> View CV
                    </button>
                  )}
                  {onViewDetails && (
                    <button
                      className={styles.detailsButton}
                      onClick={() => onViewDetails(app.id)}
                      title="View Details"
                    >
                      <i className="fa fa-info-circle"></i> Details
                    </button>
                  )}
                  {onViewReport && app.interview_score && (
                    <button
                      className={styles.reportButton}
                      onClick={() => onViewReport(app)}
                      title="View Report"
                    >
                      <i className="fa fa-file-text-o"></i> Report
                    </button>
                  )}
                  {isAdmin && onDeleteApplication && (
                    <button
                      className={styles.deleteButton}
                      onClick={() => onDeleteApplication(app)}
                      title="Delete Application"
                    >
                      <i className="fa fa-trash"></i>
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {filteredApps.length > 0 && totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          totalItems={filteredApps.length}
          itemsPerPage={itemsPerPage}
        />
      )}
    </div>
  );
};

export default ApplicationHistoryList;

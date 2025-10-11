import React from "react";
import styles from "../../pages/Profile.module.css";
import { Link } from "react-router-dom";

export default function ApplicationsList({
  applications,
  companies,
  companyFilter,
  statusFilter,
  setCompanyFilter,
  setStatusFilter,
  onClearFilters,
  onViewCV,
  onOpenReport,
  onGiveInterview, // Add new prop for interview action
}) {
  const filtered = applications.filter((app) => {
    const matchesCompany = companyFilter === "" || app.company.toLowerCase().includes(companyFilter.toLowerCase());
    const matchesStatus = statusFilter === "" || app.status.toLowerCase() === statusFilter.toLowerCase();
    return matchesCompany && matchesStatus;
  });
  const sorted = [...filtered].sort((a, b) => new Date(b.appliedDate) - new Date(a.appliedDate));

  // Helper function to determine which buttons to show based on status
  const getButtonsForStatus = (status) => {
    const normalizedStatus = status.toLowerCase();
    
    // Always show View CV and Details
    const baseButtons = ['viewCV', 'details'];
    
    switch (normalizedStatus) {
      case 'pending':
      case 'reviewed':
        return baseButtons; // Only View CV + Details
      
      case 'shortlisted':
        return [...baseButtons, 'giveInterview']; // View CV + Details + Give Interview
      
      case 'interviewed':
      case 'selected':
      case 'rejected':
        return [...baseButtons, 'report']; // View CV + Details + Report
      
      default:
        return baseButtons; // Fallback to basic buttons
    }
  };

  return (
    <section className={styles.applicationsSection}>
      <h2>Job Applications</h2>
      <div className={styles.applicationFilters}>
        <div className={styles.filterGroup}>
          <label htmlFor="companyFilter">Company:</label>
          <select id="companyFilter" value={companyFilter} onChange={(e) => setCompanyFilter(e.target.value)} className={styles.filterSelect}>
            <option value="">All Companies</option>
            {companies.map((company) => (
              <option key={company} value={company}>
                {company}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.filterGroup}>
          <label htmlFor="statusFilter">Status:</label>
          <select id="statusFilter" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className={styles.filterSelect}>
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="reviewed">Reviewed</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="interviewed">Interviewed</option>
            <option value="selected">Selected</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        <div className={styles.filterGroup}>
          <button onClick={onClearFilters} className={styles.clearFilters}>Clear Filters</button>
        </div>
      </div>

      <div className={styles.applicationsList}>
        {sorted.length > 0 ? (
          sorted.map((app) => {
            const statusKey = app.status.toLowerCase().replace(/\s+/g, "");
            return (
              <div key={app.id} className={styles.applicationCard} data-status={statusKey}>
                <div className={styles.applicationHeader}>
                  <div className={styles.companyAvatar}>
                    <img src={app.logo || '../android-chrome-192x192.png'} alt={app.company} />
                  </div>
                  <div className={styles.jobTitleWrap}>
                    <h3>{app.position}</h3>
                    <div className={styles.companySubtle}>at {app.company}</div>
                  </div>
                  <div className={styles.headerBadges}>
                    <span className={`${styles.statusBadge} ${styles[statusKey]}`}>{app.status}</span>
                  </div>
                </div>

                <div className={styles.applicationDetails}>
                  <div className={styles.metaRow}>
                    <div className={styles.metaItem} title={app.company}>
                      <i className="fa fa-building"></i>
                      <span>{app.company}</span>
                    </div>
                    {app.location && (
                      <div className={styles.metaItem}>
                        <i className="fa fa-map-marker"></i>
                        <span>{app.location}</span>
                      </div>
                    )}
                    {app.jobType && (
                      <div className={styles.metaItem}>
                        <i className="fa fa-briefcase"></i>
                        <span>{app.jobType}</span>
                      </div>
                    )}
                    <div className={styles.metaItem}>
                      <i className="fa fa-calendar"></i>
                      <span>Applied {new Date(app.appliedDate).toLocaleDateString()}</span>
                    </div>
                  </div>
                  {(app.department || app.jobType) && (
                    <div className={styles.tagsRow}>
                      {app.department && <span className={styles.chip} title="Department"><i className="fa fa-sitemap"></i> {app.department}</span>}
                      {app.jobType && <span className={styles.chip}><i className="fa fa-clock-o"></i> {app.jobType}</span>}
                    </div>
                  )}
                </div>

                <div className={styles.applicationActions}>
                  <div className={styles.scoresRow}>
                    {app.cvScore !== null && (
                      <div className={styles.scorePill} title="CV Match Score">
                        <span className={styles.pillLabel}>CV Score</span>
                        <span className={styles.pillValue}>{app.cvScore}%</span>
                        <div className={styles.miniBar}><div style={{ width: `${app.cvScore}%` }} /></div>
                        {app.minimum_cv_score_required && (
                          <div className={styles.scoreThreshold}>
                            <span className={styles.thresholdLabel}>Required: {app.minimum_cv_score_required}</span>
                            <span className={`${styles.passFailIndicator} ${
                              app.cvScore >= app.minimum_cv_score_required 
                                ? styles.pass 
                                : styles.fail
                            }`}>
                              {app.cvScore >= app.minimum_cv_score_required ? '✓ Pass' : '✗ Below'}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                    {app.interviewScore !== null && (
                      <div className={`${styles.scorePill} ${styles.scorePillSuccess}`} title="Interview Score">
                        <span className={styles.pillLabel}>Interview</span>
                        <span className={styles.pillValue}>{app.interviewScore}%</span>
                        <div className={`${styles.miniBar} ${styles.miniBarSuccess}`}><div style={{ width: `${app.interviewScore}%` }} /></div>
                      </div>
                    )}
                    {app.proctoringScore !== null && (
                      <div className={`${styles.scorePill} ${styles.scorePillWarning}`} title="Proctoring Score">
                        <span className={styles.pillLabel}>Proctoring</span>
                        <span className={styles.pillValue}>{app.proctoringScore}%</span>
                        <div className={`${styles.miniBar} ${styles.miniBarWarning}`}><div style={{ width: `${app.proctoringScore}%` }} /></div>
                      </div>
                    )}
                  </div>
                  {app.auto_processed && (
                    <div className={styles.autoProcessedBadge}>
                      <span className={styles.robotIcon}>🤖</span>
                      <span className={styles.autoLabel}>
                        Auto-{app.status === 'shortlisted' ? 'shortlisted' : 'rejected'}
                      </span>
                    </div>
                  )}

                  <div className={styles.actionsRight}>
                    {/* Always show View CV button */}
                    <button type="button" className={styles.ghostButton} onClick={onViewCV} aria-label="View your uploaded CV">
                      <i className="fa fa-file-pdf-o"></i> View CV
                    </button>
                    
                    {/* Always show Details button */}
                    <Link to={`/application/${app.id}`} className={styles.viewTimelineButton}>
                      <i className="fa fa-info-circle"></i> Details
                    </Link>
                    
                    {/* Status-based conditional buttons */}
                    {(() => {
                      const availableButtons = getButtonsForStatus(app.status);
                      
                      return (
                        <>
                          {/* Give Interview button for shortlisted candidates */}
                          {availableButtons.includes('giveInterview') && (
                            <button 
                              className={styles.interviewButton} 
                              onClick={() => onGiveInterview && onGiveInterview(app)}
                              title="Schedule or take interview"
                            >
                              <i className="fa fa-calendar-check-o"></i> Give Interview
                            </button>
                          )}
                          
                          {/* Report button for interviewed/selected/rejected candidates */}
                          {availableButtons.includes('report') && (
                            <button 
                              className={styles.primaryButton} 
                              onClick={() => onOpenReport(app)}
                              title="View interview report"
                            >
                              <i className="fa fa-file-text-o"></i> Report
                            </button>
                          )}
                        </>
                      );
                    })()}
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <p className={styles.noApplications}>No job applications yet.</p>
        )}
      </div>
    </section>
  );
}

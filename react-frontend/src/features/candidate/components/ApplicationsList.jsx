import React, { useState, useEffect } from "react";
import styles from "features/candidate/pages/Profile.module.css";
import { Link } from "react-router-dom";
import Pagination from "shared/components/ui/Pagination";

const DATE_RANGE_OPTIONS = [
  { value: "", label: "All Time" },
  { value: "week", label: "This Week" },
  { value: "month", label: "This Month" },
  { value: "quarter", label: "Last 3 Months" },
  { value: "halfyear", label: "Last 6 Months" },
];

const JOB_TYPE_OPTIONS = [
  { value: "", label: "All Types" },
  { value: "full-time", label: "Full-time" },
  { value: "part-time", label: "Part-time" },
  { value: "internship", label: "Internship" },
  { value: "contract", label: "Contract" },
  { value: "remote", label: "Remote" },
];

const DATE_CUTOFF_DAYS = { week: 7, month: 30, quarter: 90, halfyear: 180 };

export default function ApplicationsList({
  applications,
  companies,
  locations,
  companyFilter,
  statusFilter,
  jobTypeFilter,
  locationFilter,
  dateRangeFilter,
  setCompanyFilter,
  setStatusFilter,
  setJobTypeFilter,
  setLocationFilter,
  setDateRangeFilter,
  onClearFilters,
  onViewCV,
  onOpenReport,
  onGiveInterview,
}) {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;

  const filtered = applications.filter((app) => {
    const matchesCompany =
      companyFilter === "" ||
      app.company.toLowerCase().includes(companyFilter.toLowerCase());
    const matchesStatus =
      statusFilter === "" ||
      (app.statusKey || app.status.toLowerCase()) === statusFilter.toLowerCase();
    const matchesJobType =
      jobTypeFilter === "" ||
      (app.jobType || "").toLowerCase() === jobTypeFilter.toLowerCase();
    const matchesLocation =
      locationFilter === "" ||
      (app.location || "").toLowerCase().includes(locationFilter.toLowerCase());

    let matchesDate = true;
    if (dateRangeFilter && DATE_CUTOFF_DAYS[dateRangeFilter]) {
      const cutoff = new Date(
        Date.now() - DATE_CUTOFF_DAYS[dateRangeFilter] * 86400000
      );
      matchesDate = new Date(app.appliedDate) >= cutoff;
    }

    return matchesCompany && matchesStatus && matchesJobType && matchesLocation && matchesDate;
  });

  const sorted = [...filtered].sort(
    (a, b) => new Date(b.appliedDate) - new Date(a.appliedDate)
  );

  // Reset to page 1 whenever any filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [companyFilter, statusFilter, jobTypeFilter, locationFilter, dateRangeFilter]);

  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedApplications = sorted.slice(startIndex, startIndex + itemsPerPage);
  const totalPages = Math.ceil(sorted.length / itemsPerPage);

  const getButtonsForStatus = (statusKey) => {
    const s = String(statusKey || "").toLowerCase();
    const base = ["viewCV", "details"];
    if (s === "shortlisted") return [...base, "giveInterview"];
    if (["interviewed", "screening_cleared", "selected", "rejected"].includes(s)) return [...base, "report"];
    return base;
  };

  const hasActiveFilters =
    companyFilter || statusFilter || jobTypeFilter || locationFilter || dateRangeFilter;

  return (
    <section className={styles.applicationsSection}>
      <h2>Job Applications</h2>

      {/* ── Filters ─────────────────────────────────────────────── */}
      <div className={styles.applicationFilters}>
        {/* Row 1 */}
        <div className={styles.filterGroup}>
          <label htmlFor="companyFilter">Company</label>
          <select
            id="companyFilter"
            value={companyFilter}
            onChange={(e) => setCompanyFilter(e.target.value)}
            className={styles.filterSelect}
          >
            <option value="">All Companies</option>
            {companies.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div className={styles.filterGroup}>
          <label htmlFor="statusFilter">Status</label>
          <select
            id="statusFilter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className={styles.filterSelect}
          >
            <option value="">All Statuses</option>
            <option value="pending">Awaiting Recruiter Review</option>
            <option value="reviewed">Reviewed</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="interviewed">Interviewed</option>
            <option value="screening_cleared">Screening Cleared</option>
            <option value="rejected">Screening Not Cleared</option>
          </select>
        </div>

        <div className={styles.filterGroup}>
          <label htmlFor="jobTypeFilter">Job Type</label>
          <select
            id="jobTypeFilter"
            value={jobTypeFilter}
            onChange={(e) => setJobTypeFilter(e.target.value)}
            className={styles.filterSelect}
          >
            {JOB_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className={styles.filterGroup}>
          <label htmlFor="locationFilter">Location</label>
          <select
            id="locationFilter"
            value={locationFilter}
            onChange={(e) => setLocationFilter(e.target.value)}
            className={styles.filterSelect}
          >
            <option value="">All Locations</option>
            {(locations || []).map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>

        <div className={styles.filterGroup}>
          <label htmlFor="dateRangeFilter">Applied</label>
          <select
            id="dateRangeFilter"
            value={dateRangeFilter}
            onChange={(e) => setDateRangeFilter(e.target.value)}
            className={styles.filterSelect}
          >
            {DATE_RANGE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className={styles.filterGroup} style={{ justifyContent: "flex-end" }}>
          <button
            onClick={onClearFilters}
            className={styles.clearFilters}
            disabled={!hasActiveFilters}
            style={{ opacity: hasActiveFilters ? 1 : 0.5, cursor: hasActiveFilters ? "pointer" : "default" }}
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* Active filter summary */}
      {hasActiveFilters && (
        <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "12px" }}>
          Showing {sorted.length} of {applications.length} applications
        </p>
      )}

      {/* ── Cards ───────────────────────────────────────────────── */}
      <div className={styles.applicationsList}>
        {paginatedApplications.length > 0 ? (
          paginatedApplications.map((app) => {
            const statusKey =
              app.statusKey || app.status.toLowerCase().replace(/\s+/g, "");
            const availableButtons = getButtonsForStatus(statusKey);
            return (
              <div
                key={app.id}
                className={styles.applicationCard}
                data-status={statusKey}
              >
                <div className={styles.applicationHeader}>
                  <div className={styles.companyAvatar}>
                    <img
                      src={app.logo || "../android-chrome-192x192.png"}
                      alt={app.company}
                    />
                  </div>
                  <div className={styles.jobTitleWrap}>
                    <h3>{app.position}</h3>
                    <div className={styles.companySubtle}>at {app.company}</div>
                  </div>
                  <div className={styles.headerBadges}>
                    <span className={`${styles.statusBadge} ${styles[statusKey]}`}>
                      {app.status}
                    </span>
                  </div>
                </div>

                <div className={styles.applicationDetails}>
                  <div className={styles.metaRow}>
                    <div className={styles.metaItem} title={app.company}>
                      <i className="fa fa-building" />
                      <span>{app.company}</span>
                    </div>
                    {app.location && (
                      <div className={styles.metaItem}>
                        <i className="fa fa-map-marker" />
                        <span>{app.location}</span>
                      </div>
                    )}
                    {app.jobType && (
                      <div className={styles.metaItem}>
                        <i className="fa fa-briefcase" />
                        <span>{app.jobType}</span>
                      </div>
                    )}
                    <div className={styles.metaItem}>
                      <i className="fa fa-calendar" />
                      <span>Applied {new Date(app.appliedDate).toLocaleDateString()}</span>
                    </div>
                  </div>
                  {(app.department || app.jobType) && (
                    <div className={styles.tagsRow}>
                      {app.department && (
                        <span className={styles.chip} title="Department">
                          <i className="fa fa-sitemap" /> {app.department}
                        </span>
                      )}
                      {app.jobType && (
                        <span className={styles.chip}>
                          <i className="fa fa-clock-o" /> {app.jobType}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className={styles.applicationActions}>
                  <div className={styles.scoresRow}>
                    {app.scoringError ? (
                      <div
                        className={`${styles.scorePill} ${styles.scorePillError}`}
                        title={app.scoringErrorMessage || "CV scoring failed."}
                      >
                        <span className={styles.pillLabel}>CV Score</span>
                        <span className={styles.pillValue} style={{ color: "#d32f2f" }}>
                          <i className="fa fa-exclamation-triangle" /> Failed
                        </span>
                      </div>
                    ) : app.scoringRetrying ? (
                      <div
                        className={`${styles.scorePill} ${styles.scorePillWarning}`}
                        title={`Retrying CV scoring... (Attempt ${app.scoringRetryCount})`}
                      >
                        <span className={styles.pillLabel}>CV Score</span>
                        <span className={styles.pillValue} style={{ color: "#ed6c02" }}>
                          <i className="fa fa-refresh fa-spin" /> Retrying
                        </span>
                      </div>
                    ) : app.processingStatus && app.processingStatus !== "completed" ? (
                      <div className={styles.scorePill} title="CV scoring in progress">
                        <span className={styles.pillLabel}>CV Score</span>
                        <span className={styles.pillValue}>
                          <i className="fa fa-spinner fa-spin" /> Processing...
                        </span>
                      </div>
                    ) : app.cvScore !== null ? (
                      <div className={styles.scorePill} title="CV Match Score">
                        <span className={styles.pillLabel}>CV Score</span>
                        <span className={styles.pillValue}>{app.cvScore}%</span>
                        <div className={styles.miniBar}>
                          <div style={{ width: `${app.cvScore}%` }} />
                        </div>
                        {app.minimum_cv_score_required && (
                          <div className={styles.scoreThreshold}>
                            <span className={styles.thresholdLabel}>
                              Required: {app.minimum_cv_score_required}
                            </span>
                            <span
                              className={`${styles.passFailIndicator} ${
                                app.cvScore >= app.minimum_cv_score_required
                                  ? styles.pass
                                  : styles.fail
                              }`}
                            >
                              {app.cvScore >= app.minimum_cv_score_required ? "✓ Pass" : "✗ Below"}
                            </span>
                          </div>
                        )}
                      </div>
                    ) : null}
                    {app.interviewScore !== null && (
                      <div
                        className={`${styles.scorePill} ${styles.scorePillSuccess}`}
                        title="Interview Score"
                      >
                        <span className={styles.pillLabel}>Interview</span>
                        <span className={styles.pillValue}>{app.interviewScore}%</span>
                        <div className={`${styles.miniBar} ${styles.miniBarSuccess}`}>
                          <div style={{ width: `${app.interviewScore}%` }} />
                        </div>
                      </div>
                    )}
                    {app.proctoringScore !== null && (
                      <div
                        className={`${styles.scorePill} ${styles.scorePillWarning}`}
                        title="Proctoring Score"
                      >
                        <span className={styles.pillLabel}>Proctoring</span>
                        <span className={styles.pillValue}>{app.proctoringScore}%</span>
                        <div className={`${styles.miniBar} ${styles.miniBarWarning}`}>
                          <div style={{ width: `${app.proctoringScore}%` }} />
                        </div>
                      </div>
                    )}
                  </div>

                  <div className={styles.actionsRight}>
                    <button
                      type="button"
                      className={styles.ghostButton}
                      onClick={() => onViewCV && onViewCV(app)}
                      aria-label="View CV used for this application"
                    >
                      <i className="fa fa-file-pdf-o" /> View CV
                    </button>

                    <Link
                      to={`/application/${app.id}`}
                      className={styles.viewTimelineButton}
                    >
                      <i className="fa fa-info-circle" /> Details
                    </Link>

                    {availableButtons.includes("giveInterview") && (
                      <button
                        className={styles.interviewButton}
                        onClick={() => onGiveInterview && onGiveInterview(app)}
                        title="Schedule or take interview"
                      >
                        <i className="fa fa-calendar-check-o" /> Give Interview
                      </button>
                    )}

                    {availableButtons.includes("report") && (
                      <button
                        className={styles.primaryButton}
                        onClick={() => onOpenReport(app)}
                        title="View interview report"
                      >
                        <i className="fa fa-file-text-o" /> Report
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <p className={styles.noApplications}>
            {hasActiveFilters
              ? "No applications match the selected filters."
              : "No job applications yet."}
          </p>
        )}
      </div>

      {sorted.length > 0 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          totalItems={sorted.length}
          itemsPerPage={itemsPerPage}
        />
      )}
    </section>
  );
}

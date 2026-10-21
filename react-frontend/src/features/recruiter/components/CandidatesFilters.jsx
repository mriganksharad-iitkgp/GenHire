import React from 'react';
import styles from 'features/recruiter/pages/RecruiterDashboard.module.css';

const SCORE_THRESHOLDS = [
  { value: '', label: 'Any' },
  { value: '50', label: '50+' },
  { value: '70', label: '70+' },
  { value: '90', label: '90+' },
];

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'cv_score', label: 'CV Score (High to Low)' },
  { value: 'cv_score_asc', label: 'CV Score (Low to High)' },
  { value: 'interview_score', label: 'Interview Score (High to Low)' },
  { value: 'interview_score_asc', label: 'Interview Score (Low to High)' },
  { value: 'proctoring_score', label: 'Proctoring Score (High to Low)' },
  { value: 'proctoring_score_asc', label: 'Proctoring Score (Low to High)' },
  { value: 'combined_score', label: 'Combined Score (High to Low)' },
  { value: 'combined_score_asc', label: 'Combined Score (Low to High)' },
];

// A job title can be posted several times for different locations, so the
// position filter identifies the exact job (value = job id) and labels it
// "Title — Location".
const jobOptionLabel = (job) => {
  const title = job.title || 'Untitled role';
  return job.location ? `${title} — ${job.location}` : title;
};

const CandidatesFilters = ({
  jobPostings,
  selectedPosition,
  selectedStatus,
  selectedAccountType,
  onPositionChange,
  onStatusChange,
  onAccountTypeChange,
  onClear,
  minCvScore,
  onMinCvScoreChange,
  minInterviewScore,
  onMinInterviewScoreChange,
  minProctoringScore,
  onMinProctoringScoreChange,
  sortBy,
  onSortByChange,
}) => {
  const hasActiveFilters =
    selectedPosition ||
    selectedStatus ||
    selectedAccountType ||
    minCvScore ||
    minInterviewScore ||
    minProctoringScore;

  return (
    <div className={styles.candidateFilters}>
      <select
        className={styles.filterSelect}
        value={selectedPosition}
        onChange={(e) => onPositionChange(e.target.value)}
        aria-label="Filter by job role and location"
        title="Filter by job role and location"
      >
        <option value="">All Job Roles</option>
        {jobPostings.map((job, idx) => (
          <option key={job._id || job.id || `jobopt-${idx}`} value={job._id || job.id}>
            {jobOptionLabel(job)}
          </option>
        ))}
      </select>
      <select
        className={styles.filterSelect}
        value={selectedStatus}
        onChange={(e) => onStatusChange(e.target.value)}
      >
        <option value="">All Statuses</option>
        <option value="Pending">Pending</option>
        <option value="Reviewed">Reviewed</option>
        <option value="Shortlisted">Eligible for screening</option>
        <option value="Interviewed">Interviewed</option>
        <option value="screening_cleared">Screening Cleared</option>
        <option value="workflow:oa">Online assessment stage</option>
        <option value="workflow:company">Company interview stages</option>
        <option value="lifecycle:hired">Hired</option>
        <option value="lifecycle:withdrawn">Withdrawn</option>
        <option value="lifecycle:closed">Closed</option>
        <option value="Rejected">Not progressing</option>
      </select>
      <select
        className={styles.filterSelect}
        value={selectedAccountType}
        onChange={(e) => onAccountTypeChange(e.target.value)}
        aria-label="Filter by candidate source"
        title="Direct applicants vs candidates you invited"
      >
        <option value="">All Candidates</option>
        <option value="direct">Direct Applicants</option>
        <option value="invited">Invited Candidates</option>
      </select>
      <select
        className={styles.filterSelect}
        value={minCvScore}
        onChange={(e) => onMinCvScoreChange(e.target.value)}
        aria-label="Minimum CV score"
        title="Minimum CV score"
      >
        {SCORE_THRESHOLDS.map((opt) => (
          <option key={opt.value} value={opt.value}>CV Score: {opt.label}</option>
        ))}
      </select>
      <select
        className={styles.filterSelect}
        value={minInterviewScore}
        onChange={(e) => onMinInterviewScoreChange(e.target.value)}
        aria-label="Minimum interview score"
        title="Minimum interview score"
      >
        {SCORE_THRESHOLDS.map((opt) => (
          <option key={opt.value} value={opt.value}>Interview Score: {opt.label}</option>
        ))}
      </select>
      <select
        className={styles.filterSelect}
        value={minProctoringScore}
        onChange={(e) => onMinProctoringScoreChange(e.target.value)}
        aria-label="Minimum proctoring score"
        title="Minimum proctoring score"
      >
        {SCORE_THRESHOLDS.map((opt) => (
          <option key={opt.value} value={opt.value}>Proctoring Score: {opt.label}</option>
        ))}
      </select>
      <select
        className={styles.filterSelect}
        value={sortBy}
        onChange={(e) => onSortByChange(e.target.value)}
        aria-label="Sort applications by"
        title="Sort by"
      >
        {SORT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>Sort: {opt.label}</option>
        ))}
      </select>
      {hasActiveFilters && (
        <button className={styles.clearFiltersButton} onClick={onClear}>
          <i className="fa fa-times"></i> Clear Filters
        </button>
      )}
    </div>
  );
};

export default CandidatesFilters;

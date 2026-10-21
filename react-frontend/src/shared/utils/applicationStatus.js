// Canonical application-status helpers.
//
// Legacy jobs use screening-only statuses. Managed applications carry a
// server-derived workflow label; company outcomes are recorded by recruiters.
// The legacy positive status is "screening_cleared" and
// "rejected" is displayed as "Screening Not Cleared". The backend may still
// return the legacy value "selected" for documents created before the
// rename migration ran; normalizeStatus folds it into the canonical value.

export const normalizeStatus = (status) => {
  const value = String(status || "").toLowerCase();
  return value === "selected" ? "screening_cleared" : value;
};

export const STATUS_LABELS = {
  pending: "Pending",
  reviewed: "Reviewed",
  shortlisted: "Shortlisted",
  interviewed: "Interviewed",
  screening_cleared: "Screening Cleared",
  rejected: "Screening Not Cleared",
};

// Candidate-facing label overrides: a "pending" application is simply
// waiting on the recruiter, so say that instead of a bare "Pending".
export const CANDIDATE_STATUS_LABELS = {
  ...STATUS_LABELS,
  pending: "Awaiting Recruiter Review",
};

export const statusLabel = (status) =>
  STATUS_LABELS[normalizeStatus(status)] ||
  String(status || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

export const candidateStatusLabel = (status) =>
  CANDIDATE_STATUS_LABELS[normalizeStatus(status)] || statusLabel(status);

// "rejected" is reused for two different moments in the pipeline: a CV score
// below the job's threshold (candidate never interviewed) and a recruiter's
// post-interview "not cleared" call. Showing "Screening Not Cleared" for the
// former is misleading — no screening ever happened — so callers that have
// the application record on hand should use this instead of the plain label.
// `app` needs only interview_score and/or interviewed_at to disambiguate.
export const applicationStatusLabel = (app, { candidateFacing = false } = {}) => {
  if (app?.workflow_version_id && typeof app?.workflow_label === "string" && app.workflow_label.trim()) {
    return app.workflow_label;
  }
  const status = normalizeStatus(app?.status);
  if (status === "rejected") {
    const reachedInterview =
      app?.interview_score != null || app?.interviewScore != null || !!app?.interviewed_at;
    return reachedInterview ? "Screening Not Cleared" : "Not Shortlisted";
  }
  const labelMap = candidateFacing ? CANDIDATE_STATUS_LABELS : STATUS_LABELS;
  return labelMap[status] || statusLabel(status);
};

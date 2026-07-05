// Canonical application-status helpers.
//
// GenHire only screens candidates — it never hires — so the terminal positive
// status is "screening_cleared" (displayed as "Screening Cleared") and
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

// Shown when a job's owning recruiter has not filled in a company name.
//
// This used to be the literal "TechCorp Solutions" — a leftover seed value —
// duplicated across the job board, job details, and application views. Because
// it read like a real company, a recruiter whose company name failed to resolve
// saw someone else's brand on their own posting. A neutral label makes the gap
// obvious instead of disguising it.
export const COMPANY_NOT_SPECIFIED = "Company not specified";

/** Display name for a job/application company field, never a fake company. */
export const companyLabel = (value) =>
  String(value || "").trim() || COMPANY_NOT_SPECIFIED;

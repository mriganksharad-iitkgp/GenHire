// Centralized API layer for dashboard (recruiter & candidate)
// Endpoint functions only — the HTTP core lives in shared/api/client.js.

import { request, requestBlob } from "shared/api/client";

// Profile
export const getProfile = () => request("/profile");
export const updateProfile = (payload) =>
  request("/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
export const updateCompanyProfile = (payload) =>
  request("/company-profile", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

// CV Details
export const getCvDetails = () => request("/cv-details");
export const updateCvDetails = (payload) =>
  request("/cv-details", {
    method: "PUT",
    body: JSON.stringify(payload),
  });

// File uploads (candidate)
export const uploadCV = (file) => {
  const formData = new FormData();
  formData.append("cv_file", file); // Changed from 'cv' to 'cv_file' for new CV management system
  formData.append("is_primary", "false"); // Don't set as primary automatically
  return request("/cv/upload", { method: "POST", body: formData }); // New endpoint
};

export const uploadPhoto = (file) => {
  const formData = new FormData();
  formData.append("photo", file);
  return request("/upload-photo", { method: "POST", body: formData });
};

// File views (blob)
export const viewCV = async () => requestBlob("/view-cv", { method: "GET" });
export const viewPhoto = async () =>
  requestBlob("/view-photo", { method: "GET" });

// Jobs
export const getJobs = () => request("/jobs");
export const createJob = (payload, jdFile) => {
  if (!jdFile) {
    return request("/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  // Array fields go over as JSON strings so newline-separated values
  // (responsibilities/requirements/benefits) survive multipart form-data
  // intact instead of being mangled by a naive comma-split on the backend.
  const formData = new FormData();
  Object.entries(payload).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    if (Array.isArray(value)) {
      formData.append(key, JSON.stringify(value));
    } else if (typeof value === "object") {
      formData.append(key, JSON.stringify(value));
    } else {
      formData.append(key, value);
    }
  });
  formData.append("jd_file", jdFile);
  return request("/jobs", {
    method: "POST",
    body: formData,
  });
};
export const generateJobWithAI = (prompt, jdFile) => {
  if (!jdFile) {
    return request("/jobs/generate-ai", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    });
  }
  const formData = new FormData();
  if (prompt) formData.append("prompt", prompt);
  formData.append("jd_file", jdFile);
  return request("/jobs/generate-ai", {
    method: "POST",
    body: formData,
  });
};
export const updateJob = (jobId, payload) =>
  request(`/jobs/${jobId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
export const deleteJob = (jobId) =>
  request(`/jobs/${jobId}`, { method: "DELETE" });
export const getJdDownloadUrl = (jobId) => request(`/jobs/${jobId}/jd-download`);
export const checkCvMatchScore = (jobId, payload) =>
  request(`/jobs/${jobId}/check-cv-score`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

// Applications
export const getApplications = () => request("/applications");
export const setApplicationStatus = (applicationId, status) =>
  request(`/applications/${applicationId}/status`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });
export const getInterviewReport = (applicationId) =>
  request(`/applications/${applicationId}/interview-report`);

// Candidate: application CV view (for recruiter-owned jobs)
export const viewApplicationCV = async (applicationId) =>
  requestBlob(`/applications/${applicationId}/cv`, { method: "GET" });

// Interview management
export const startInterview = (applicationId) =>
  request("/interviews/start", {
    method: "POST",
    body: JSON.stringify({
      application_id: applicationId,
      cv_path: "uploads/cv/Data Science_resume_juanjosecarin.pdf",
      jd_path: "uploads/jd/Data_Scientist_Job_Description.pdf",
      reference_paths: [
        "uploads/reference/Artificial Intelligence, Machine Learning, and Deep Learning.pdf",
        "uploads/reference/Machine Learning For Absolute Beginners.pdf",
      ],
    }),
  });

// Centralized API layer for dashboard (recruiter & candidate)
// Keeps endpoints and headers in one place, enabling easy swap later

const API_BASE =
  process.env.REACT_APP_API_BASE || `${process.env.REACT_APP_API_URL}/api`;

function authHeaders() {
  const token = localStorage.getItem(
    process.env.REACT_APP_TOKEN_KEY || "companyxyz-token",
  );
  return {
    Authorization: `Bearer ${token}`,
  };
}

async function request(path, options = {}) {
  const headers = { ...authHeaders(), ...(options.headers || {}) };
  // Only set JSON content type when body exists and is not FormData
  if (
    options.body &&
    typeof FormData !== "undefined" &&
    !(options.body instanceof FormData)
  ) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let errMsg = "Request failed";
    try {
      const data = await res.json();
      errMsg = data.error || data.message || errMsg;
    } catch (_) {
      // ignore json parse error
    }
    const error = new Error(errMsg);
    error.status = res.status;
    throw error;
  }
  // No content
  if (res.status === 204) return null;
  return res.json();
}

async function requestBlob(path, options = {}) {
  const headers = { ...authHeaders(), ...(options.headers || {}) };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const error = new Error(`Request failed: ${res.status}`);
    error.status = res.status;
    throw error;
  }
  return res.blob();
}

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
export const createJob = (payload) =>
  request("/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
export const generateJobWithAI = (prompt) =>
  request("/jobs/generate-ai", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
export const updateJob = (jobId, payload) =>
  request(`/jobs/${jobId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
export const deleteJob = (jobId) =>
  request(`/jobs/${jobId}`, { method: "DELETE" });

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

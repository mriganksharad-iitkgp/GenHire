// Admin API Service - Centralized API layer for admin operations

import { getToken, getUser, clearSession } from "../utils/sessionManager";

function signalExpiredSession() {
  clearSession();
  window.dispatchEvent(new CustomEvent("auth:session-expired"));
}

const API_BASE =
  process.env.REACT_APP_API_BASE || `${process.env.REACT_APP_API_URL}/api`;

function authHeaders() {
  return {
    Authorization: `Bearer ${getToken()}`,
    "Content-Type": "application/json",
  };
}

async function request(path, options = {}) {
  const headers = { ...authHeaders(), ...(options.headers || {}) };

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch (_) {
    const error = new Error("Unable to reach the server. Please check your internet connection.");
    error.status = 0;
    throw error;
  }

  if (!res.ok) {
    if (res.status === 401) {
      signalExpiredSession();
      const error = new Error("Your session has expired. Please log in again.");
      error.status = 401;
      throw error;
    }
    let errMsg = "Request failed";
    try {
      const data = await res.json();
      errMsg = data.error || data.message || errMsg;
    } catch (_) {}
    const error = new Error(errMsg);
    error.status = res.status;
    throw error;
  }

  if (res.status === 204) return null;
  return res.json();
}

// Dashboard Stats
export const getStats = () => request("/admin/stats");

// Users
export const getUsers = (filters = {}) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.append(key, value);
    }
  });
  return request(`/admin/users?${params}`);
};

export const getUserDetails = (userId) => request(`/admin/users/${userId}`);

export const deleteUser = (userId) =>
  request(`/admin/users/${userId}`, { method: "DELETE" });

export const updateUserPermissions = (userId, permissions) =>
  request(`/admin/users/${userId}/permissions`, {
    method: "PUT",
    body: JSON.stringify({ permissions }),
  });

export const updateUserType = (userId, userType) =>
  request(`/admin/users/${userId}/user-type`, {
    method: "PUT",
    body: JSON.stringify({ user_type: userType }),
  });

// Candidates
export const getCandidateDetails = (candidateId) =>
  request(`/admin/candidates/${candidateId}`);

export const updateCandidate = (candidateId, data) =>
  request(`/admin/candidates/${candidateId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

// Recruiters
export const getRecruiterDetails = (recruiterId) =>
  request(`/admin/recruiters/${recruiterId}`);

export const updateRecruiter = (recruiterId, data) =>
  request(`/admin/recruiters/${recruiterId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const getPendingRecruiters = () => request("/admin/pending-recruiters");

export const verifyRecruiter = (recruiterId) =>
  request(`/admin/users/${recruiterId}/verify`, { method: "PUT" });

export const rejectRecruiter = (recruiterId, reason) =>
  request(`/admin/users/${recruiterId}/reject`, {
    method: "PUT",
    body: JSON.stringify({ reason }),
  });

// Jobs
export const getAllJobs = (filters = {}) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.append(key, value);
    }
  });
  return request(`/admin/jobs?${params}`);
};

export const getJobDetails = (jobId) => request(`/admin/jobs/${jobId}`);

export const updateJob = (jobId, data) =>
  request(`/admin/jobs/${jobId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteJob = (jobId) =>
  request(`/admin/jobs/${jobId}`, { method: "DELETE" });

// Applications
export const getApplicationDetails = (applicationId) =>
  request(`/admin/applications/${applicationId}`);

export const updateApplication = (applicationId, data) =>
  request(`/admin/applications/${applicationId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteApplication = (applicationId) =>
  request(`/admin/applications/${applicationId}`, { method: "DELETE" });

export const updateApplicationStatus = (applicationId, status) =>
  request(`/admin/applications/${applicationId}/status`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });

// CV Management
export const getCandidateCV = (candidateId) =>
  request(`/admin/candidates/${candidateId}/cv`);

export const deleteCandidateCV = (candidateId) =>
  request(`/admin/candidates/${candidateId}/cv`, { method: "DELETE" });

// System Stats
export const getSystemStats = () => request("/admin/system/stats");

// Cost Statistics (detailed usage transparency)
export const getCostStatistics = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  return request(`/admin/cost-statistics?${query.toString()}`);
};

export const getCandidateUsageSummary = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  return request(`/admin/cost-statistics/candidates/usage?${query.toString()}`);
};

export const getCandidateUsageLines = (candidateId, params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  return request(
    `/admin/cost-statistics/candidates/${candidateId}/usage-lines?${query.toString()}`,
  );
};

export const getRecruiterUsageSummary = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  return request(`/admin/cost-statistics/recruiters/usage?${query.toString()}`);
};

export const getRecruiterUsageLines = (recruiterId, params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  return request(
    `/admin/cost-statistics/recruiters/${recruiterId}/usage-lines?${query.toString()}`,
  );
};

export const getCandidateCreditSummary = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  return request(
    `/admin/cost-statistics/candidates/credit-summary?${query.toString()}`,
  );
};

export const getCandidateCreditLines = (candidateId, params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  return request(
    `/admin/cost-statistics/candidates/${candidateId}/credit-lines?${query.toString()}`,
  );
};

export const getRecruiterCreditSummary = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  return request(
    `/admin/cost-statistics/recruiters/credit-summary?${query.toString()}`,
  );
};

export const getRecruiterCreditLines = (recruiterId, params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, value);
    }
  });
  return request(
    `/admin/cost-statistics/recruiters/${recruiterId}/credit-lines?${query.toString()}`,
  );
};

// Permissions
export const getAvailablePermissions = () => request("/admin/permissions");

// Helper to get current admin info
export const getCurrentAdmin = () => {
  return getUser();
};

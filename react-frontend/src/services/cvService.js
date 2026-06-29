/**
 * CV Management Service
 * Handles all CV-related API calls
 */

import { getToken, clearSession } from "../utils/sessionManager";

const API_BASE_URL = `${process.env.REACT_APP_API_URL}/api`;

function signalExpiredSession() {
  clearSession();
  window.dispatchEvent(new CustomEvent("auth:session-expired"));
}

function throwIfExpired(response) {
  if (response.status === 401) {
    signalExpiredSession();
    const error = new Error("Your session has expired. Please log in again.");
    error.status = 401;
    throw error;
  }
}

async function safeFetch(url, options) {
  try {
    return await fetch(url, options);
  } catch (_) {
    const error = new Error("Unable to reach the server. Please check your internet connection.");
    error.status = 0;
    throw error;
  }
}

class CVService {
  async uploadCV(cvFile, isPrimary = false) {
    const token = getToken();
    if (!token) throw new Error("No authentication token found");

    const formData = new FormData();
    formData.append("cv_file", cvFile);
    formData.append("is_primary", isPrimary.toString());

    const response = await safeFetch(`${API_BASE_URL}/cv/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });

    if (!response.ok) {
      throwIfExpired(response);
      const error = await response.json();
      throw new Error(error.error || "Failed to upload CV");
    }

    return response.json();
  }

  async listCVs() {
    const token = getToken();
    if (!token) throw new Error("No authentication token found");

    const response = await safeFetch(`${API_BASE_URL}/cv/list`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      throwIfExpired(response);
      const error = await response.json();
      throw new Error(error.error || "Failed to fetch CVs");
    }

    return response.json();
  }

  async getCV(cvId) {
    const token = getToken();
    if (!token) throw new Error("No authentication token found");

    const response = await safeFetch(`${API_BASE_URL}/cv/${cvId}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      throwIfExpired(response);
      const error = await response.json();
      throw new Error(error.error || "Failed to fetch CV");
    }

    return response.json();
  }

  async deleteCV(cvId) {
    const token = getToken();
    if (!token) throw new Error("No authentication token found");

    const response = await safeFetch(`${API_BASE_URL}/cv/${cvId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      throwIfExpired(response);
      const error = await response.json();
      throw new Error(error.error || "Failed to delete CV");
    }

    return response.json();
  }

  async setPrimaryCV(cvId) {
    const token = getToken();
    if (!token) throw new Error("No authentication token found");

    const response = await safeFetch(`${API_BASE_URL}/cv/${cvId}/set-primary`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      throwIfExpired(response);
      const error = await response.json();
      throw new Error(error.error || "Failed to set primary CV");
    }

    return response.json();
  }

  async previewCV(cvId) {
    const token = getToken();
    if (!token) throw new Error("No authentication token found");

    const response = await safeFetch(`${API_BASE_URL}/cv/${cvId}/preview`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      throwIfExpired(response);
      throw new Error("Failed to preview CV");
    }

    return response.blob();
  }

  async getCVText(cvId) {
    const token = getToken();
    if (!token) throw new Error("No authentication token found");

    const response = await safeFetch(`${API_BASE_URL}/cv/${cvId}/text`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      throwIfExpired(response);
      throw new Error("Failed to fetch CV text");
    }

    return response.json();
  }
}

export default new CVService();

/**
 * CV Management Service
 * Handles all CV-related API calls
 */

const API_BASE_URL = `${process.env.REACT_APP_API_URL}/api`;

class CVService {
  /**
   * Upload a new CV PDF
   * @param {File} cvFile - CV PDF file
   * @param {boolean} isPrimary - Set as primary CV
   * @returns {Promise} Upload response
   */
  async uploadCV(cvFile, isPrimary = false) {
    const token = localStorage.getItem("companyxyz-token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    const formData = new FormData();
    formData.append("cv_file", cvFile);
    formData.append("is_primary", isPrimary.toString());

    const response = await fetch(`${API_BASE_URL}/cv/upload`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to upload CV");
    }

    return response.json();
  }

  /**
   * Get list of all CVs for current user
   * @returns {Promise} List of CVs
   */
  async listCVs() {
    const token = localStorage.getItem("companyxyz-token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    const response = await fetch(`${API_BASE_URL}/cv/list`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to fetch CVs");
    }

    return response.json();
  }

  /**
   * Get specific CV details
   * @param {string} cvId - CV ID
   * @returns {Promise} CV details
   */
  async getCV(cvId) {
    const token = localStorage.getItem("companyxyz-token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    const response = await fetch(`${API_BASE_URL}/cv/${cvId}`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to fetch CV");
    }

    return response.json();
  }

  /**
   * Delete a CV
   * @param {string} cvId - CV ID
   * @returns {Promise} Delete response
   */
  async deleteCV(cvId) {
    const token = localStorage.getItem("companyxyz-token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    const response = await fetch(`${API_BASE_URL}/cv/${cvId}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to delete CV");
    }

    return response.json();
  }

  /**
   * Set a CV as primary
   * @param {string} cvId - CV ID
   * @returns {Promise} Update response
   */
  async setPrimaryCV(cvId) {
    const token = localStorage.getItem("companyxyz-token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    const response = await fetch(`${API_BASE_URL}/cv/${cvId}/set-primary`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to set primary CV");
    }

    return response.json();
  }

  /**
   * Preview/Download CV PDF
   * @param {string} cvId - CV ID
   * @returns {Promise<Blob>} CV PDF blob
   */
  async previewCV(cvId) {
    const token = localStorage.getItem("companyxyz-token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    const response = await fetch(`${API_BASE_URL}/cv/${cvId}/preview`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error("Failed to preview CV");
    }

    return response.blob();
  }

  /**
   * Get extracted text from CV
   * @param {string} cvId - CV ID
   * @returns {Promise} Extracted text data
   */
  async getCVText(cvId) {
    const token = localStorage.getItem("companyxyz-token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    const response = await fetch(`${API_BASE_URL}/cv/${cvId}/text`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error("Failed to fetch CV text");
    }

    return response.json();
  }
}

export default new CVService();

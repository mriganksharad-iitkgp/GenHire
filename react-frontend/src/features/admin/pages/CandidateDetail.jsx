import React, { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AdminLayout from "features/admin/components/AdminLayout";
import ConfirmModal from "features/admin/components/ConfirmModal";
import ApplicationDetailModal from "features/admin/components/ApplicationDetailModal";
import IdentityCardPanel from "features/admin/components/IdentityCardPanel";
import InterviewReportModal from "features/interview/components/InterviewReportModal";
import CVDetailsModal from "features/candidate/components/CVDetailsModal";
import PracticeDetailsModal from "features/interview/components/PracticeDetailsModal";
import PracticeHistoryList from "shared/components/lists/PracticeHistoryList";
import ApplicationHistoryList from "shared/components/lists/ApplicationHistoryList";
import JDDetailsModal from "features/recruiter/components/JDDetailsModal";
import styles from "./AdminPages.module.css";
import * as adminApi from "features/admin/api/adminApi";
import { getToken } from "shared/utils/session";
import { authedFetch, API_BASE } from "shared/api/client";

const CandidateDetail = () => {
  const navigate = useNavigate();
  const { candidateId } = useParams();
  const [candidate, setCandidate] = useState(null);
  const [applications, setApplications] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);
  
  // Pagination for applications
  
  // Delete modal
  const [deleteModal, setDeleteModal] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  
  // Application detail modal
  const [selectedAppId, setSelectedAppId] = useState(null);
  const [appModalOpen, setAppModalOpen] = useState(false);
  
  // Application delete
  const [deleteAppModal, setDeleteAppModal] = useState({ open: false, app: null });
  const [deleteAppLoading, setDeleteAppLoading] = useState(false);
  
  // CV management
  const [cvDeleting, setCvDeleting] = useState(false);
  const [cvLoading, setCvLoading] = useState(false);
  
  // CV Details Modal (same as candidate sees)
  const [showCVDetailsModal, setShowCVDetailsModal] = useState(false);
  
  // Interview Report Modal
  const [reportModal, setReportModal] = useState({ open: false, report: null, cvScore: null, interviewScore: null });
  
  // Practice History
  const [practiceHistory, setPracticeHistory] = useState([]);
  const [practiceLoading, setPracticeLoading] = useState(false);
  const [selectedPractice, setSelectedPractice] = useState(null);
  const [practiceModalOpen, setPracticeModalOpen] = useState(false);
  const [practiceReportModal, setPracticeReportModal] = useState({ open: false, report: null });
  
  // JD Details Modal for practice sessions
  const [showJdDetailsModal, setShowJdDetailsModal] = useState(false);
  const [selectedJdSession, setSelectedJdSession] = useState(null);
  
  // Notifications
  const [notification, setNotification] = useState({ show: false, message: "", type: "success" });

  const showNotification = useCallback((message, type = "success") => {
    setNotification({ show: true, message, type });
    setTimeout(() => setNotification({ show: false, message: "", type: "success" }), 4000);
  }, []);

  const fetchCandidateDetails = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getCandidateDetails(candidateId);
      setCandidate(data.candidate);
      setApplications(data.applications || []);
      setStats(data.stats);
      setEditData({
        name: data.candidate.name || "",
        email: data.candidate.email || "",
        phone: data.candidate.phone || "",
        location: data.candidate.location || "",
        title: data.candidate.title || "",
        about: data.candidate.about || "",
        skills: data.candidate.skills?.join(", ") || "",
        linkedin: data.candidate.linkedin || "",
        github: data.candidate.github || "",
        portfolio: data.candidate.portfolio || "",
        experience: data.candidate.experience || "",
        education: data.candidate.education || "",
      });
    } catch (error) {
      console.error("Error fetching candidate:", error);
      showNotification(error.message || "Failed to fetch candidate details", "error");
    } finally {
      setLoading(false);
    }
  }, [candidateId, showNotification]);

  useEffect(() => {
    fetchCandidateDetails();
  }, [navigate, fetchCandidateDetails]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateCandidate(candidateId, {
        ...editData,
        skills: editData.skills.split(",").map((s) => s.trim()).filter(Boolean),
      });
      showNotification("Candidate updated successfully");
      setEditMode(false);
      fetchCandidateDetails();
    } catch (error) {
      showNotification(error.message || "Failed to update candidate", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleteLoading(true);
    try {
      await adminApi.deleteUser(candidateId);
      showNotification("Candidate deleted successfully");
      navigate("/admin/candidates");
    } catch (error) {
      showNotification(error.message || "Failed to delete candidate", "error");
    } finally {
      setDeleteLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const handleOpenApplication = (appId) => {
    setSelectedAppId(appId);
    setAppModalOpen(true);
  };

  const handleDeleteApplication = async () => {
    if (!deleteAppModal.app) return;
    setDeleteAppLoading(true);
    try {
      await adminApi.deleteApplication(deleteAppModal.app.id);
      showNotification("Application deleted successfully");
      setDeleteAppModal({ open: false, app: null });
      fetchCandidateDetails();
    } catch (error) {
      showNotification(error.message || "Failed to delete application", "error");
    } finally {
      setDeleteAppLoading(false);
    }
  };

  // Handle application status change
  const handleApplicationStatusChange = async (appId, newStatus) => {
    try {
      const token = getToken();
      const response = await authedFetch(`${API_BASE}/admin/applications/${appId}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status: newStatus })
      });
      
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || "Failed to update status");
      }
      
      showNotification(`Application status updated to ${newStatus}`);
      fetchCandidateDetails();
    } catch (error) {
      console.error("Error updating application status:", error);
      showNotification(error.message || "Failed to update status", "error");
    }
  };

  // Handle viewing CV for an application
  const handleViewApplicationCV = async (app) => {
    setCvLoading(true);
    try {
      const token = getToken();
      let url = `${API_BASE}/admin/cv/${candidateId}?token=${token}`;
      if (app.cv_id) {
        url = `${API_BASE}/cv/${app.cv_id}/preview?token=${token}`;
      }
      window.open(url, "_blank");
    } catch (error) {
      console.error("Error viewing CV:", error);
      if (candidate?.cv_details) {
        setShowCVDetailsModal(true);
      } else {
        showNotification("No CV available", "info");
      }
    } finally {
      setCvLoading(false);
    }
  };

  const handleViewCV = async () => {
    setCvLoading(true);
    try {
      const token = getToken();
      const url = `${API_BASE}/admin/cv/${candidateId}?token=${token}`;
      window.open(url, "_blank");
    } catch (error) {
      console.error("Error viewing CV:", error);
      showNotification(error.message || "Failed to view CV", "error");
    } finally {
      setCvLoading(false);
    }
  };

  const handleDeleteCV = async () => {
    if (!window.confirm("Are you sure you want to delete this candidate's CV? This action cannot be undone.")) {
      return;
    }
    setCvDeleting(true);
    try {
      await adminApi.deleteCandidateCV(candidateId);
      showNotification("CV deleted successfully");
      fetchCandidateDetails();
    } catch (error) {
      showNotification(error.message || "Failed to delete CV", "error");
    } finally {
      setCvDeleting(false);
    }
  };

  // Fetch practice history for this candidate
  const fetchPracticeHistory = useCallback(async () => {
    setPracticeLoading(true);
    try {
      const token = getToken();
      const response = await authedFetch(`${API_BASE}/admin/candidates/${candidateId}/practice-history`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setPracticeHistory(data.sessions || []);
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error(`[Admin] Practice history error:`, errorData);
      }
    } catch (error) {
      console.error("Error fetching practice history:", error);
    } finally {
      setPracticeLoading(false);
    }
  }, [candidateId]);

  // View interview report for an application
  const handleViewReport = async (app) => {
    try {
      const token = getToken();
      const url = `${API_BASE}/admin/applications/${app.id}/report`;
      const response = await authedFetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const report = await response.json();
        setReportModal({
          open: true,
          report: report,
          cvScore: app.cv_score,
          interviewScore: app.interview_score
        });
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error("[Admin] Report fetch failed:", response.status, errorData);
        showNotification(errorData.error || "Failed to load interview report", "error");
      }
    } catch (error) {
      console.error("[Admin] Error fetching report:", error);
      showNotification("Error loading interview report", "error");
    }
  };

  // View practice report by session ID (for PracticeHistoryList component)
  const handleViewPracticeReportById = async (sessionId) => {
    try {
      const token = getToken();
      const response = await authedFetch(`${API_BASE}/admin/practice/${sessionId}/report`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const report = await response.json();
        setPracticeReportModal({ open: true, report });
      } else {
        showNotification("Failed to load practice report", "error");
      }
    } catch (error) {
      console.error("Error fetching practice report:", error);
      showNotification("Error loading practice report", "error");
    }
  };

  // Handle viewing CV for practice session
  const handleViewPracticeCV = async (session) => {
    if (session.cv_id) {
      try {
        const token = getToken();
        const url = `${API_BASE}/cv/${session.cv_id}/preview?token=${token}`;
        window.open(url, '_blank');
      } catch (err) {
        console.error('Error opening CV:', err);
        showNotification('Failed to open CV', 'error');
      }
    } else if (candidate?.cv_details) {
      // Show manual CV details modal
      setShowCVDetailsModal(true);
    } else {
      showNotification('No CV available for this session', 'info');
    }
  };

  // Handle viewing JD for practice session
  const handleViewPracticeJD = (session) => {
    setSelectedJdSession(session);
    setShowJdDetailsModal(true);
  };



  // Use effect to fetch practice history
  useEffect(() => {
    if (candidateId) {
      fetchPracticeHistory();
    }
  }, [candidateId, fetchPracticeHistory]);

  if (loading) {
    return (
      <AdminLayout>
        <div className={styles.loadingContainer}>
          <div className={styles.spinner}></div>
          <p>Loading candidate details...</p>
        </div>
      </AdminLayout>
    );
  }

  if (!candidate) {
    return (
      <AdminLayout>
        <div className={styles.pageContainer}>
          <div className={styles.emptyState}>
            <div className={styles.emptyStateIcon}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            </div>
            <h3>Candidate not found</h3>
            <p>The candidate you're looking for doesn't exist or has been deleted.</p>
          </div>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className={styles.pageContainer}>
        {/* Notification */}
        {notification.show && (
          <div className={`${styles.notification} ${styles[notification.type]}`}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {notification.type === "success" ? (
                <>
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </>
              ) : (
                <>
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="15" y1="9" x2="9" y2="15"></line>
                  <line x1="9" y1="9" x2="15" y2="15"></line>
                </>
              )}
            </svg>
            <span>{notification.message}</span>
            <button onClick={() => setNotification({ show: false, message: "", type: "success" })}>×</button>
          </div>
        )}

        {/* Back Button */}
        <button className={styles.backButton} onClick={() => navigate("/admin/candidates")}>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
          Back to Candidates
        </button>

        {/* Header */}
        <div className={styles.detailHeader}>
          <div className={`${styles.detailAvatar} ${styles.candidate}`}>
            {candidate.name?.charAt(0).toUpperCase() || "C"}
          </div>
          <div className={styles.detailInfo}>
            <h1 className={styles.detailName}>{candidate.name}</h1>
            <p className={styles.detailEmail}>{candidate.email}</p>
            <div className={styles.detailBadges}>
              <span className={`${styles.detailBadge} ${styles.candidate}`}>Candidate</span>
              {candidate.email_verified && (
                <span className={`${styles.detailBadge} ${styles.verified}`}>Email Verified</span>
              )}
            </div>
          </div>
          <div className={styles.detailActions}>
            {!editMode ? (
              <>
                <button
                  className={styles.alertButton}
                  style={{ background: "#6366f1" }}
                  onClick={() => setEditMode(true)}
                >
                  Edit Profile
                </button>
                <button
                  className={styles.alertButton}
                  style={{ background: "#dc2626" }}
                  onClick={() => setDeleteModal(true)}
                >
                  Delete
                </button>
              </>
            ) : (
              <>
                <button
                  className={styles.alertButton}
                  style={{ background: "#64748b" }}
                  onClick={() => {
                    setEditMode(false);
                    setEditData({
                      name: candidate.name || "",
                      phone: candidate.phone || "",
                      location: candidate.location || "",
                      title: candidate.title || "",
                      about: candidate.about || "",
                      skills: candidate.skills?.join(", ") || "",
                    });
                  }}
                  disabled={saving}
                >
                  Cancel
                </button>
                <button
                  className={styles.alertButton}
                  style={{ background: "#10b981" }}
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? "Saving..." : "Save Changes"}
                </button>
              </>
            )}
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className={styles.statsRow}>
            <div className={styles.miniStatCard}>
              <span className={styles.miniStatValue}>{stats.total_applications}</span>
              <span className={styles.miniStatLabel}>Applications</span>
            </div>
            <div className={styles.miniStatCard}>
              <span className={styles.miniStatValue}>{stats.shortlisted}</span>
              <span className={styles.miniStatLabel}>Shortlisted</span>
            </div>
            <div className={styles.miniStatCard}>
              <span className={styles.miniStatValue}>{stats.interviewed}</span>
              <span className={styles.miniStatLabel}>Interviewed</span>
            </div>
            <div className={styles.miniStatCard}>
              <span className={styles.miniStatValue}>{stats.screening_cleared ?? stats.selected ?? 0}</span>
              <span className={styles.miniStatLabel}>Screening Cleared</span>
            </div>
            <div className={styles.miniStatCard}>
              <span className={styles.miniStatValue}>{stats.avg_cv_score || 0}</span>
              <span className={styles.miniStatLabel}>Avg CV Score</span>
            </div>
          </div>
        )}

        {/* Profile Information */}
        <div className={styles.infoCard}>
          <div className={styles.infoCardHeader}>
            <h2 className={styles.infoCardTitle}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
              Profile Information
            </h2>
          </div>
          <div className={styles.infoCardBody}>
            {editMode ? (
              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Full Name</label>
                  <input
                    type="text"
                    value={editData.name}
                    onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Email</label>
                  <input
                    type="email"
                    value={editData.email}
                    onChange={(e) => setEditData({ ...editData, email: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                    disabled
                    title="Email cannot be changed"
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Phone</label>
                  <input
                    type="text"
                    value={editData.phone}
                    onChange={(e) => setEditData({ ...editData, phone: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Location</label>
                  <input
                    type="text"
                    value={editData.location}
                    onChange={(e) => setEditData({ ...editData, location: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Job Title</label>
                  <input
                    type="text"
                    value={editData.title}
                    onChange={(e) => setEditData({ ...editData, title: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>LinkedIn</label>
                  <input
                    type="url"
                    value={editData.linkedin}
                    onChange={(e) => setEditData({ ...editData, linkedin: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                    placeholder="https://linkedin.com/in/..."
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>GitHub</label>
                  <input
                    type="url"
                    value={editData.github}
                    onChange={(e) => setEditData({ ...editData, github: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                    placeholder="https://github.com/..."
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Portfolio</label>
                  <input
                    type="url"
                    value={editData.portfolio}
                    onChange={(e) => setEditData({ ...editData, portfolio: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                    placeholder="https://yourportfolio.com"
                  />
                </div>
                <div className={styles.infoItem} style={{ gridColumn: "1 / -1" }}>
                  <label className={styles.infoLabel}>Skills (comma-separated)</label>
                  <input
                    type="text"
                    value={editData.skills}
                    onChange={(e) => setEditData({ ...editData, skills: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                    placeholder="React, Python, Node.js..."
                  />
                </div>
                <div className={styles.infoItem} style={{ gridColumn: "1 / -1" }}>
                  <label className={styles.infoLabel}>Experience</label>
                  <textarea
                    value={editData.experience}
                    onChange={(e) => setEditData({ ...editData, experience: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem", minHeight: "80px", resize: "vertical" }}
                    placeholder="Work experience details..."
                  />
                </div>
                <div className={styles.infoItem} style={{ gridColumn: "1 / -1" }}>
                  <label className={styles.infoLabel}>Education</label>
                  <textarea
                    value={editData.education}
                    onChange={(e) => setEditData({ ...editData, education: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem", minHeight: "80px", resize: "vertical" }}
                    placeholder="Education background..."
                  />
                </div>
                <div className={styles.infoItem} style={{ gridColumn: "1 / -1" }}>
                  <label className={styles.infoLabel}>About</label>
                  <textarea
                    value={editData.about}
                    onChange={(e) => setEditData({ ...editData, about: e.target.value })}
                    className={styles.searchInput}
                    style={{ padding: "0.5rem", minHeight: "100px", resize: "vertical" }}
                  />
                </div>
              </div>
            ) : (
              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Full Name</span>
                  <span className={styles.infoValue}>{candidate.name || "Not provided"}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Email</span>
                  <span className={styles.infoValue}>{candidate.email}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Phone</span>
                  <span className={styles.infoValue}>{candidate.phone || "Not provided"}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Location</span>
                  <span className={styles.infoValue}>{candidate.location || "Not provided"}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Job Title</span>
                  <span className={styles.infoValue}>{candidate.title || "Not provided"}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>LinkedIn</span>
                  <span className={styles.infoValue}>
                    {candidate.linkedin ? (
                      <a href={candidate.linkedin} target="_blank" rel="noopener noreferrer" style={{ color: "var(--admin-primary)" }}>
                        View Profile
                      </a>
                    ) : "Not provided"}
                  </span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>GitHub</span>
                  <span className={styles.infoValue}>
                    {candidate.github ? (
                      <a href={candidate.github} target="_blank" rel="noopener noreferrer" style={{ color: "var(--admin-primary)" }}>
                        View GitHub
                      </a>
                    ) : "Not provided"}
                  </span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Portfolio</span>
                  <span className={styles.infoValue}>
                    {candidate.portfolio ? (
                      <a href={candidate.portfolio} target="_blank" rel="noopener noreferrer" style={{ color: "var(--admin-primary)" }}>
                        View Portfolio
                      </a>
                    ) : "Not provided"}
                  </span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Member Since</span>
                  <span className={styles.infoValue}>{formatDate(candidate.created_at)}</span>
                </div>
                <div className={styles.infoItem} style={{ gridColumn: "1 / -1" }}>
                  <span className={styles.infoLabel}>Skills</span>
                  <span className={styles.infoValue}>
                    {candidate.skills?.length > 0 ? (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.5rem" }}>
                        {candidate.skills.map((skill, idx) => (
                          <span key={idx} style={{
                            background: "#e0e7ff",
                            color: "#4338ca",
                            padding: "0.25rem 0.75rem",
                            borderRadius: "9999px",
                            fontSize: "0.825rem",
                            fontWeight: 500
                          }}>
                            {skill}
                          </span>
                        ))}
                      </div>
                    ) : "No skills listed"}
                  </span>
                </div>
                {candidate.experience && (
                  <div className={styles.infoItem} style={{ gridColumn: "1 / -1" }}>
                    <span className={styles.infoLabel}>Experience</span>
                    <span className={styles.infoValue} style={{ whiteSpace: "pre-wrap" }}>{candidate.experience}</span>
                  </div>
                )}
                {candidate.education && (
                  <div className={styles.infoItem} style={{ gridColumn: "1 / -1" }}>
                    <span className={styles.infoLabel}>Education</span>
                    <span className={styles.infoValue} style={{ whiteSpace: "pre-wrap" }}>{candidate.education}</span>
                  </div>
                )}
                {candidate.about && (
                  <div className={styles.infoItem} style={{ gridColumn: "1 / -1" }}>
                    <span className={styles.infoLabel}>About</span>
                    <span className={styles.infoValue}>{candidate.about}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* PDF CV */}
        <div className={styles.infoCard}>
          <div className={styles.infoCardHeader}>
            <h2 className={styles.infoCardTitle}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
              </svg>
              Uploaded Resume (PDF)
            </h2>
          </div>
          <div className={styles.infoCardBody}>
            {candidate.cv_path ? (
              <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flex: 1 }}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2" style={{ width: "24px", height: "24px" }}>
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <polyline points="9 15 12 18 15 15"></polyline>
                    <line x1="12" y1="12" x2="12" y2="18"></line>
                  </svg>
                  <span style={{ color: "var(--admin-text-primary)" }}>
                    {candidate.cv_path.split(/[/\\]/).pop() || "Resume.pdf"}
                  </span>
                </div>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    onClick={handleViewCV}
                    disabled={cvLoading}
                    className={styles.alertButton}
                    style={{ background: "#6366f1", fontSize: "0.875rem", padding: "0.5rem 1rem" }}
                  >
                    {cvLoading ? (
                      "Loading..."
                    ) : (
                      <>
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: "16px", height: "16px", marginRight: "4px" }}>
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                          <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                        View CV
                      </>
                    )}
                  </button>
                  <button
                    className={styles.alertButton}
                    style={{ background: "#dc2626", fontSize: "0.875rem", padding: "0.5rem 1rem" }}
                    onClick={handleDeleteCV}
                    disabled={cvDeleting}
                  >
                    {cvDeleting ? (
                      "Deleting..."
                    ) : (
                      <>
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: "16px", height: "16px", marginRight: "4px" }}>
                          <polyline points="3 6 5 6 21 6"></polyline>
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                        Delete CV
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--admin-text-secondary)" }}>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: "24px", height: "24px" }}>
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <span>No PDF CV uploaded</span>
              </div>
            )}
          </div>
        </div>

        {/* Identity card (interview face verification reference) */}
        <IdentityCardPanel candidateId={candidateId} showNotification={showNotification} />

        {/* Profile CV (Parsed CV Data) */}
        {candidate.cv_details && Object.keys(candidate.cv_details).length > 0 && (
          <div className={styles.infoCard}>
            <div className={styles.infoCardHeader}>
              <h2 className={styles.infoCardTitle}>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
                  <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
                </svg>
                Profile CV (Parsed Data)
              </h2>
              <button
                onClick={() => setShowCVDetailsModal(true)}
                className={styles.alertButton}
                style={{ background: "#6366f1", fontSize: "0.825rem", padding: "0.375rem 0.75rem" }}
              >
                View Full Details
              </button>
            </div>
            <div className={styles.infoCardBody}>
              {/* Personal Info */}
              {candidate.cv_details.personalInfo && (
                <div style={{ marginBottom: "1.5rem" }}>
                  <h4 style={{ color: "var(--admin-text-primary)", marginBottom: "0.75rem", fontSize: "0.9rem", fontWeight: 600, borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
                    Personal Information
                  </h4>
                  <div className={styles.infoGrid} style={{ gap: "0.75rem" }}>
                    {candidate.cv_details.personalInfo.fullName && (
                      <div className={styles.infoItem}>
                        <span className={styles.infoLabel}>Full Name</span>
                        <span className={styles.infoValue}>{candidate.cv_details.personalInfo.fullName}</span>
                      </div>
                    )}
                    {candidate.cv_details.personalInfo.email && (
                      <div className={styles.infoItem}>
                        <span className={styles.infoLabel}>Email</span>
                        <span className={styles.infoValue}>{candidate.cv_details.personalInfo.email}</span>
                      </div>
                    )}
                    {candidate.cv_details.personalInfo.phone && (
                      <div className={styles.infoItem}>
                        <span className={styles.infoLabel}>Phone</span>
                        <span className={styles.infoValue}>{candidate.cv_details.personalInfo.phone}</span>
                      </div>
                    )}
                    {candidate.cv_details.personalInfo.location && (
                      <div className={styles.infoItem}>
                        <span className={styles.infoLabel}>Location</span>
                        <span className={styles.infoValue}>{candidate.cv_details.personalInfo.location}</span>
                      </div>
                    )}
                    {candidate.cv_details.personalInfo.linkedin && (
                      <div className={styles.infoItem}>
                        <span className={styles.infoLabel}>LinkedIn</span>
                        <span className={styles.infoValue}>
                          <a href={candidate.cv_details.personalInfo.linkedin} target="_blank" rel="noopener noreferrer" style={{ color: "#6366f1" }}>
                            {candidate.cv_details.personalInfo.linkedin}
                          </a>
                        </span>
                      </div>
                    )}
                    {candidate.cv_details.personalInfo.github && (
                      <div className={styles.infoItem}>
                        <span className={styles.infoLabel}>GitHub</span>
                        <span className={styles.infoValue}>
                          <a href={candidate.cv_details.personalInfo.github} target="_blank" rel="noopener noreferrer" style={{ color: "#6366f1" }}>
                            {candidate.cv_details.personalInfo.github}
                          </a>
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Professional Summary */}
              {candidate.cv_details.professionalSummary && (
                <div style={{ marginBottom: "1.5rem" }}>
                  <h4 style={{ color: "var(--admin-text-primary)", marginBottom: "0.75rem", fontSize: "0.9rem", fontWeight: 600, borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
                    Professional Summary
                  </h4>
                  <p style={{ color: "var(--admin-text-secondary)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                    {candidate.cv_details.professionalSummary}
                  </p>
                </div>
              )}

              {/* Education */}
              {candidate.cv_details.education && Array.isArray(candidate.cv_details.education) && candidate.cv_details.education.length > 0 && (
                <div style={{ marginBottom: "1.5rem" }}>
                  <h4 style={{ color: "var(--admin-text-primary)", marginBottom: "0.75rem", fontSize: "0.9rem", fontWeight: 600, borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
                    Education
                  </h4>
                  {candidate.cv_details.education.map((edu, idx) => (
                    <div key={idx} style={{ marginBottom: "1rem", padding: "0.75rem", background: "#f8fafc", borderRadius: "8px" }}>
                      <div style={{ fontWeight: 600, color: "var(--admin-text-primary)" }}>
                        {edu.degree} {edu.fieldOfStudy && `in ${edu.fieldOfStudy}`}
                      </div>
                      <div style={{ color: "var(--admin-text-secondary)", fontSize: "0.875rem" }}>
                        {edu.institution}
                      </div>
                      <div style={{ color: "#64748b", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                        {edu.startDate} - {edu.endDate || "Present"}
                        {edu.gpa && ` | GPA: ${edu.gpa}`}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Work Experience */}
              {candidate.cv_details.workExperience && Array.isArray(candidate.cv_details.workExperience) && candidate.cv_details.workExperience.length > 0 && (
                <div style={{ marginBottom: "1.5rem" }}>
                  <h4 style={{ color: "var(--admin-text-primary)", marginBottom: "0.75rem", fontSize: "0.9rem", fontWeight: 600, borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
                    Work Experience
                  </h4>
                  {candidate.cv_details.workExperience.map((exp, idx) => (
                    <div key={idx} style={{ marginBottom: "1rem", padding: "0.75rem", background: "#f8fafc", borderRadius: "8px" }}>
                      <div style={{ fontWeight: 600, color: "var(--admin-text-primary)" }}>
                        {exp.jobTitle}
                      </div>
                      <div style={{ color: "var(--admin-text-secondary)", fontSize: "0.875rem" }}>
                        {exp.company} {exp.location && `| ${exp.location}`}
                      </div>
                      <div style={{ color: "#64748b", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                        {exp.startDate} - {exp.endDate || "Present"}
                      </div>
                      {exp.responsibilities && Array.isArray(exp.responsibilities) && exp.responsibilities.length > 0 && (
                        <ul style={{ margin: "0.5rem 0 0 1.25rem", color: "var(--admin-text-secondary)", fontSize: "0.85rem" }}>
                          {exp.responsibilities.slice(0, 3).map((resp, ridx) => (
                            <li key={ridx} style={{ marginBottom: "0.25rem" }}>{typeof resp === 'string' ? resp : ''}</li>
                          ))}
                          {exp.responsibilities.length > 3 && (
                            <li style={{ color: "#64748b" }}>... +{exp.responsibilities.length - 3} more</li>
                          )}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Skills */}
              {candidate.cv_details.skills && (
                <div style={{ marginBottom: "1.5rem" }}>
                  <h4 style={{ color: "var(--admin-text-primary)", marginBottom: "0.75rem", fontSize: "0.9rem", fontWeight: 600, borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
                    Skills
                  </h4>
                  {/* Technical Skills */}
                  {candidate.cv_details.skills.technical && Array.isArray(candidate.cv_details.skills.technical) && candidate.cv_details.skills.technical.length > 0 && (
                    <div style={{ marginBottom: "0.75rem" }}>
                      <span style={{ fontSize: "0.8rem", fontWeight: 500, color: "var(--admin-text-secondary)" }}>Technical: </span>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.375rem", marginTop: "0.375rem" }}>
                        {candidate.cv_details.skills.technical.map((skill, idx) => (
                          <span key={idx} style={{ background: "#dbeafe", color: "#1d4ed8", padding: "0.2rem 0.6rem", borderRadius: "9999px", fontSize: "0.75rem", fontWeight: 500 }}>
                            {typeof skill === 'string' ? skill : skill?.name || ''}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* Soft Skills */}
                  {candidate.cv_details.skills.soft && Array.isArray(candidate.cv_details.skills.soft) && candidate.cv_details.skills.soft.length > 0 && (
                    <div style={{ marginBottom: "0.75rem" }}>
                      <span style={{ fontSize: "0.8rem", fontWeight: 500, color: "var(--admin-text-secondary)" }}>Soft Skills: </span>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.375rem", marginTop: "0.375rem" }}>
                        {candidate.cv_details.skills.soft.map((skill, idx) => (
                          <span key={idx} style={{ background: "#fef3c7", color: "#92400e", padding: "0.2rem 0.6rem", borderRadius: "9999px", fontSize: "0.75rem", fontWeight: 500 }}>
                            {typeof skill === 'string' ? skill : skill?.name || ''}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* Languages */}
                  {candidate.cv_details.skills.languages && Array.isArray(candidate.cv_details.skills.languages) && candidate.cv_details.skills.languages.length > 0 && (
                    <div>
                      <span style={{ fontSize: "0.8rem", fontWeight: 500, color: "var(--admin-text-secondary)" }}>Languages: </span>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.375rem", marginTop: "0.375rem" }}>
                        {candidate.cv_details.skills.languages.map((lang, idx) => (
                          <span key={idx} style={{ background: "#dcfce7", color: "#166534", padding: "0.2rem 0.6rem", borderRadius: "9999px", fontSize: "0.75rem", fontWeight: 500 }}>
                            {typeof lang === 'string' ? lang : lang?.name || ''}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Projects */}
              {candidate.cv_details.projects && Array.isArray(candidate.cv_details.projects) && candidate.cv_details.projects.length > 0 && (
                <div style={{ marginBottom: "1.5rem" }}>
                  <h4 style={{ color: "var(--admin-text-primary)", marginBottom: "0.75rem", fontSize: "0.9rem", fontWeight: 600, borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
                    Projects
                  </h4>
                  {candidate.cv_details.projects.slice(0, 3).map((project, idx) => (
                    <div key={idx} style={{ marginBottom: "1rem", padding: "0.75rem", background: "#f8fafc", borderRadius: "8px" }}>
                      <div style={{ fontWeight: 600, color: "var(--admin-text-primary)" }}>
                        {project.name}
                        {project.url && (
                          <a href={project.url} target="_blank" rel="noopener noreferrer" style={{ marginLeft: "0.5rem", color: "#6366f1", fontSize: "0.8rem" }}>
                            ↗ View
                          </a>
                        )}
                      </div>
                      {project.description && (
                        <p style={{ color: "var(--admin-text-secondary)", fontSize: "0.85rem", marginTop: "0.25rem", lineHeight: 1.5 }}>
                          {project.description}
                        </p>
                      )}
                      {project.technologies && Array.isArray(project.technologies) && project.technologies.length > 0 && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem", marginTop: "0.5rem" }}>
                          {project.technologies.map((tech, tidx) => (
                            <span key={tidx} style={{ background: "#e0e7ff", color: "#4338ca", padding: "0.15rem 0.5rem", borderRadius: "4px", fontSize: "0.7rem" }}>
                              {typeof tech === 'string' ? tech : tech?.name || ''}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {candidate.cv_details.projects.length > 3 && (
                    <p style={{ color: "#64748b", fontSize: "0.85rem" }}>+{candidate.cv_details.projects.length - 3} more projects</p>
                  )}
                </div>
              )}

              {/* Certifications */}
              {candidate.cv_details.certifications && Array.isArray(candidate.cv_details.certifications) && candidate.cv_details.certifications.length > 0 && (
                <div>
                  <h4 style={{ color: "var(--admin-text-primary)", marginBottom: "0.75rem", fontSize: "0.9rem", fontWeight: 600, borderBottom: "1px solid #e2e8f0", paddingBottom: "0.5rem" }}>
                    Certifications
                  </h4>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                    {candidate.cv_details.certifications.map((cert, idx) => {
                      const certName = typeof cert === 'string' ? cert : (cert?.name || cert?.credentialId || 'Certification');
                      const certIssuer = typeof cert === 'object' ? cert?.issuer : null;
                      return (
                        <div key={idx} style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#166534", padding: "0.5rem 0.75rem", borderRadius: "8px", fontSize: "0.85rem" }}>
                          <div style={{ fontWeight: 500 }}>{certName}</div>
                          {certIssuer && <div style={{ fontSize: "0.75rem", opacity: 0.8 }}>{certIssuer}</div>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Applications - Using same design as candidate portal with admin features */}
        <div className={styles.infoCard}>
          <div className={styles.infoCardBody}>
            <ApplicationHistoryList
              applications={applications}
              isLoading={loading}
              onViewDetails={handleOpenApplication}
              onViewCV={handleViewApplicationCV}
              onViewReport={handleViewReport}
              onDeleteApplication={(app) => setDeleteAppModal({ open: true, app })}
              onStatusChange={handleApplicationStatusChange}
              itemsPerPage={8}
              showTitle={true}
              isAdmin={true}
            />
          </div>
        </div>

        {/* Practice History - Using same design as candidate portal */}
        <div className={styles.infoCard}>
          <div className={styles.infoCardBody}>
            <PracticeHistoryList
              sessions={practiceHistory}
              isLoading={practiceLoading}
              onViewReport={handleViewPracticeReportById}
              onViewCV={handleViewPracticeCV}
              onViewJD={handleViewPracticeJD}
              itemsPerPage={5}
              showTitle={true}
              isAdmin={true}
            />
          </div>
        </div>

        {/* Delete Candidate Modal */}
        <ConfirmModal
          isOpen={deleteModal}
          onClose={() => setDeleteModal(false)}
          onConfirm={handleDelete}
          title="Delete Candidate"
          message={`Are you sure you want to delete ${candidate.name}? This will also delete all their applications and interview data. This action cannot be undone.`}
          confirmText="Delete"
          isLoading={deleteLoading}
        />

        {/* Delete Application Modal */}
        <ConfirmModal
          isOpen={deleteAppModal.open}
          onClose={() => setDeleteAppModal({ open: false, app: null })}
          onConfirm={handleDeleteApplication}
          title="Delete Application"
          message={`Are you sure you want to delete the application for "${deleteAppModal.app?.job_title}"? This will remove all interview data and scores. This action cannot be undone.`}
          confirmText="Delete"
          isLoading={deleteAppLoading}
        />

        {/* Application Detail Modal */}
        <ApplicationDetailModal
          isOpen={appModalOpen}
          onClose={() => {
            setAppModalOpen(false);
            setSelectedAppId(null);
          }}
          applicationId={selectedAppId}
          onUpdate={fetchCandidateDetails}
          showNotification={showNotification}
        />

        {/* Interview Report Modal */}
        <InterviewReportModal
          isOpen={reportModal.open}
          onClose={() => setReportModal({ open: false, report: null, cvScore: null, interviewScore: null })}
          report={reportModal.report}
          cvScore={reportModal.cvScore}
          interviewScore={reportModal.interviewScore}
        />

        {/* CV Details Modal (view-only, same as candidate sees) */}
        <CVDetailsModal
          isOpen={showCVDetailsModal}
          onClose={() => setShowCVDetailsModal(false)}
          cvDetails={candidate?.cv_details}
        />

        {/* Practice Details Modal */}
        <PracticeDetailsModal
          isOpen={practiceModalOpen}
          onClose={() => { setPracticeModalOpen(false); setSelectedPractice(null); }}
          session={selectedPractice}
          getRoleName={(roleId) => {
            const roles = {
              'software-engineer': 'Software Engineer',
              'data-scientist': 'Data Scientist',
              'product-manager': 'Product Manager',
              'business-analyst': 'Business Analyst',
              'fullstack-developer': 'Full Stack Developer',
              'devops-engineer': 'DevOps Engineer'
            };
            return roles[roleId] || roleId;
          }}
          getRoleIcon={(roleId) => {
            const icons = {
              'software-engineer': 'fa-code',
              'data-scientist': 'fa-line-chart',
              'product-manager': 'fa-tasks',
              'business-analyst': 'fa-briefcase',
              'fullstack-developer': 'fa-laptop',
              'devops-engineer': 'fa-server'
            };
            return icons[roleId] || 'fa-briefcase';
          }}
        />

        {/* JD Details Modal for Practice Sessions */}
        <JDDetailsModal
          isOpen={showJdDetailsModal}
          onClose={() => setShowJdDetailsModal(false)}
          session={selectedJdSession}
          getRoleName={(roleId) => {
            const roles = {
              'software-engineer': 'Software Engineer',
              'data-scientist': 'Data Scientist',
              'product-manager': 'Product Manager',
              'business-analyst': 'Business Analyst',
              'fullstack-developer': 'Full Stack Developer',
              'devops-engineer': 'DevOps Engineer'
            };
            return roles[roleId] || roleId;
          }}
          getRoleIcon={(roleId) => {
            const icons = {
              'software-engineer': 'fa-code',
              'data-scientist': 'fa-line-chart',
              'product-manager': 'fa-tasks',
              'business-analyst': 'fa-briefcase',
              'fullstack-developer': 'fa-laptop',
              'devops-engineer': 'fa-server'
            };
            return icons[roleId] || 'fa-briefcase';
          }}
        />

        {/* Practice Report Modal */}
        <InterviewReportModal
          isOpen={practiceReportModal.open}
          onClose={() => setPracticeReportModal({ open: false, report: null })}
          report={practiceReportModal.report}
          cvScore={practiceReportModal.report?.cv_score}
          interviewScore={practiceReportModal.report?.interview_score}
        />
      </div>
    </AdminLayout>
  );
};

export default CandidateDetail;

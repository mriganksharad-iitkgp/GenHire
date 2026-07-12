import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import ConfirmModal from "features/admin/components/ConfirmModal";
import styles from "./AdminPages.module.css";
import * as adminApi from "features/admin/api/adminApi";

const Verification = () => {
  const navigate = useNavigate();
  const [pendingRecruiters, setPendingRecruiters] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Action states
  const [actionLoading, setActionLoading] = useState(null); // Stores id of user being processed
  const [rejectModal, setRejectModal] = useState({ show: false, user: null, rejectReason: "" });
  const [rejectLoading, setRejectLoading] = useState(false);
  
  // Notifications
  const [notification, setNotification] = useState({ show: false, message: "", type: "success" });

  const showNotification = useCallback((message, type = "success") => {
    setNotification({ show: true, message, type });
    setTimeout(() => setNotification({ show: false, message: "", type: "success" }), 4000);
  }, []);

  const fetchPendingRecruiters = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getPendingRecruiters();
      setPendingRecruiters(data.pending_recruiters || data.recruiters || []);
    } catch (error) {
      console.error("Error fetching pending recruiters:", error);
      showNotification(error.message || "Failed to fetch pending recruiters", "error");
    } finally {
      setLoading(false);
    }
  }, [showNotification]);

  useEffect(() => {
    fetchPendingRecruiters();
  }, [navigate, fetchPendingRecruiters]);

  const handleVerify = async (recruiterId) => {
    setActionLoading(recruiterId);
    try {
      await adminApi.verifyRecruiter(recruiterId);
      showNotification("Recruiter verified successfully");
      fetchPendingRecruiters();
      window.dispatchEvent(new CustomEvent("recruiterVerificationChanged"));
    } catch (error) {
      showNotification(error.message || "Failed to verify recruiter", "error");
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async () => {
    if (!rejectModal.user) return;

    setRejectLoading(true);
    try {
      await adminApi.rejectRecruiter(rejectModal.user.id, rejectModal.rejectReason || "");
      showNotification("Recruiter rejected and removed");
      setRejectModal({ show: false, user: null, rejectReason: "" });
      fetchPendingRecruiters();
      window.dispatchEvent(new CustomEvent("recruiterVerificationChanged"));
    } catch (error) {
      showNotification(error.message || "Failed to reject recruiter", "error");
    } finally {
      setRejectLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <>
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

        {/* Header */}
        <div className={styles.pageHeader}>
          <div className={styles.pageHeaderContent}>
            <h1 className={styles.pageTitle}>Pending Verifications</h1>
            <p className={styles.pageSubtitle}>
              Review and approve recruiter registration requests
            </p>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className={styles.loadingContainer}>
            <div className={styles.spinner}></div>
            <p>Loading pending requests...</p>
          </div>
        ) : pendingRecruiters.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyStateIcon}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
              </svg>
            </div>
            <h3>All Caught Up!</h3>
            <p>There are no pending recruiter verifications at the moment.</p>
          </div>
        ) : (
          <div className={styles.verificationGrid}>
            {pendingRecruiters.map((recruiter) => (
              <div key={recruiter.id} className={styles.verificationCard}>
                <div className={styles.verificationCardHeader}>
                  <div className={`${styles.detailAvatar} ${styles.recruiter}`} style={{ width: "48px", height: "48px", fontSize: "1.2rem" }}>
                    {recruiter.name?.charAt(0).toUpperCase() || "R"}
                  </div>
                  <div className={styles.verificationCardInfo}>
                    <h3 className={styles.verificationCardName}>{recruiter.name}</h3>
                    <p className={styles.verificationCardEmail}>{recruiter.email}</p>
                  </div>
                </div>
                
                <div className={styles.verificationCardBody}>
                  <div className={styles.verificationField}>
                    <span className={styles.verificationLabel}>Company</span>
                    <span className={styles.verificationValue}>{recruiter.company_name || "Not provided"}</span>
                  </div>
                  <div className={styles.verificationField}>
                    <span className={styles.verificationLabel}>Industry</span>
                    <span className={styles.verificationValue}>{recruiter.company_industry || "Not provided"}</span>
                  </div>
                  <div className={styles.verificationField}>
                    <span className={styles.verificationLabel}>Company Size</span>
                    <span className={styles.verificationValue}>{recruiter.company_size || "Not provided"}</span>
                  </div>
                  <div className={styles.verificationField}>
                    <span className={styles.verificationLabel}>Phone</span>
                    <span className={styles.verificationValue}>{recruiter.phone || "Not provided"}</span>
                  </div>
                  <div className={styles.verificationField}>
                    <span className={styles.verificationLabel}>Website</span>
                    <span className={styles.verificationValue}>
                      {recruiter.company_website ? (
                        <a href={recruiter.company_website.startsWith("http") ? recruiter.company_website : `https://${recruiter.company_website}`} target="_blank" rel="noopener noreferrer">
                          {recruiter.company_website}
                        </a>
                      ) : "Not provided"}
                    </span>
                  </div>
                  <div className={styles.verificationField}>
                    <span className={styles.verificationLabel}>Registered</span>
                    <span className={styles.verificationValue}>{formatDate(recruiter.created_at)}</span>
                  </div>
                  {recruiter.company_description && (
                    <div className={styles.verificationField} style={{ gridColumn: "1 / -1" }}>
                      <span className={styles.verificationLabel}>About</span>
                      <span className={styles.verificationValue}>{recruiter.company_description}</span>
                    </div>
                  )}
                </div>
                
                <div className={styles.verificationCardActions}>
                  <button
                    className={`${styles.verificationButton} ${styles.approve}`}
                    onClick={() => handleVerify(recruiter.id)}
                    disabled={actionLoading === recruiter.id}
                  >
                    {actionLoading === recruiter.id ? (
                      "Processing..."
                    ) : (
                      <>
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        Approve
                      </>
                    )}
                  </button>
                  <button
                    className={`${styles.verificationButton} ${styles.reject}`}
                    onClick={() => setRejectModal({ show: true, user: recruiter, rejectReason: "" })}
                    disabled={actionLoading === recruiter.id}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="18" y1="6" x2="6" y2="18"></line>
                      <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Reject
                  </button>
                  <button
                    className={`${styles.verificationButton} ${styles.view}`}
                    onClick={() => navigate(`/admin/recruiters/${recruiter.id}`)}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                    View Details
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Reject Modal */}
        <ConfirmModal
          isOpen={rejectModal.show}
          onClose={() => setRejectModal({ show: false, user: null, rejectReason: "" })}
          onConfirm={handleReject}
          title="Reject Recruiter Application"
          message={`You are about to reject ${rejectModal.user?.name}'s registration from ${rejectModal.user?.company_name || "their company"}. The recruiter will be notified by email.`}
          confirmText="Reject Application"
          isLoading={rejectLoading}
        >
          <div style={{ marginTop: "16px" }}>
            <label style={{ display: "block", marginBottom: "6px", fontSize: "13px", fontWeight: "600", color: "var(--admin-text-secondary)" }}>
              Reason for rejection <span style={{ fontWeight: "400", color: "#9ca3af" }}>(shown to the recruiter)</span>
            </label>
            <textarea
              value={rejectModal.rejectReason || ""}
              onChange={(e) =>
                setRejectModal((prev) => ({ ...prev, rejectReason: e.target.value }))
              }
              placeholder="e.g. Incomplete company information, unverifiable credentials, duplicate account…"
              rows={3}
              style={{
                width: "100%",
                padding: "8px 12px",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                fontSize: "14px",
                resize: "vertical",
                boxSizing: "border-box",
                fontFamily: "inherit",
              }}
            />
          </div>
        </ConfirmModal>
      </div>
    </>
  );
};

export default Verification;

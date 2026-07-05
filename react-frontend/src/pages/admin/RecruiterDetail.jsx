import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AdminLayout from "../../components/admin/AdminLayout";
import ConfirmModal from "../../components/admin/ConfirmModal";
import JobDetailModal from "../../components/admin/JobDetailModal";
import JobEditModal from "../../components/JobEditModal";
import styles from "./AdminPages.module.css";
import * as adminApi from "../../services/adminApi";
import { getToken } from "../../utils/sessionManager";

const RecruiterDetail = () => {
  const navigate = useNavigate();
  const { recruiterId } = useParams();
  const [recruiter, setRecruiter] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);

  // Pagination for jobs
  const [jobPage, setJobPage] = useState(1);
  const jobsPerPage = 10;

  // Delete modal
  const [deleteModal, setDeleteModal] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Verify action
  const [verifyLoading, setVerifyLoading] = useState(false);

  // Job detail modal
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [jobModalOpen, setJobModalOpen] = useState(false);

  // Job delete modal
  const [deleteJobModal, setDeleteJobModal] = useState({
    open: false,
    job: null,
  });
  const [deleteJobLoading, setDeleteJobLoading] = useState(false);

  // Job edit modal
  const [jobEditModal, setJobEditModal] = useState({ open: false, job: null });

  // Job filters
  const [jobFilters, setJobFilters] = useState({
    search: "",
    status: "",
    sortBy: "created_at",
    sortOrder: "desc",
  });

  // Notifications
  const [notification, setNotification] = useState({
    show: false,
    message: "",
    type: "success",
  });

  const showNotification = useCallback((message, type = "success") => {
    setNotification({ show: true, message, type });
    setTimeout(
      () => setNotification({ show: false, message: "", type: "success" }),
      4000,
    );
  }, []);

  // Filter and sort jobs
  const filteredJobs = useMemo(() => {
    let result = [...jobs];

    // Search filter
    if (jobFilters.search.trim()) {
      const searchLower = jobFilters.search.toLowerCase();
      result = result.filter(
        (job) =>
          job.title?.toLowerCase().includes(searchLower) ||
          job.department?.toLowerCase().includes(searchLower) ||
          job.location?.toLowerCase().includes(searchLower),
      );
    }

    // Status filter
    if (jobFilters.status) {
      result = result.filter((job) => job.status === jobFilters.status);
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0;
      switch (jobFilters.sortBy) {
        case "title":
          comparison = (a.title || "").localeCompare(b.title || "");
          break;
        case "applicants":
          comparison = (a.applicants || 0) - (b.applicants || 0);
          break;
        case "created_at":
        default:
          const dateA = a.created_at ? new Date(a.created_at) : new Date(0);
          const dateB = b.created_at ? new Date(b.created_at) : new Date(0);
          comparison = dateA - dateB;
          break;
      }
      return jobFilters.sortOrder === "desc" ? -comparison : comparison;
    });

    return result;
  }, [jobs, jobFilters]);

  // Pagination calculations
  const totalJobPages = Math.ceil(filteredJobs.length / jobsPerPage);
  const paginatedJobs = filteredJobs.slice(
    (jobPage - 1) * jobsPerPage,
    jobPage * jobsPerPage,
  );

  const fetchRecruiterDetails = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getRecruiterDetails(recruiterId);
      setRecruiter(data.recruiter);
      setJobs(data.jobs || []);
      setStats(data.stats);
      setEditData({
        name: data.recruiter.name || "",
        phone: data.recruiter.phone || "",
        location: data.recruiter.location || "",
        company_name: data.recruiter.company_name || "",
        company_description: data.recruiter.company_description || "",
        company_website: data.recruiter.company_website || "",
        company_size: data.recruiter.company_size || "",
        company_industry: data.recruiter.company_industry || "",
        linkedin_profile: data.recruiter.linkedin_profile || "",
      });
    } catch (error) {
      console.error("Error fetching recruiter:", error);
      showNotification(
        error.message || "Failed to fetch recruiter details",
        "error",
      );
    } finally {
      setLoading(false);
    }
  }, [recruiterId, showNotification]);

  useEffect(() => {
    const user = adminApi.getCurrentAdmin();
    if (!user || (user.userType !== "admin" && user.user_type !== "admin")) {
      navigate("/login");
      return;
    }
    fetchRecruiterDetails();
  }, [navigate, fetchRecruiterDetails]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateRecruiter(recruiterId, editData);
      showNotification("Recruiter updated successfully");
      setEditMode(false);
      fetchRecruiterDetails();
    } catch (error) {
      showNotification(error.message || "Failed to update recruiter", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleVerify = async () => {
    setVerifyLoading(true);
    try {
      await adminApi.verifyRecruiter(recruiterId);
      showNotification("Recruiter verified successfully");
      fetchRecruiterDetails();
    } catch (error) {
      showNotification(error.message || "Failed to verify recruiter", "error");
    } finally {
      setVerifyLoading(false);
    }
  };

  const handleDelete = async () => {
    setDeleteLoading(true);
    try {
      await adminApi.deleteUser(recruiterId);
      showNotification("Recruiter deleted successfully");
      navigate("/admin/recruiters");
    } catch (error) {
      showNotification(error.message || "Failed to delete recruiter", "error");
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

  const handleOpenJob = (jobId) => {
    setSelectedJobId(jobId);
    setJobModalOpen(true);
  };

  const handleDeleteJob = async () => {
    if (!deleteJobModal.job) return;
    setDeleteJobLoading(true);
    try {
      await adminApi.deleteJob(deleteJobModal.job.id);
      showNotification("Job deleted successfully");
      setDeleteJobModal({ open: false, job: null });
      fetchRecruiterDetails();
    } catch (error) {
      showNotification(error.message || "Failed to delete job", "error");
    } finally {
      setDeleteJobLoading(false);
    }
  };

  const handleEditJob = async (job) => {
    // Fetch full job details for editing
    try {
      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/api/jobs/${job.id}`,
        {
          headers: {
            Authorization: `Bearer ${getToken()}`,
          },
        },
      );
      if (response.ok) {
        const jobDetails = await response.json();
        setJobEditModal({ open: true, job: jobDetails });
      } else {
        // Use basic job data if full fetch fails
        setJobEditModal({ open: true, job });
      }
    } catch (error) {
      console.error("Error fetching job details:", error);
      setJobEditModal({ open: true, job });
    }
  };

  const handleJobUpdate = async (updatedJob) => {
    try {
      await adminApi.updateJob(updatedJob._id || updatedJob.id, updatedJob);
      showNotification("Job updated successfully");
      setJobEditModal({ open: false, job: null });
      fetchRecruiterDetails();
    } catch (error) {
      showNotification(error.message || "Failed to update job", "error");
    }
  };

  if (loading) {
    return (
      <AdminLayout>
        <div className={styles.loadingContainer}>
          <div className={styles.spinner}></div>
          <p>Loading recruiter details...</p>
        </div>
      </AdminLayout>
    );
  }

  if (!recruiter) {
    return (
      <AdminLayout>
        <div className={styles.pageContainer}>
          <div className={styles.emptyState}>
            <div className={styles.emptyStateIcon}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            </div>
            <h3>Recruiter not found</h3>
            <p>
              The recruiter you're looking for doesn't exist or has been
              deleted.
            </p>
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
          <div
            className={`${styles.notification} ${styles[notification.type]}`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
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
            <button
              onClick={() =>
                setNotification({ show: false, message: "", type: "success" })
              }
            >
              ×
            </button>
          </div>
        )}

        {/* Back Button */}
        <button
          className={styles.backButton}
          onClick={() => navigate("/admin/recruiters")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
          Back to Recruiters
        </button>

        {/* Header */}
        <div className={styles.detailHeader}>
          <div className={`${styles.detailAvatar} ${styles.recruiter}`}>
            {recruiter.name?.charAt(0).toUpperCase() || "R"}
          </div>
          <div className={styles.detailInfo}>
            <h1 className={styles.detailName}>{recruiter.name}</h1>
            <p className={styles.detailEmail}>{recruiter.email}</p>
            {recruiter.company_name && (
              <p className={styles.detailEmail} style={{ fontStyle: "italic" }}>
                {recruiter.company_name}
              </p>
            )}
            <div className={styles.detailBadges}>
              <span className={`${styles.detailBadge} ${styles.recruiter}`}>
                Recruiter
              </span>
              <span
                className={`${styles.detailBadge} ${recruiter.is_verified ? styles.verified : styles.pending}`}
              >
                {recruiter.is_verified ? "Verified" : "Pending Verification"}
              </span>
            </div>
          </div>
          <div className={styles.detailActions}>
            {!recruiter.is_verified && (
              <button
                className={styles.alertButton}
                style={{ background: "#10b981" }}
                onClick={handleVerify}
                disabled={verifyLoading}
              >
                {verifyLoading ? "Verifying..." : "Verify"}
              </button>
            )}
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
                  onClick={() => setEditMode(false)}
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
              <span className={styles.miniStatValue}>{stats.total_jobs}</span>
              <span className={styles.miniStatLabel}>Total Jobs</span>
            </div>
            <div className={styles.miniStatCard}>
              <span className={styles.miniStatValue}>{stats.active_jobs}</span>
              <span className={styles.miniStatLabel}>Active Jobs</span>
            </div>
            <div className={styles.miniStatCard}>
              <span className={styles.miniStatValue}>
                {stats.total_applications}
              </span>
              <span className={styles.miniStatLabel}>Total Applications</span>
            </div>
            <div className={styles.miniStatCard}>
              <span className={styles.miniStatValue}>
                {stats.total_selected}
              </span>
              <span className={styles.miniStatLabel}>Hired</span>
            </div>
            <div className={styles.miniStatCard}>
              <span className={styles.miniStatValue}>
                {stats.conversion_rate}%
              </span>
              <span className={styles.miniStatLabel}>Conversion Rate</span>
            </div>
          </div>
        )}

        {/* Company Information */}
        <div className={styles.infoCard}>
          <div className={styles.infoCardHeader}>
            <h2 className={styles.infoCardTitle}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
              </svg>
              Company Information
            </h2>
          </div>
          <div className={styles.infoCardBody}>
            {editMode ? (
              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Contact Name</label>
                  <input
                    type="text"
                    value={editData.name}
                    onChange={(e) =>
                      setEditData({ ...editData, name: e.target.value })
                    }
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Company Name</label>
                  <input
                    type="text"
                    value={editData.company_name}
                    onChange={(e) =>
                      setEditData({ ...editData, company_name: e.target.value })
                    }
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Industry</label>
                  <input
                    type="text"
                    value={editData.company_industry}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        company_industry: e.target.value,
                      })
                    }
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Company Size</label>
                  <input
                    type="text"
                    value={editData.company_size}
                    onChange={(e) =>
                      setEditData({ ...editData, company_size: e.target.value })
                    }
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>Website</label>
                  <input
                    type="text"
                    value={editData.company_website}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        company_website: e.target.value,
                      })
                    }
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div className={styles.infoItem}>
                  <label className={styles.infoLabel}>LinkedIn</label>
                  <input
                    type="text"
                    value={editData.linkedin_profile}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        linkedin_profile: e.target.value,
                      })
                    }
                    className={styles.searchInput}
                    style={{ padding: "0.5rem" }}
                  />
                </div>
                <div
                  className={styles.infoItem}
                  style={{ gridColumn: "1 / -1" }}
                >
                  <label className={styles.infoLabel}>
                    Company Description
                  </label>
                  <textarea
                    value={editData.company_description}
                    onChange={(e) =>
                      setEditData({
                        ...editData,
                        company_description: e.target.value,
                      })
                    }
                    className={styles.searchInput}
                    style={{
                      padding: "0.5rem",
                      minHeight: "100px",
                      resize: "vertical",
                    }}
                  />
                </div>
              </div>
            ) : (
              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Contact Name</span>
                  <span className={styles.infoValue}>{recruiter.name}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Email</span>
                  <span className={styles.infoValue}>{recruiter.email}</span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Phone</span>
                  <span className={styles.infoValue}>
                    {recruiter.phone || "Not provided"}
                  </span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Company Name</span>
                  <span className={styles.infoValue}>
                    {recruiter.company_name || "Not provided"}
                  </span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Industry</span>
                  <span className={styles.infoValue}>
                    {recruiter.company_industry || "Not provided"}
                  </span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Company Size</span>
                  <span className={styles.infoValue}>
                    {recruiter.company_size || "Not provided"}
                  </span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Website</span>
                  <span className={styles.infoValue}>
                    {recruiter.company_website ? (
                      <a
                        href={
                          recruiter.company_website.startsWith("http")
                            ? recruiter.company_website
                            : `https://${recruiter.company_website}`
                        }
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {recruiter.company_website}
                      </a>
                    ) : (
                      "Not provided"
                    )}
                  </span>
                </div>
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Member Since</span>
                  <span className={styles.infoValue}>
                    {formatDate(recruiter.created_at)}
                  </span>
                </div>
                {recruiter.verified_at && (
                  <div className={styles.infoItem}>
                    <span className={styles.infoLabel}>Verified On</span>
                    <span className={styles.infoValue}>
                      {formatDate(recruiter.verified_at)}
                    </span>
                  </div>
                )}
                {recruiter.company_description && (
                  <div
                    className={styles.infoItem}
                    style={{ gridColumn: "1 / -1" }}
                  >
                    <span className={styles.infoLabel}>About Company</span>
                    <span className={styles.infoValue}>
                      {recruiter.company_description}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Job Postings */}
        <div className={styles.infoCard}>
          <div className={styles.infoCardHeader}>
            <h2 className={styles.infoCardTitle}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
              </svg>
              Job Postings ({filteredJobs.length}
              {filteredJobs.length !== jobs.length ? ` of ${jobs.length}` : ""})
            </h2>
          </div>

          {/* Filters */}
          <div
            style={{
              padding: "1rem",
              borderBottom: "1px solid #e2e8f0",
              display: "flex",
              gap: "0.75rem",
              alignItems: "center",
            }}
          >
            <input
              type="text"
              placeholder="Search jobs..."
              value={jobFilters.search}
              onChange={(e) => {
                setJobFilters({ ...jobFilters, search: e.target.value });
                setJobPage(1);
              }}
              className={styles.searchInput}
              style={{
                flex: "1",
                minWidth: "150px",
                padding: "0.5rem 0.75rem",
              }}
            />
            <select
              value={jobFilters.status}
              onChange={(e) => {
                setJobFilters({ ...jobFilters, status: e.target.value });
                setJobPage(1);
              }}
              className={styles.searchInput}
              style={{ padding: "0.5rem 0.75rem", width: "120px" }}
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="draft">Draft</option>
              <option value="paused">Paused</option>
              <option value="closed">Closed</option>
            </select>
            <select
              value={`${jobFilters.sortBy}-${jobFilters.sortOrder}`}
              onChange={(e) => {
                const [sortBy, sortOrder] = e.target.value.split("-");
                setJobFilters({ ...jobFilters, sortBy, sortOrder });
              }}
              className={styles.searchInput}
              style={{ padding: "0.5rem 0.75rem", width: "140px" }}
            >
              <option value="created_at-desc">Newest First</option>
              <option value="created_at-asc">Oldest First</option>
              <option value="title-asc">Title A-Z</option>
              <option value="title-desc">Title Z-A</option>
              <option value="applicants-desc">Most Applicants</option>
              <option value="applicants-asc">Least Applicants</option>
            </select>
            {(jobFilters.search || jobFilters.status) && (
              <button
                onClick={() => {
                  setJobFilters({
                    search: "",
                    status: "",
                    sortBy: "created_at",
                    sortOrder: "desc",
                  });
                  setJobPage(1);
                }}
                className={styles.alertButton}
                style={{
                  background: "#6b7280",
                  fontSize: "0.8rem",
                  padding: "0.4rem 0.6rem",
                }}
              >
                Clear
              </button>
            )}
          </div>

          <div style={{ overflow: "auto" }}>
            {filteredJobs.length === 0 ? (
              <div
                style={{
                  padding: "2rem",
                  textAlign: "center",
                  color: "var(--admin-text-secondary)",
                }}
              >
                {jobs.length === 0
                  ? "No job postings yet"
                  : "No jobs match your filters"}
              </div>
            ) : (
              <>
                <table className={styles.dataTable}>
                  <thead>
                    <tr>
                      <th>Job Title</th>
                      <th>Department</th>
                      <th>Status</th>
                      <th>Applicants</th>
                      <th>Interviewed</th>
                      <th>Screening Cleared</th>
                      <th>Posted</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedJobs.map((job) => (
                      <tr
                        key={job.id}
                        onClick={() => handleOpenJob(job.id)}
                        style={{ cursor: "pointer" }}
                        className={styles.clickableRow}
                      >
                        <td style={{ fontWeight: 500 }}>{job.title}</td>
                        <td>{job.department || "N/A"}</td>
                        <td>
                          <span
                            className={`${styles.tableBadge} ${styles[job.status]}`}
                          >
                            {job.status}
                          </span>
                        </td>
                        <td>{job.applicants || 0}</td>
                        <td>{job.interviewed || 0}</td>
                        <td>{job.screening_cleared ?? job.selected ?? 0}</td>
                        <td>{formatDate(job.created_at)}</td>
                        <td>
                          <div
                            style={{ display: "flex", gap: "0.5rem" }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              className={styles.actionButton}
                              title="View Details"
                              onClick={() => handleOpenJob(job.id)}
                            >
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                              >
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                              </svg>
                            </button>
                            <button
                              className={styles.actionButton}
                              title="Edit Job"
                              onClick={() => handleEditJob(job)}
                              style={{ color: "#6366f1" }}
                            >
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                              >
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                              </svg>
                            </button>
                            <button
                              className={`${styles.actionButton} ${styles.danger}`}
                              title="Delete Job"
                              onClick={() =>
                                setDeleteJobModal({ open: true, job })
                              }
                            >
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                              >
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {/* Pagination */}
                {totalJobPages > 1 && (
                  <div className={styles.pagination}>
                    <button
                      className={styles.paginationButton}
                      onClick={() => setJobPage((p) => Math.max(1, p - 1))}
                      disabled={jobPage === 1}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        style={{ width: "16px", height: "16px" }}
                      >
                        <polyline points="15 18 9 12 15 6"></polyline>
                      </svg>
                      Previous
                    </button>
                    <span className={styles.paginationInfo}>
                      Page {jobPage} of {totalJobPages} ({jobs.length} total)
                    </span>
                    <button
                      className={styles.paginationButton}
                      onClick={() =>
                        setJobPage((p) => Math.min(totalJobPages, p + 1))
                      }
                      disabled={jobPage === totalJobPages}
                    >
                      Next
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        style={{ width: "16px", height: "16px" }}
                      >
                        <polyline points="9 18 15 12 9 6"></polyline>
                      </svg>
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Delete Recruiter Modal */}
        <ConfirmModal
          isOpen={deleteModal}
          onClose={() => setDeleteModal(false)}
          onConfirm={handleDelete}
          title="Delete Recruiter"
          message={`Are you sure you want to delete ${recruiter.name}? This will also delete all their job postings and related applications. This action cannot be undone.`}
          confirmText="Delete"
          isLoading={deleteLoading}
        />

        {/* Delete Job Modal */}
        <ConfirmModal
          isOpen={deleteJobModal.open}
          onClose={() => setDeleteJobModal({ open: false, job: null })}
          onConfirm={handleDeleteJob}
          title="Delete Job Posting"
          message={`Are you sure you want to delete the job "${deleteJobModal.job?.title}"? This will remove all related applications and interview data. This action cannot be undone.`}
          confirmText="Delete"
          isLoading={deleteJobLoading}
        />

        {/* Job Detail Modal */}
        <JobDetailModal
          isOpen={jobModalOpen}
          onClose={() => {
            setJobModalOpen(false);
            setSelectedJobId(null);
          }}
          jobId={selectedJobId}
          onUpdate={fetchRecruiterDetails}
          showNotification={showNotification}
        />

        {/* Job Edit Modal */}
        <JobEditModal
          isOpen={jobEditModal.open}
          onClose={() => setJobEditModal({ open: false, job: null })}
          onJobUpdate={handleJobUpdate}
          jobData={jobEditModal.job}
        />
      </div>
    </AdminLayout>
  );
};

export default RecruiterDetail;

import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import DetailModal, { ModalSection, ModalField, ModalGrid, ModalBadge } from "./DetailModal";
import * as adminApi from "../../services/adminApi";
import styles from "./DetailModal.module.css";

const STATUS_OPTIONS = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "closed", label: "Closed" },
];

const JobDetailModal = ({
  isOpen,
  onClose,
  jobId,
  onUpdate,
  onDelete,
  showNotification,
}) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deletingApplicant, setDeletingApplicant] = useState(null);
  const [error, setError] = useState(null);

  const fetchDetails = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await adminApi.getJobDetails(jobId);
      setData(result);
      setEditData({
        title: result.job?.title || "",
        department: result.job?.department || "",
        location: result.job?.location || "",
        type: result.job?.type || "",
        experience: result.job?.experience || "",
        salary: result.job?.salary || "",
        status: result.job?.status || "draft",
        description: result.job?.description || "",
        minimum_cv_score: result.job?.minimum_cv_score || 50,
      });
    } catch (err) {
      setError(err.message || "Failed to load job details");
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (isOpen && jobId) {
      fetchDetails();
    }
  }, [isOpen, jobId, fetchDetails]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateJob(jobId, {
        ...editData,
        minimum_cv_score: parseFloat(editData.minimum_cv_score) || 50,
      });
      setEditMode(false);
      fetchDetails();
      if (onUpdate) onUpdate();
      if (showNotification) showNotification("Job updated successfully");
    } catch (err) {
      setError(err.message || "Failed to update job");
      if (showNotification) showNotification(err.message || "Failed to update job", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("Are you sure you want to delete this job? This will also delete all applications. This action cannot be undone.")) {
      return;
    }
    setDeleting(true);
    try {
      await adminApi.deleteJob(jobId);
      if (showNotification) showNotification("Job deleted successfully");
      onClose();
      if (onDelete) onDelete();
    } catch (err) {
      setError(err.message || "Failed to delete job");
      if (showNotification) showNotification(err.message || "Failed to delete job", "error");
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteApplicant = async (applicationId, applicantName) => {
    if (!window.confirm(`Are you sure you want to delete ${applicantName}'s application? This will remove all interview data and scores. This action cannot be undone.`)) {
      return;
    }
    setDeletingApplicant(applicationId);
    try {
      await adminApi.deleteApplication(applicationId);
      if (showNotification) showNotification("Application deleted successfully");
      fetchDetails(); // Refresh data
      if (onUpdate) onUpdate();
    } catch (err) {
      if (showNotification) showNotification(err.message || "Failed to delete application", "error");
    } finally {
      setDeletingApplicant(null);
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

  const getActions = () => {
    if (editMode) {
      return [
        { label: "Cancel", onClick: () => setEditMode(false), variant: "secondary" },
        { label: "Save Changes", onClick: handleSave, variant: "primary", loading: saving },
      ];
    }
    return [
      { label: "Delete", onClick: handleDelete, variant: "danger", loading: deleting },
      { label: "Edit", onClick: () => setEditMode(true), variant: "primary" },
    ];
  };

  return (
    <DetailModal
      isOpen={isOpen}
      onClose={onClose}
      title="Job Details"
      subtitle={data?.job?.company ? `Company: ${data.job.company}` : undefined}
      size="large"
      actions={loading ? [] : getActions()}
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: "2rem" }}>
          <div className={styles.buttonSpinner} style={{ width: 32, height: 32, margin: "0 auto" }}></div>
          <p style={{ marginTop: "1rem", color: "#64748b" }}>Loading job details...</p>
        </div>
      ) : error ? (
        <div style={{ textAlign: "center", padding: "2rem", color: "#dc2626" }}>
          <p>{error}</p>
          <button onClick={fetchDetails} style={{ marginTop: "1rem" }}>Retry</button>
        </div>
      ) : (
        <>
          {/* Status Section */}
          <ModalSection title="Status & Settings">
            <ModalGrid columns={3}>
              <ModalField
                label="Status"
                value={editMode ? editData.status : data.job?.status}
                type="select"
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, status: val })}
                options={STATUS_OPTIONS}
              />
              <ModalField
                label="Minimum CV Score"
                value={editMode ? editData.minimum_cv_score : `${data.job?.minimum_cv_score || 50}%`}
                type="number"
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, minimum_cv_score: val })}
              />
              <div>
                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                  Current Status
                </span>
                <div style={{ marginTop: "0.5rem" }}>
                  <ModalBadge variant={data.job?.status}>{data.job?.status || "draft"}</ModalBadge>
                </div>
              </div>
            </ModalGrid>
          </ModalSection>

          {/* Basic Info */}
          <ModalSection title="Basic Information">
            <ModalGrid columns={2}>
              <ModalField
                label="Job Title"
                value={editData.title}
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, title: val })}
              />
              <ModalField
                label="Department"
                value={editData.department}
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, department: val })}
              />
              <ModalField
                label="Location"
                value={editData.location}
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, location: val })}
              />
              <ModalField
                label="Type"
                value={editData.type}
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, type: val })}
              />
              <ModalField
                label="Experience"
                value={editData.experience}
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, experience: val })}
              />
              <ModalField
                label="Salary"
                value={editData.salary}
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, salary: val })}
              />
            </ModalGrid>
          </ModalSection>

          {/* Statistics */}
          <ModalSection title="Application Statistics">
            <ModalGrid columns={6}>
              <ModalField label="Total" value={data.stats?.total || 0} />
              <ModalField label="Pending" value={data.stats?.pending || 0} />
              <ModalField label="Shortlisted" value={data.stats?.shortlisted || 0} />
              <ModalField label="Interviewed" value={data.stats?.interviewed || 0} />
              <ModalField label="Screening Cleared" value={data.stats?.screening_cleared ?? data.stats?.selected ?? 0} />
              <ModalField label="Rejected" value={data.stats?.rejected || 0} />
            </ModalGrid>
          </ModalSection>

          {/* Applicants List */}
          {data.applicants && data.applicants.length > 0 && (
            <ModalSection title={`Applicants (${data.applicants.length})`} collapsible defaultOpen>
              <div style={{ maxHeight: "300px", overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: "8px" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", position: "sticky", top: 0 }}>
                      <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: 600, color: "#475569" }}>Name</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: 600, color: "#475569" }}>Email</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: 600, color: "#475569" }}>Status</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: 600, color: "#475569" }}>CV Score</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: 600, color: "#475569" }}>Interview</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: 600, color: "#475569" }}>Applied</th>
                      <th style={{ padding: "0.75rem", textAlign: "center", fontWeight: 600, color: "#475569" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.applicants.map((applicant) => (
                      <tr 
                        key={applicant.id} 
                        style={{ borderTop: "1px solid #e2e8f0", cursor: "pointer" }}
                        onClick={() => {
                          if (applicant.candidate_id) {
                            onClose();
                            navigate(`/admin/candidates/${applicant.candidate_id}`);
                          }
                        }}
                        onMouseOver={(e) => e.currentTarget.style.background = "#f8fafc"}
                        onMouseOut={(e) => e.currentTarget.style.background = "transparent"}
                      >
                        <td style={{ padding: "0.75rem", fontWeight: 500, color: "#6366f1" }}>{applicant.name}</td>
                        <td style={{ padding: "0.75rem", color: "#64748b" }}>{applicant.email}</td>
                        <td style={{ padding: "0.75rem" }}>
                          <ModalBadge variant={applicant.status}>{applicant.status}</ModalBadge>
                        </td>
                        <td style={{ padding: "0.75rem" }}>{applicant.cv_score ? `${applicant.cv_score}%` : "N/A"}</td>
                        <td style={{ padding: "0.75rem" }}>{applicant.interview_score ? `${applicant.interview_score}%` : "N/A"}</td>
                        <td style={{ padding: "0.75rem", color: "#64748b" }}>{formatDate(applicant.applied_at)}</td>
                        <td style={{ padding: "0.75rem", textAlign: "center" }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteApplicant(applicant.application_id || applicant.id, applicant.name);
                            }}
                            disabled={deletingApplicant === (applicant.application_id || applicant.id)}
                            style={{
                              background: "none",
                              border: "none",
                              color: deletingApplicant === applicant.application_id ? "#9ca3af" : "#dc2626",
                              cursor: deletingApplicant === applicant.application_id ? "not-allowed" : "pointer",
                              padding: "0.375rem",
                              borderRadius: "4px",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              transition: "background 0.15s"
                            }}
                            onMouseOver={(e) => e.currentTarget.style.background = "#fef2f2"}
                            onMouseOut={(e) => e.currentTarget.style.background = "none"}
                            title="Delete Application"
                          >
                            {deletingApplicant === applicant.application_id ? (
                              <span style={{ fontSize: "0.75rem" }}>...</span>
                            ) : (
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: "16px", height: "16px" }}>
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                              </svg>
                            )}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ModalSection>
          )}

          {/* Description */}
          <ModalSection title="Job Description">
            <ModalField
              label="Description"
              value={editData.description}
              type="textarea"
              editable={editMode}
              onChange={(val) => setEditData({ ...editData, description: val })}
            />
          </ModalSection>

          {/* Skills & Requirements (view only) */}
          {!editMode && data.job?.skills?.length > 0 && (
            <ModalSection title="Required Skills" collapsible>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                {data.job.skills.map((skill, idx) => (
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
            </ModalSection>
          )}

          {/* Meta Info */}
          <ModalSection title="Metadata">
            <ModalGrid columns={2}>
              <ModalField label="Job ID" value={data.job?.id} />
              <ModalField label="Created By" value={data.recruiter?.name || "Unknown"} />
              <ModalField label="Created At" value={formatDate(data.job?.created_at)} />
              <ModalField label="Deadline" value={formatDate(data.job?.deadline)} />
            </ModalGrid>
          </ModalSection>
        </>
      )}
    </DetailModal>
  );
};

export default JobDetailModal;

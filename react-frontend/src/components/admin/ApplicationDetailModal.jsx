import React, { useState, useEffect, useCallback } from "react";
import DetailModal, { ModalSection, ModalField, ModalGrid, ModalBadge } from "./DetailModal";
import * as adminApi from "../../services/adminApi";
import styles from "./DetailModal.module.css";

const STATUS_OPTIONS = [
  { value: "pending", label: "Pending" },
  { value: "reviewed", label: "Reviewed" },
  { value: "shortlisted", label: "Shortlisted" },
  { value: "interviewed", label: "Interviewed" },
  { value: "selected", label: "Selected" },
  { value: "rejected", label: "Rejected" },
];

const ApplicationDetailModal = ({
  isOpen,
  onClose,
  applicationId,
  onUpdate,
  onDelete,
  showNotification,
}) => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);

  const fetchDetails = useCallback(async () => {
    if (!applicationId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await adminApi.getApplicationDetails(applicationId);
      setData(result);
      setEditData({
        status: result.application?.status || "pending",
        admin_notes: result.application?.admin_notes || "",
        cv_score: result.application?.cv_score || "",
        interview_score: result.application?.interview_score || "",
      });
    } catch (err) {
      setError(err.message || "Failed to load application details");
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    if (isOpen && applicationId) {
      fetchDetails();
    }
  }, [isOpen, applicationId, fetchDetails]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminApi.updateApplication(applicationId, {
        ...editData,
        cv_score: editData.cv_score ? parseFloat(editData.cv_score) : null,
        interview_score: editData.interview_score ? parseFloat(editData.interview_score) : null,
      });
      setEditMode(false);
      fetchDetails();
      if (onUpdate) onUpdate();
      if (showNotification) showNotification("Application updated successfully");
    } catch (err) {
      setError(err.message || "Failed to update application");
      if (showNotification) showNotification(err.message || "Failed to update application", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm("Are you sure you want to delete this application? This action cannot be undone.")) {
      return;
    }
    setDeleting(true);
    try {
      await adminApi.deleteApplication(applicationId);
      if (showNotification) showNotification("Application deleted successfully");
      onClose();
      if (onDelete) onDelete();
    } catch (err) {
      setError(err.message || "Failed to delete application");
      if (showNotification) showNotification(err.message || "Failed to delete application", "error");
    } finally {
      setDeleting(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatScore = (score) => {
    if (score === null || score === undefined) return "N/A";
    return `${Math.round(score)}%`;
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
      title="Application Details"
      subtitle={data?.job?.title ? `For: ${data.job.title}` : undefined}
      size="large"
      actions={loading ? [] : getActions()}
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: "2rem" }}>
          <div className={styles.buttonSpinner} style={{ width: 32, height: 32, margin: "0 auto" }}></div>
          <p style={{ marginTop: "1rem", color: "#64748b" }}>Loading application details...</p>
        </div>
      ) : error ? (
        <div style={{ textAlign: "center", padding: "2rem", color: "#dc2626" }}>
          <p>{error}</p>
          <button onClick={fetchDetails} style={{ marginTop: "1rem" }}>Retry</button>
        </div>
      ) : (
        <>
          {/* Status Section */}
          <ModalSection title="Status & Scores">
            <ModalGrid columns={3}>
              <ModalField
                label="Status"
                value={editMode ? editData.status : data.application?.status}
                type="select"
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, status: val })}
                options={STATUS_OPTIONS}
              />
              <ModalField
                label="CV Score"
                value={editMode ? editData.cv_score : formatScore(data.application?.cv_score)}
                type="number"
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, cv_score: val })}
              />
              <ModalField
                label="Interview Score"
                value={editMode ? editData.interview_score : formatScore(data.application?.interview_score)}
                type="number"
                editable={editMode}
                onChange={(val) => setEditData({ ...editData, interview_score: val })}
              />
            </ModalGrid>
            {!editMode && (
              <div style={{ marginTop: "1rem" }}>
                <ModalBadge variant={data.application?.status}>
                  {data.application?.status || "pending"}
                </ModalBadge>
              </div>
            )}
          </ModalSection>

          {/* Candidate Info */}
          <ModalSection title="Candidate Information">
            <ModalGrid columns={2}>
              <ModalField label="Name" value={data.candidate?.name} />
              <ModalField label="Email" value={data.candidate?.email} />
              <ModalField label="Phone" value={data.candidate?.phone} />
              <ModalField label="Candidate ID" value={data.candidate?.id} />
            </ModalGrid>
          </ModalSection>

          {/* Job Info */}
          <ModalSection title="Job Information">
            <ModalGrid columns={2}>
              <ModalField label="Job Title" value={data.job?.title} />
              <ModalField label="Department" value={data.job?.department} />
              <ModalField label="Company" value={data.job?.company || data.recruiter?.company_name} />
              <ModalField label="Recruiter" value={data.recruiter?.name} />
            </ModalGrid>
          </ModalSection>

          {/* Application Details */}
          <ModalSection title="Application Details">
            <ModalGrid columns={2}>
              <ModalField label="Applied At" value={formatDate(data.application?.applied_at)} />
              <ModalField label="Last Updated" value={formatDate(data.application?.updated_at)} />
              <ModalField label="Interview Date" value={formatDate(data.application?.interview_date)} />
              <ModalField label="Interview Completed" value={data.application?.interview_completed ? "Yes" : "No"} />
            </ModalGrid>
          </ModalSection>

          {/* CV Score Breakdown */}
          {data.application?.cv_score_breakdown && (
            <ModalSection title="CV Score Breakdown" collapsible>
              <ModalGrid columns={2}>
                {Object.entries(data.application.cv_score_breakdown).map(([key, value]) => (
                  <ModalField key={key} label={key.replace(/_/g, " ")} value={formatScore(value)} />
                ))}
              </ModalGrid>
            </ModalSection>
          )}

          {/* Cover Letter */}
          {data.application?.cover_letter && (
            <ModalSection title="Cover Letter" collapsible>
              <div style={{ 
                background: "#f8fafc", 
                padding: "1rem", 
                borderRadius: "8px",
                whiteSpace: "pre-wrap",
                fontSize: "0.9rem",
                lineHeight: "1.6"
              }}>
                {data.application.cover_letter}
              </div>
            </ModalSection>
          )}

          {/* Admin Notes */}
          <ModalSection title="Admin Notes">
            <ModalField
              label="Notes"
              value={editData.admin_notes}
              type="textarea"
              editable={editMode}
              onChange={(val) => setEditData({ ...editData, admin_notes: val })}
            />
          </ModalSection>
        </>
      )}
    </DetailModal>
  );
};

export default ApplicationDetailModal;

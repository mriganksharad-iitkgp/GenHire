import React, { useCallback, useEffect, useRef, useState } from "react";
import * as adminApi from "features/admin/api/adminApi";
import ConfirmModal from "features/admin/components/ConfirmModal";
import styles from "features/admin/pages/AdminPages.module.css";

/**
 * Admin view of a candidate's identity card. Candidates can upload their card
 * exactly once; this panel is the only place it can be replaced or reset.
 */
const IdentityCardPanel = ({ candidateId, showNotification }) => {
  const [imageUrl, setImageUrl] = useState(null);
  const [hasCard, setHasCard] = useState(null); // null = loading
  const [working, setWorking] = useState(false);
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const fileInputRef = useRef(null);
  const objectUrlRef = useRef(null);

  const loadCard = useCallback(async () => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    try {
      const blob = await adminApi.getCandidateIdentityCardBlob(candidateId);
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      setImageUrl(url);
      setHasCard(true);
    } catch (err) {
      setImageUrl(null);
      setHasCard(false);
    }
  }, [candidateId]);

  useEffect(() => {
    loadCard();
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, [loadCard]);

  const handleReplaceSelected = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setWorking(true);
    try {
      await adminApi.replaceCandidateIdentityCard(candidateId, file);
      showNotification?.("Identity card replaced");
      await loadCard();
    } catch (err) {
      showNotification?.(err.message || "Failed to replace identity card", "error");
    } finally {
      setWorking(false);
    }
  };

  const handleReset = async () => {
    setWorking(true);
    try {
      await adminApi.resetCandidateIdentityCard(candidateId);
      showNotification?.("Identity card removed — the candidate can upload a new one");
      setResetModalOpen(false);
      await loadCard();
    } catch (err) {
      showNotification?.(err.message || "Failed to remove identity card", "error");
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className={styles.infoCard}>
      <div className={styles.infoCardHeader}>
        <h2 className={styles.infoCardTitle}>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="4" width="20" height="16" rx="2"></rect>
            <circle cx="8.5" cy="11" r="2.5"></circle>
            <path d="M14 9h5M14 13h5M4.5 18c.7-1.8 2.2-3 4-3s3.3 1.2 4 3"></path>
          </svg>
          Identity Card
        </h2>
      </div>
      <div className={styles.infoCardBody}>
        {hasCard === null && <span style={{ color: "var(--admin-text-secondary)" }}>Loading…</span>}

        {hasCard === false && (
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <span style={{ color: "var(--admin-text-secondary)" }}>
              No identity card on file — the candidate will be asked to upload
              one before their next interview.
            </span>
            <button
              className={styles.alertButton}
              style={{ background: "#6366f1", fontSize: "0.875rem", padding: "0.5rem 1rem" }}
              onClick={() => fileInputRef.current?.click()}
              disabled={working}
            >
              Upload on candidate's behalf
            </button>
          </div>
        )}

        {hasCard && (
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "flex-start" }}>
            {imageUrl && (
              <img
                src={imageUrl}
                alt="Candidate identity card"
                style={{ maxWidth: "280px", maxHeight: "180px", borderRadius: "8px", border: "1px solid var(--admin-border, #e5e7eb)" }}
              />
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <button
                className={styles.alertButton}
                style={{ background: "#6366f1", fontSize: "0.875rem", padding: "0.5rem 1rem" }}
                onClick={() => fileInputRef.current?.click()}
                disabled={working}
              >
                {working ? "Working…" : "Replace identity card"}
              </button>
              <button
                className={styles.alertButton}
                style={{ background: "#dc2626", fontSize: "0.875rem", padding: "0.5rem 1rem" }}
                onClick={() => setResetModalOpen(true)}
                disabled={working}
              >
                Remove (candidate re-uploads)
              </button>
            </div>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style={{ display: "none" }}
          onChange={handleReplaceSelected}
        />
      </div>

      <ConfirmModal
        isOpen={resetModalOpen}
        onClose={() => setResetModalOpen(false)}
        onConfirm={handleReset}
        title="Remove identity card?"
        message="The stored card will be deleted and the candidate will be able to upload a new one. They cannot start interviews until they do."
        confirmText="Remove card"
        isLoading={working}
      />
    </div>
  );
};

export default IdentityCardPanel;

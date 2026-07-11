import React, { useEffect, useRef, useState } from "react";
import {
  getIdentityCardStatus,
  uploadIdentityCard,
  viewIdentityCard,
} from "features/candidate/api/identityCardApi";
import styles from "./IdentityCardUpload.module.css";

/**
 * One-time identity-card upload. The card is required before any real
 * interview (the capture at interview start is matched against it), can be
 * uploaded exactly once, and after that only an administrator can change it.
 */
const IdentityCardUpload = ({ showToast }) => {
  const [status, setStatus] = useState(null); // null = loading
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    getIdentityCardStatus()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) setStatus({ uploaded: false, locked: false, error: true });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!status?.uploaded) return undefined;
    let objectUrl = null;
    viewIdentityCard()
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      })
      .catch(() => {});
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [status?.uploaded]);

  const handleUpload = async () => {
    if (!selectedFile || uploading) return;
    setUploading(true);
    try {
      const result = await uploadIdentityCard(selectedFile);
      setStatus(result.status);
      setSelectedFile(null);
      showToast?.("Identity card uploaded. It can now only be changed by an admin.", "success");
    } catch (err) {
      showToast?.(err.message || "Failed to upload identity card", "error");
    } finally {
      setUploading(false);
    }
  };

  if (status === null) {
    return (
      <div className={styles.card}>
        <h3>Identity Card</h3>
        <p className={styles.hint}>Loading…</p>
      </div>
    );
  }

  if (status.uploaded) {
    return (
      <div className={styles.card}>
        <h3>Identity Card</h3>
        {previewUrl && (
          <img src={previewUrl} alt="Uploaded identity card" className={styles.preview} />
        )}
        <p className={styles.lockedNote}>
          <span className={styles.lockIcon} aria-hidden="true">🔒</span>
          Uploaded{status.uploaded_at ? ` on ${new Date(status.uploaded_at).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })}` : ""}.
          Your identity card is verified against your face before every
          interview and can only be changed by an administrator.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <h3>Identity Card</h3>
      <p className={styles.hint}>
        Upload a clear photo of your government or institutional ID. It is
        required before you can start an interview — your face is matched
        against it at interview start.
      </p>
      <p className={styles.warning}>
        You can upload it <strong>only once</strong>; after that, changes go
        through an administrator.
      </p>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className={styles.fileInput}
        onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
      />
      {selectedFile && (
        <p className={styles.hint}>Selected: {selectedFile.name}</p>
      )}
      <button
        className={styles.uploadButton}
        onClick={handleUpload}
        disabled={!selectedFile || uploading}
      >
        {uploading ? "Uploading…" : "Upload Identity Card"}
      </button>
    </div>
  );
};

export default IdentityCardUpload;

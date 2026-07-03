import React, { useState, useEffect } from 'react';
import cvService from '../../services/cvService';
import ConfirmDialog from '../common/ConfirmDialog';
import styles from './CVManagement.module.css';

const CVManagement = () => {
  const [cvs, setCvs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [previewCV, setPreviewCV] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [maxCVs, setMaxCVs] = useState(5);
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    loadCVs();
  }, []);

  const loadCVs = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await cvService.listCVs();
      setCvs(response.cvs || []);
      setMaxCVs(response.max_allowed || 5);
    } catch (err) {
      setError(err.message || 'Failed to load CVs');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    if (file.type !== 'application/pdf') {
      setError('Only PDF files are allowed');
      return;
    }

    // Validate file size (10MB)
    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB');
      return;
    }

    try {
      setUploading(true);
      setError('');
      setSuccess('');

      const isPrimary = cvs.length === 0; // First CV is automatically primary
      await cvService.uploadCV(file, isPrimary);

      setSuccess('CV uploaded successfully!');
      await loadCVs();

      // Clear file input
      event.target.value = '';
    } catch (err) {
      setError(err.message || 'Failed to upload CV');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = (cvId) => {
    setPendingDeleteId(cvId);
  };

  const confirmDelete = async () => {
    const cvId = pendingDeleteId;
    if (!cvId) return;
    setIsDeleting(true);
    try {
      setError('');
      setSuccess('');
      await cvService.deleteCV(cvId);
      setSuccess('CV deleted successfully');
      await loadCVs();
    } catch (err) {
      setError(err.message || 'Failed to delete CV');
    } finally {
      setIsDeleting(false);
      setPendingDeleteId(null);
    }
  };

  const handleSetPrimary = async (cvId) => {
    try {
      setError('');
      setSuccess('');
      await cvService.setPrimaryCV(cvId);
      setSuccess('Primary CV updated successfully');
      await loadCVs();
    } catch (err) {
      setError(err.message || 'Failed to set primary CV');
    }
  };

  const handlePreview = async (cvId) => {
    try {
      setError('');
      const response = await cvService.getCVText(cvId);
      setPreviewCV(response);
      setShowPreview(true);
    } catch (err) {
      setError(err.message || 'Failed to fetch CV text');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className={styles.cvManagement}>
        <h3>📄 My CVs</h3>
        <div className={styles.loading}>Loading CVs...</div>
      </div>
    );
  }

  return (
    <div className={styles.cvManagement}>
      <div className={styles.header}>
        <h3>📄 My CVs</h3>
        <span className={styles.cvCount}>
          {cvs.length} / {maxCVs} CVs uploaded
        </span>
      </div>

      {error && <div className={styles.error}>{error}</div>}
      {success && <div className={styles.success}>{success}</div>}

      {/* Upload Section */}
      <div className={styles.uploadSection}>
        <label htmlFor="cv-upload" className={styles.uploadButton}>
          <input
            id="cv-upload"
            type="file"
            accept=".pdf"
            onChange={handleFileUpload}
            disabled={uploading || cvs.length >= maxCVs}
            style={{ display: 'none' }}
          />
          {uploading ? (
            <>⏳ Uploading...</>
          ) : cvs.length >= maxCVs ? (
            <>🚫 Maximum CVs Reached</>
          ) : (
            <>➕ Upload New CV (PDF)</>
          )}
        </label>
        <p className={styles.uploadHint}>
          📌 Max file size: 10MB | Format: PDF only | 
          {cvs.length === 0 && ' Your first CV will be set as primary'}
        </p>
      </div>

      {/* CV List */}
      <div className={styles.cvList}>
        {cvs.length === 0 ? (
          <div className={styles.emptyState}>
            <p>📭 No CVs uploaded yet</p>
            <p className={styles.emptyHint}>
              Upload your CV to apply for jobs and start practice interviews
            </p>
          </div>
        ) : (
          cvs.map((cv) => (
            <div key={cv.cv_id} className={styles.cvCard}>
              <div className={styles.cvHeader}>
                <div className={styles.cvTitle}>
                  <span className={styles.cvIcon}>📄</span>
                  <span className={styles.cvFilename}>{cv.filename}</span>
                  {cv.is_primary && (
                    <span className={styles.primaryBadge}>⭐ Primary</span>
                  )}
                </div>
                <div className={styles.cvActions}>
                  {!cv.is_primary && (
                    <button
                      className={styles.actionButton}
                      onClick={() => handleSetPrimary(cv.cv_id)}
                      title="Set as primary CV"
                    >
                      ⭐
                    </button>
                  )}
                  <button
                    className={styles.actionButton}
                    onClick={() => handlePreview(cv.cv_id)}
                    title="Preview extracted text"
                  >
                    👁️
                  </button>
                  <button
                    className={`${styles.actionButton} ${styles.deleteButton}`}
                    onClick={() => handleDelete(cv.cv_id)}
                    title="Delete CV"
                  >
                    🗑️
                  </button>
                </div>
              </div>

              <div className={styles.cvMeta}>
                <span>📅 Uploaded: {formatDate(cv.upload_date)}</span>
                {cv.metadata && (
                  <>
                    <span>📏 {formatFileSize(cv.metadata.file_size)}</span>
                    {cv.metadata.pages > 0 && (
                      <span>📃 {cv.metadata.pages} page{cv.metadata.pages > 1 ? 's' : ''}</span>
                    )}
                    {cv.metadata.character_count > 0 && (
                      <span>✍️ {cv.metadata.character_count.toLocaleString()} characters</span>
                    )}
                  </>
                )}
              </div>

              {cv.is_primary && (
                <div className={styles.primaryNote}>
                  This CV will be used by default when applying for jobs
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Preview Modal */}
      {showPreview && previewCV && (
        <div className={styles.modal} onClick={() => setShowPreview(false)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h4>📄 {previewCV.filename}</h4>
              <button
                className={styles.closeButton}
                onClick={() => setShowPreview(false)}
              >
                ✕
              </button>
            </div>
            <div className={styles.modalBody}>
              <p className={styles.previewMeta}>
                {previewCV.character_count.toLocaleString()} characters extracted
              </p>
              <pre className={styles.previewText}>
                {previewCV.extracted_text || 'No text extracted'}
              </pre>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={!!pendingDeleteId}
        onClose={() => setPendingDeleteId(null)}
        onConfirm={confirmDelete}
        title="Delete CV"
        message="Are you sure you want to delete this CV?"
        confirmText="Delete"
        confirmVariant="danger"
        isLoading={isDeleting}
      />
    </div>
  );
};

export default CVManagement;

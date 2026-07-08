import React, { useState, useEffect } from 'react';
import cvService from 'features/candidate/api/cvService';
import styles from './CVSelector.module.css';

/**
 * CV Selector Component
 * Allows users to select which CV to use for applications or practice
 */
const CVSelector = ({ onSelect, selectedCvId = null, showLabel = true }) => {
  const [cvs, setCvs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedCV, setSelectedCV] = useState(selectedCvId);

  useEffect(() => {
    loadCVs();
  }, []);

  useEffect(() => {
    // Auto-select primary CV if none selected and CVs are loaded
    if (!selectedCV && cvs.length > 0) {
      const primaryCV = cvs.find(cv => cv.is_primary);
      if (primaryCV) {
        setSelectedCV(primaryCV.cv_id);
        if (onSelect) {
          onSelect(primaryCV.cv_id);
        }
      }
    }
  }, [cvs, selectedCV, onSelect]);

  const loadCVs = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await cvService.listCVs();
      setCvs(response.cvs || []);
    } catch (err) {
      setError(err.message || 'Failed to load CVs');
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (cvId) => {
    setSelectedCV(cvId);
    if (onSelect) {
      onSelect(cvId);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className={styles.cvSelector}>
        {showLabel && <label>Select CV</label>}
        <div className={styles.loading}>Loading CVs...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.cvSelector}>
        {showLabel && <label>Select CV</label>}
        <div className={styles.error}>{error}</div>
      </div>
    );
  }

  if (cvs.length === 0) {
    return (
      <div className={styles.cvSelector}>
        {showLabel && <label>Select CV</label>}
        <div className={styles.noCV}>
          <p>📭 No CVs uploaded yet</p>
          <p className={styles.hint}>
            Upload a CV in your profile to continue
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.cvSelector}>
      {showLabel && (
        <label>
          Select CV
          <span className={styles.optional}>(optional - uses primary if not selected)</span>
        </label>
      )}

      <div className={styles.cvList}>
        {cvs.map((cv) => (
          <div
            key={cv.cv_id}
            className={`${styles.cvOption} ${
              selectedCV === cv.cv_id ? styles.selected : ''
            }`}
            onClick={() => handleSelect(cv.cv_id)}
          >
            <div className={styles.radioButton}>
              {selectedCV === cv.cv_id && <div className={styles.radioInner} />}
            </div>
            <div className={styles.cvInfo}>
              <div className={styles.cvName}>
                <span className={styles.cvIcon}>📄</span>
                {cv.filename}
                {cv.is_primary && (
                  <span className={styles.primaryBadge}>⭐ Primary</span>
                )}
              </div>
              <div className={styles.cvMeta}>
                <span>📅 {formatDate(cv.upload_date)}</span>
                {cv.metadata?.pages > 0 && (
                  <span>📃 {cv.metadata.pages} page{cv.metadata.pages > 1 ? 's' : ''}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {selectedCV && (
        <div className={styles.selectedInfo}>
          ✅ Using: <strong>{cvs.find(cv => cv.cv_id === selectedCV)?.filename}</strong>
        </div>
      )}
    </div>
  );
};

export default CVSelector;

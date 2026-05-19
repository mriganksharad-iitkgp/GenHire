import React, { useCallback, useEffect, useState } from 'react';
import { useCandidateData } from '../../contexts/CandidateDataContext';
import styles from './CVList.module.css';

const CVList = ({ onCVClick, showToast, refreshTrigger = 0 }) => {
  const { cvs, cvsLoaded, loadCvsCached, invalidateCvs } = useCandidateData();
  const [cvList, setCvList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [settingPrimary, setSettingPrimary] = useState(null);

  const fetchCVs = useCallback(async (force = false) => {
    setLoading(true);
    try {
      const token = localStorage.getItem('companyxyz-token');
      const loadedCvs = await loadCvsCached(force, async () => {
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/cv/list`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || 'Failed to load CVs');
        }

        const data = await response.json();
        return data.cvs || [];
      });

      setCvList(loadedCvs || []);
    } catch (err) {
      console.error('Error fetching CVs:', err);
      showToast?.(err.message || 'Failed to load CVs', 'error');
    } finally {
      setLoading(false);
    }
  }, [loadCvsCached, showToast]);

  useEffect(() => {
    if (cvsLoaded) {
      setCvList(cvs || []);
      setLoading(false);
      return;
    }

    fetchCVs(false);
  }, [cvsLoaded, cvs, fetchCVs]);

  useEffect(() => {
    if (refreshTrigger > 0) {
      fetchCVs(true);
    }
  }, [refreshTrigger, fetchCVs]);

  const handleSetPrimary = async (cvId, e) => {
    e.stopPropagation();
    setSettingPrimary(cvId);

    try {
      const token = localStorage.getItem('companyxyz-token');
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/cv/${cvId}/set-primary`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        showToast?.(data.error || 'Failed to set primary CV', 'error');
        return;
      }

      showToast?.('Primary CV updated successfully', 'success');
      invalidateCvs();
      await fetchCVs(true);
    } catch (err) {
      console.error('Error setting primary CV:', err);
      showToast?.('Failed to set primary CV', 'error');
    } finally {
      setSettingPrimary(null);
    }
  };

  const handleCVClick = (cv) => {
    onCVClick?.(cv);
  };

  if (loading) {
    return (
      <div className={styles.loading}>
        <i className="fa fa-spinner fa-spin"></i>
        <span>Loading CVs...</span>
      </div>
    );
  }

  if (cvList.length === 0) {
    return (
      <div className={styles.emptyState}>
        <i className="fa fa-file-text-o"></i>
        <p>No CVs uploaded yet</p>
        <small>Upload your first CV above to get started</small>
      </div>
    );
  }

  return (
    <div className={styles.cvList}>
      <div className={styles.header}>
        <h4>
          <i className="fa fa-list"></i> Uploaded CVs ({cvList.length})
        </h4>
        <small>Click to view in new tab</small>
      </div>

      <div className={styles.list}>
        {cvList.map((cv) => (
          <div
            key={cv.cv_id}
            className={`${styles.cvCard} ${cv.is_primary ? styles.primary : ''}`}
            onClick={() => handleCVClick(cv)}
          >
            <div className={styles.cvIcon}>
              <i className="fa fa-file-pdf-o"></i>
            </div>

            <div className={styles.cvInfo}>
              <div className={styles.cvFileName} title={cv.filename}>
                {cv.filename || cv.file_name || cv.original_filename || 'Uploaded CV'}
              </div>
              <div className={styles.cvActions}>
                {cv.is_primary ? (
                  <span className={styles.primaryBadge}>
                    <i className="fa fa-star"></i> Primary
                  </span>
                ) : (
                  <button
                    className={styles.primaryButton}
                    onClick={(e) => handleSetPrimary(cv.cv_id, e)}
                    disabled={settingPrimary === cv.cv_id}
                    title="Set as primary CV"
                  >
                    {settingPrimary === cv.cv_id ? (
                      <i className="fa fa-spinner fa-spin"></i>
                    ) : (
                      <>
                        <i className="fa fa-star-o"></i>
                        <span>Make Primary</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className={styles.footer}>
        <i className="fa fa-info-circle"></i>
        <small>Primary CV is auto-selected when applying for jobs or starting practice interviews</small>
      </div>
    </div>
  );
};

export default CVList;

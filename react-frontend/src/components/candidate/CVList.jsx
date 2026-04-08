import React, { useState, useEffect } from 'react';
import styles from './CVList.module.css';

const CVList = ({ onCVClick, showToast, refreshTrigger }) => {
  const [cvList, setCvList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [settingPrimary, setSettingPrimary] = useState(null);

  useEffect(() => {
    fetchCVs();
  }, [refreshTrigger]); // Re-fetch when refreshTrigger changes

  const fetchCVs = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('companyxyz-token');
      console.log('🔍 Fetching CVs from:', `${process.env.REACT_APP_API_URL}/api/cv/list`);
      
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/cv/list`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      console.log('📡 CV list response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('✅ CV list data received:', data);
        console.log('📋 Number of CVs:', data.cvs?.length || 0);
        if (data.cvs && data.cvs.length > 0) {
          console.log('📄 First CV structure:', data.cvs[0]);
          console.log('📄 Filename fields:', {
            filename: data.cvs[0].filename,
            file_name: data.cvs[0].file_name,
            original_filename: data.cvs[0].original_filename
          });
        }
        setCvList(data.cvs || []);
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('❌ CV list fetch failed:', response.status, errorData);
        showToast?.(`Failed to load CVs: ${errorData.error || 'Unknown error'}`, 'error');
      }
    } catch (err) {
      console.error('❌ Error fetching CVs:', err);
      showToast?.('Failed to load CVs', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSetPrimary = async (cvId, e) => {
    e.stopPropagation(); // Prevent CV click
    setSettingPrimary(cvId);
    
    try {
      const token = localStorage.getItem('companyxyz-token');
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/cv/${cvId}/set-primary`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        showToast?.('Primary CV updated successfully', 'success');
        await fetchCVs(); // Refresh list
      } else {
        const data = await response.json();
        showToast?.(data.error || 'Failed to set primary CV', 'error');
      }
    } catch (err) {
      console.error('Error setting primary CV:', err);
      showToast?.('Failed to set primary CV', 'error');
    } finally {
      setSettingPrimary(null);
    }
  };

  const handleCVClick = (cv) => {
    // Open CV PDF in new tab using fetch with auth headers
    const token = localStorage.getItem('companyxyz-token');
    const url = `${process.env.REACT_APP_API_URL}/api/cv/${cv.cv_id}/preview`;
    
    fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to load CV');
      }
      return response.blob();
    })
    .then(blob => {
      const blobUrl = window.URL.createObjectURL(blob);
      window.open(blobUrl, '_blank');
    })
    .catch(err => {
      console.error('Error opening CV:', err);
      showToast?.('Failed to open CV', 'error');
    });
    
    onCVClick?.(cv);
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return 'N/A';
    return bytes < 1024 * 1024 
      ? `${(bytes / 1024).toFixed(1)} KB`
      : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
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
                {cv.filename}
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

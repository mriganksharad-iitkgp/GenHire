import React, { useState, useEffect } from 'react';
import { useCandidateData } from '../contexts/CandidateDataContext';
import styles from './CVSelectionModal.module.css';

const CVSelectionModal = ({ 
  isOpen, 
  onClose, 
  onSubmit,
  jobTitle,
  mode = 'apply' // 'apply' or 'practice'
}) => {
  const { cvs: cachedCvs, cvsLoaded, loadCvsCached } = useCandidateData();
  const [cvList, setCvList] = useState([]);
  const [selectedCvId, setSelectedCvId] = useState(null);
  const [useManualCV, setUseManualCV] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [manualCVComplete, setManualCVComplete] = useState(false);

  useEffect(() => {
    if (isOpen) {
      // Only fetch if not already loaded (caching via context)
      if (!cvsLoaded) {
        fetchCVs();
        checkManualCVCompletion();
      } else {
        // Use cached data - instant loading!
        console.log('📦 Using cached CVs from context');
        setCvList(cachedCvs);
        setLoading(false);
        
        // Auto-select primary CV if available
        const primaryCV = cachedCvs?.find(cv => cv.is_primary);
        if (primaryCV) {
          setSelectedCvId(primaryCV.cv_id);
          setUseManualCV(false);
        } else if (cachedCvs?.length > 0) {
          setSelectedCvId(cachedCvs[0].cv_id);
          setUseManualCV(false);
        } else {
          setUseManualCV(true);
        }
      }
    } else {
      // Reset submitting state when modal closes
      setIsSubmitting(false);
      setError(null);
    }
  }, [isOpen, cvsLoaded, cachedCvs]);

  const fetchCVs = async () => {
    setLoading(true);
    try {
      // Use cached data from context
      const cvs = await loadCvsCached(false, async () => {
        const token = localStorage.getItem('companyxyz-token');
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/cv/list`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          return data.cvs || [];
        } else {
          throw new Error('Failed to load CVs');
        }
      });

      setCvList(cvs);
      
      // Auto-select primary CV if available
      const primaryCV = cvs?.find(cv => cv.is_primary);
      if (primaryCV) {
        setSelectedCvId(primaryCV.cv_id);
        setUseManualCV(false);
      } else if (cvs?.length > 0) {
        setSelectedCvId(cvs[0].cv_id);
        setUseManualCV(false);
      } else {
        // No CVs uploaded, default to manual CV
        setUseManualCV(true);
      }
    } catch (err) {
      console.error('Error fetching CVs:', err);
      setError('Failed to load CVs');
      setUseManualCV(true); // Fallback to manual CV
    } finally {
      setLoading(false);
    }
  };

  const checkManualCVCompletion = async () => {
    try {
      const token = localStorage.getItem('companyxyz-token');
      const user = JSON.parse(localStorage.getItem('companyxyz-user'));
      
      // Check if manual CV details are complete
      // This is a basic check - you can make it more sophisticated
      const hasBasicInfo = user?.name && user?.email;
      setManualCVComplete(hasBasicInfo);
    } catch (err) {
      console.error('Error checking manual CV:', err);
      setManualCVComplete(false);
    }
  };

  const handleSubmit = () => {
    // Validation
    if (useManualCV && !manualCVComplete) {
      setError('Please complete your profile CV details before applying with manual CV');
      return;
    }

    if (!useManualCV && !selectedCvId) {
      setError('Please select a CV or choose to apply with profile details');
      return;
    }

    setIsSubmitting(true);

    // Submit with selected option
    onSubmit({
      cv_id: useManualCV ? null : selectedCvId,
      use_manual_cv: useManualCV
    });
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

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>Choose Your CV/Resume</h2>
          <p className={styles.subtitle}>
            {mode === 'practice' ? 'Practice Interview for: ' : 'Applying for: '}
            <strong>{jobTitle}</strong>
          </p>
          <button className={styles.closeButton} onClick={onClose}>
            <i className="fa fa-times"></i>
          </button>
        </div>

        <div className={styles.content}>
          {loading ? (
            <div className={styles.loadingState}>
              <i className="fa fa-spinner fa-spin"></i>
              <p>Loading your CVs...</p>
            </div>
          ) : (
            <>
              {/* Uploaded CV Options */}
              {cvList.length > 0 && (
                <div className={styles.section}>
                  <h3>
                    <i className="fa fa-file-pdf-o"></i> Uploaded CVs/Resumes
                  </h3>
                  <div className={styles.cvList}>
                    {cvList.map((cv, index) => {
                      console.log(`📄 Rendering CV ${index}:`, cv);
                      console.log(`📄 Filename for CV ${index}:`, cv.filename);
                      return (
                      <div
                        key={cv.cv_id}
                        className={`${styles.cvCard} ${
                          !useManualCV && selectedCvId === cv.cv_id ? styles.selected : ''
                        }`}
                        onClick={() => {
                          setSelectedCvId(cv.cv_id);
                          setUseManualCV(false);
                          setError(null);
                        }}
                      >
                        <div className={styles.cvCardHeader}>
                          <div className={styles.radioButton}>
                            {!useManualCV && selectedCvId === cv.cv_id && (
                              <i className="fa fa-check-circle"></i>
                            )}
                          </div>
                          <div className={styles.pdfIcon}>
                            <i className="fa fa-file-pdf-o"></i>
                          </div>
                          <div className={styles.cvInfo}>
                            <div className={styles.cvFileName}>
                              {cv.filename || cv.file_name || cv.original_filename || `CV_${index + 1}.pdf`}
                            </div>
                            {cv.is_primary && (
                              <span className={styles.primaryBadge}>
                                <i className="fa fa-star"></i> Primary
                              </span>
                            )}
                            <div className={styles.cvMeta}>
                              <span>
                                <i className="fa fa-file"></i> {cv.metadata?.pages || 'N/A'} pages
                              </span>
                              <span>
                                <i className="fa fa-hdd-o"></i> {formatFileSize(cv.metadata?.file_size)}
                              </span>
                              <span>
                                <i className="fa fa-calendar"></i> {formatDate(cv.uploaded_at)}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                    })}
                  </div>
                </div>
              )}

              {/* Manual CV Option */}
              <div className={styles.section}>
                <h3>
                  <i className="fa fa-user"></i> Use Profile Details
                </h3>
                <div
                  className={`${styles.cvCard} ${styles.manualCard} ${
                    useManualCV ? styles.selected : ''
                  }`}
                  onClick={() => {
                    setUseManualCV(true);
                    setSelectedCvId(null);
                    setError(null);
                  }}
                >
                  <div className={styles.cvCardHeader}>
                    <div className={styles.radioButton}>
                      {useManualCV && <i className="fa fa-check-circle"></i>}
                    </div>
                    <div className={styles.cvInfo}>
                      <h4>Apply with Profile CV Details</h4>
                      <p className={styles.description}>
                        Use your manually entered CV information from your profile
                      </p>
                      {!manualCVComplete && (
                        <div className={styles.warning}>
                          <i className="fa fa-exclamation-triangle"></i>
                          <span>
                            Your profile CV details are incomplete. Please complete them before using this option.
                          </span>
                        </div>
                      )}
                      {manualCVComplete && (
                        <div className={styles.success}>
                          <i className="fa fa-check-circle"></i>
                          <span>Profile CV details are complete</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* No CVs Uploaded Message */}
              {cvList.length === 0 && (
                <div className={styles.emptyState}>
                  <i className="fa fa-info-circle"></i>
                  <p>
                    You haven't uploaded any CVs yet. You can upload CVs from your profile page or apply with your profile details.
                  </p>
                </div>
              )}
            </>
          )}

          {/* Error Message */}
          {error && (
            <div className={styles.errorMessage}>
              <i className="fa fa-exclamation-circle"></i>
              {error}
            </div>
          )}
        </div>

        <div className={styles.footer}>
          <button
            className={styles.cancelButton}
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            className={styles.submitButton}
            onClick={handleSubmit}
            disabled={isSubmitting || loading}
          >
            {isSubmitting ? (
              <>
                <i className="fa fa-spinner fa-spin"></i> {mode === 'practice' ? 'Starting...' : 'Submitting...'}
              </>
            ) : mode === 'practice' ? (
              <>
                <i className="fa fa-play-circle"></i> Start Practice Interview Now
              </>
            ) : (
              <>
                <i className="fa fa-paper-plane"></i> Submit Application
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CVSelectionModal;

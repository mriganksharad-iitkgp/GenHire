import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useCandidateData } from 'features/candidate/context/CandidateDataContext';
import { getProfile, updateCvDetails } from 'shared/api/endpoints';
import { isProfileCvComplete } from 'shared/utils/cvDetails';
import cvService from 'features/candidate/api/cvService';
import CVDetailsForm from 'features/candidate/components/CVDetailsForm';
import styles from './CVSelectionModal.module.css';

import { getToken } from "shared/utils/session";

// Mirrors the limits enforced by CVController (PDF only, 10 MB, 5 per user) so
// a doomed upload is rejected here instead of after a round trip.
const MAX_CV_SIZE_MB = 10;
const MAX_CVS_PER_USER = 5;

const CVSelectionModal = ({
  isOpen,
  onClose,
  onSubmit,
  jobTitle,
  mode = 'apply' // 'apply', 'practice', or 'check_score'
}) => {
  const {
    cvs: cachedCvs,
    cvsLoaded,
    loadCvsCached,
    loadProfileCached,
    invalidateCvs,
    updateCachedProfile,
  } = useCandidateData();
  const [cvList, setCvList] = useState([]);
  const [selectedCvId, setSelectedCvId] = useState(null);
  const [useManualCV, setUseManualCV] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [manualCVComplete, setManualCVComplete] = useState(false);

  // Inline "unblock myself" state — a candidate with neither an uploaded CV nor
  // completed profile details used to hit a dead end here, told to go to their
  // profile page with no way to act and no way back into the application.
  const [isUploading, setIsUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState(null);
  const [showCvDetailsForm, setShowCvDetailsForm] = useState(false);
  const [existingCvDetails, setExistingCvDetails] = useState(null);
  const fileInputRef = useRef(null);

  const checkManualCVCompletion = useCallback(async () => {
    try {
      const profile = await loadProfileCached(false, getProfile);
      setExistingCvDetails(profile?.cv_details || null);
      setManualCVComplete(isProfileCvComplete(profile?.cv_details));
    } catch (err) {
      console.error('Error checking manual CV:', err);
      setManualCVComplete(false);
    }
  }, [loadProfileCached]);

  // Picks the best default: primary CV, else the first CV, else profile details.
  const applyDefaultSelection = useCallback((cvs, preferredCvId = null) => {
    if (preferredCvId) {
      setSelectedCvId(preferredCvId);
      setUseManualCV(false);
      return;
    }
    const primaryCV = cvs?.find(cv => cv.is_primary);
    if (primaryCV) {
      setSelectedCvId(primaryCV.cv_id);
      setUseManualCV(false);
    } else if (cvs?.length > 0) {
      setSelectedCvId(cvs[0].cv_id);
      setUseManualCV(false);
    } else {
      setUseManualCV(true);
    }
  }, []);

  const fetchCVs = useCallback(async () => {
    setLoading(true);
    try {
      // Use cached data from context
      const cvs = await loadCvsCached(false, async () => {
        const token = getToken();
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
      applyDefaultSelection(cvs);
    } catch (err) {
      console.error('Error fetching CVs:', err);
      setError('Failed to load CVs');
      setUseManualCV(true); // Fallback to manual CV
    } finally {
      setLoading(false);
    }
  }, [loadCvsCached, applyDefaultSelection]);

  useEffect(() => {
    if (isOpen) {
      checkManualCVCompletion();
      // Only fetch if not already loaded (caching via context)
      if (!cvsLoaded) {
        fetchCVs();
      } else {
        // Use cached data - instant loading!
        setCvList(cachedCvs);
        setLoading(false);
        applyDefaultSelection(cachedCvs);
      }
    } else {
      // Reset transient state when modal closes
      setIsSubmitting(false);
      setError(null);
      setUploadNotice(null);
      setShowCvDetailsForm(false);
    }
  }, [isOpen, cvsLoaded, cachedCvs, checkManualCVCompletion, fetchCVs, applyDefaultSelection]);

  /**
   * Attach a CV PDF without leaving the application. On success the new CV is
   * selected, so the candidate can submit immediately.
   */
  const handleFileSelected = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // let the same file be re-picked after an error
    if (!file) return;

    if (!/\.pdf$/i.test(file.name)) {
      setError('Only PDF files are supported. Please attach your CV as a PDF.');
      return;
    }
    if (file.size > MAX_CV_SIZE_MB * 1024 * 1024) {
      setError(`That file is larger than ${MAX_CV_SIZE_MB} MB. Please attach a smaller PDF.`);
      return;
    }

    setIsUploading(true);
    setError(null);
    setUploadNotice(null);
    try {
      // First CV becomes the primary one so future applications default to it.
      const result = await cvService.uploadCV(file, cvList.length === 0);
      const newCvId = result?.cv?.cv_id || null;

      invalidateCvs();
      const cvs = await loadCvsCached(true, async () => {
        const data = await cvService.listCVs();
        return data?.cvs || [];
      });

      setCvList(cvs);
      applyDefaultSelection(cvs, newCvId);
      setUploadNotice(`"${file.name}" attached — you can submit your application now.`);
    } catch (err) {
      console.error('CV upload failed:', err);
      setError(err?.message || 'Could not upload that CV. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  /**
   * Save profile CV details entered inline, then select that option so the
   * candidate lands back on a submittable application.
   */
  const handleSaveCvDetails = async (formData) => {
    try {
      await updateCvDetails(formData);
      updateCachedProfile(prev => ({ ...(prev || {}), cv_details: formData }));
      setExistingCvDetails(formData);
      const complete = isProfileCvComplete(formData);
      setManualCVComplete(complete);
      setShowCvDetailsForm(false);
      setError(null);
      if (complete) {
        setUseManualCV(true);
        setSelectedCvId(null);
        setUploadNotice('Profile CV details saved — you can submit your application now.');
      } else {
        setError('Saved, but some required CV details are still missing. Please complete education, technical skills, a project, and expected salary.');
      }
    } catch (err) {
      console.error('Error saving CV details:', err);
      setError(err?.message || 'Could not save your CV details. Please try again.');
      // Rethrow so CVDetailsForm stays open showing its own error toast,
      // instead of reporting "saved successfully" over a failed write.
      throw err;
    }
  };

  // Nothing to submit with — surfaced on the button instead of failing on click.
  const hasUsableChoice = useManualCV ? manualCVComplete : !!selectedCvId;
  const atCvLimit = cvList.length >= MAX_CVS_PER_USER;

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
    return new Date(dateString).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const actionNoun =
    mode === 'practice' ? 'start practice' : mode === 'check_score' ? 'check your score' : 'apply';

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>Choose Your CV/Resume</h2>
          <p className={styles.subtitle}>
            {mode === 'practice'
              ? 'Practice Interview for: '
              : mode === 'check_score'
                ? 'Checking match score for: '
                : 'Applying for: '}
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
              {/* Both ways forward, offered up front when neither is ready yet,
                  so the candidate never has to leave to unblock themselves. */}
              {!hasUsableChoice && (
                <div className={styles.getStarted}>
                  <p className={styles.getStartedText}>
                    To {actionNoun}, choose one of these — either works:
                  </p>
                  <div className={styles.getStartedActions}>
                    <button
                      type="button"
                      className={styles.primaryAction}
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading || atCvLimit}
                    >
                      <i className={`fa ${isUploading ? 'fa-spinner fa-spin' : 'fa-upload'}`}></i>{' '}
                      {isUploading ? 'Uploading…' : 'Attach CV (PDF)'}
                    </button>
                    <span className={styles.getStartedOr}>or</span>
                    <button
                      type="button"
                      className={styles.secondaryAction}
                      onClick={() => setShowCvDetailsForm(true)}
                      disabled={isUploading}
                    >
                      <i className="fa fa-pencil-square-o"></i> Fill in CV details
                    </button>
                  </div>
                </div>
              )}

              {/* Uploaded CV Options */}
              {cvList.length > 0 && (
                <div className={styles.section}>
                  <h3>
                    <i className="fa fa-file-pdf-o"></i> Uploaded CVs/Resumes
                  </h3>
                  <div className={styles.cvList}>
                    {cvList.map((cv, index) => (
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
                    ))}
                  </div>
                </div>
              )}

              {/* Attach another CV — always available, not just when empty. */}
              <div className={styles.uploadRow}>
                <button
                  type="button"
                  className={styles.uploadButton}
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading || atCvLimit}
                >
                  <i className={`fa ${isUploading ? 'fa-spinner fa-spin' : 'fa-paperclip'}`}></i>{' '}
                  {isUploading
                    ? 'Uploading…'
                    : cvList.length > 0
                      ? 'Attach a different CV (PDF)'
                      : 'Attach your CV (PDF)'}
                </button>
                <span className={styles.uploadHint}>
                  {atCvLimit
                    ? `You've reached the ${MAX_CVS_PER_USER}-CV limit. Remove one from your profile to add another.`
                    : `PDF only, up to ${MAX_CV_SIZE_MB} MB.`}
                </span>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                onChange={handleFileSelected}
                style={{ display: 'none' }}
              />

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
                        <>
                          <div className={styles.warning}>
                            <i className="fa fa-exclamation-triangle"></i>
                            <span>
                              Your profile CV details are incomplete — you'll need education,
                              technical skills, a project, and expected salary.
                            </span>
                          </div>
                          <button
                            type="button"
                            className={styles.inlineFixButton}
                            onClick={(e) => {
                              e.stopPropagation();
                              setShowCvDetailsForm(true);
                            }}
                          >
                            <i className="fa fa-pencil-square-o"></i> Complete them now
                          </button>
                        </>
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
            </>
          )}

          {/* Success notice after an inline upload / details save */}
          {uploadNotice && (
            <div className={styles.successMessage}>
              <i className="fa fa-check-circle"></i>
              {uploadNotice}
            </div>
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
            disabled={isSubmitting || loading || isUploading || !hasUsableChoice}
            title={
              hasUsableChoice
                ? undefined
                : 'Attach a CV PDF or complete your profile CV details first'
            }
          >
            {isSubmitting ? (
              <>
                <i className="fa fa-spinner fa-spin"></i>{' '}
                {mode === 'practice' ? 'Starting...' : mode === 'check_score' ? 'Checking...' : 'Submitting...'}
              </>
            ) : mode === 'practice' ? (
              <>
                <i className="fa fa-play-circle"></i> Start Practice Interview Now
              </>
            ) : mode === 'check_score' ? (
              <>
                <i className="fa fa-check-circle"></i> Check My Match Score
              </>
            ) : (
              <>
                <i className="fa fa-paper-plane"></i> Submit Application
              </>
            )}
          </button>
        </div>
      </div>

      {/* Renders its own full-screen layer above this modal (z-index 10040). */}
      {showCvDetailsForm && (
        <CVDetailsForm
          existingData={existingCvDetails}
          onSave={handleSaveCvDetails}
          onClose={() => setShowCvDetailsForm(false)}
        />
      )}
    </div>
  );
};

export default CVSelectionModal;

import React from 'react';
import styles from 'features/recruiter/pages/RecruiterDashboard.module.css';
import { getToken, getUser, clearSession, isLoggedIn } from "shared/utils/session";
import { normalizeStatus, statusLabel, applicationStatusLabel } from "shared/utils/applicationStatus";

const CandidateCard = ({ application, displayStatus, updateApplicationStatus, viewInterviewReport, viewProctoringReport }) => {
  const cvScorePct = (typeof application.cv_score === 'number')
    ? Math.round(application.cv_score)
    : (typeof application.similarity_score === 'number' ? Math.round(application.similarity_score * 100) : null);
  const interviewScorePct = (typeof application.interview_score === 'number')
    ? Math.round(application.interview_score)
    : null;
  const proctoringScorePct = (typeof application.proctoring_score === 'number')
    ? Math.round(application.proctoring_score)
    : null;

  // Define the status progression hierarchy
  const statusHierarchy = ['pending', 'reviewed', 'shortlisted', 'interviewed', 'screening_cleared', 'rejected'];

  // Get available status options based on current status (one-way progression)
  const getAvailableStatusOptions = (currentStatus) => {
    const currentIndex = statusHierarchy.indexOf(currentStatus);

    // If current status is not found, default to all options
    if (currentIndex === -1) {
      return statusHierarchy;
    }

    // Allow current status and all subsequent statuses
    const availableStatuses = statusHierarchy.slice(currentIndex);

    // Special case: if interviewed, screening either clears or doesn't
    if (currentStatus === 'interviewed') {
      return ['interviewed', 'screening_cleared', 'rejected'];
    }

    // Special case: terminal statuses — no further progression
    if (currentStatus === 'screening_cleared' || currentStatus === 'rejected') {
      return [currentStatus];
    }

    return availableStatuses;
  };

  const availableStatuses = getAvailableStatusOptions(normalizeStatus(application.status));

  // Identity verification summary written by /register-face — tells the
  // recruiter whether the person on camera matched the account's registered
  // face before this interview.
  const identity = application.identity_verification;
  const identityChip = (() => {
    if (!identity || !identity.status) return null;
    switch (identity.status) {
      case 'verified':
        return { text: '✓ ID Verified', color: '#166534', background: '#f0fdf4', border: '#bbf7d0' };
      case 'registered_new':
        return { text: '🪪 ID Registered (1st interview)', color: '#1e40af', background: '#eff6ff', border: '#bfdbfe' };
      case 'mismatch':
      case 'mismatch_blocked':
        return { text: '⚠ ID Mismatch', color: '#991b1b', background: '#fef2f2', border: '#fecdd3' };
      case 'unverified_monitor':
      case 'unverified_system_unavailable':
        return { text: 'ID Unverified', color: '#9a3412', background: '#fff7ed', border: '#fed7aa' };
      default:
        return null;
    }
  })();

  return (
    <div className={styles.candidateCard}>
      <div className={styles.candidateInfo}>
        <div className={styles.candidateAvatar}>
          {application.student_name.split(' ').map(n => n[0]).join('')}
        </div>
        <div className={styles.candidateDetails}>
          <h3>{application.student_name}</h3>
          <p>{application.student_email}</p>
          <p>{application.student_profile?.phone || 'No phone provided'}</p>
          <span className={styles.jobBadge}>{application.job_title}</span>
        </div>
      </div>

      <div className={styles.candidateScores}>
        <div className={styles.scoreItem}>
          <span className={styles.scoreLabel}>Status</span>
          <span className={`${styles.statusBadge} ${styles[application.status]}`}>
            {applicationStatusLabel(application)}
          </span>
        </div>
        <div className={styles.scoreItem}>
          <span className={styles.scoreLabel}>Applied</span>
          <span className={styles.scoreText}>
            {new Date(application.applied_at).toLocaleDateString()}
          </span>
        </div>
        {identityChip && (
          <div className={styles.scoreItem}>
            <span className={styles.scoreLabel}>Identity</span>
            <span
              style={{
                color: identityChip.color,
                background: identityChip.background,
                border: `1px solid ${identityChip.border}`,
                borderRadius: 12,
                padding: '2px 10px',
                fontSize: 12,
                fontWeight: 600,
                whiteSpace: 'nowrap',
              }}
              title="Face verification result from the pre-interview identity check"
            >
              {identityChip.text}
            </span>
          </div>
        )}
        {cvScorePct !== null && (
          <div className={styles.scoreItem}>
            <span className={styles.scoreLabel}>CV Score</span>
            <div className={styles.scoreBar}>
              <div className={styles.scoreFill} style={{ width: `${cvScorePct}%`, background: '#4a90e2' }} />
              <span className={styles.scoreText}>{cvScorePct}%</span>
            </div>
          </div>
        )}
        {interviewScorePct !== null && (
          <div className={styles.scoreItem}>
            <span className={styles.scoreLabel}>Interview</span>
            <div className={styles.scoreBar}>
              <div className={styles.scoreFill} style={{ width: `${interviewScorePct}%`, background: '#27ae60' }} />
              <span className={styles.scoreText}>{interviewScorePct}%</span>
            </div>
          </div>
        )}
        {proctoringScorePct !== null && (
          <div className={styles.scoreItem}>
            <span className={styles.scoreLabel}>Proctoring</span>
            <div className={styles.scoreBar}>
              <div className={styles.scoreFill} style={{ width: `${proctoringScorePct}%`, background: '#8e44ad' }} />
              <span className={styles.scoreText}>{proctoringScorePct}%</span>
            </div>
          </div>
        )}
      </div>

      <div className={styles.candidateMeta}>
        <p><i className="fa fa-calendar" aria-hidden="true"></i> Applied: {new Date(application.applied_at).toLocaleDateString()}</p>
        <p><i className="fa fa-briefcase" aria-hidden="true"></i> {application.student_profile?.experience || 'No experience listed'}</p>
        <p><i className="fa fa-map-marker" aria-hidden="true"></i> {application.student_profile?.location || 'No location provided'}</p>
      </div>

      <div className={styles.candidateActions}>
        <select
          className={styles.statusSelect}
          value={normalizeStatus(application.status)}
          onChange={(e) => updateApplicationStatus(application._id, e.target.value)}
          title={`Current: ${applicationStatusLabel(application)} - Can only progress forward`}
          aria-label={`Update application status for ${application.student_name}`}
        >
          {availableStatuses.map(status => (
            <option key={status} value={status}>
              {statusLabel(status)}
            </option>
          ))}
        </select>
        {((typeof application.interview_score === 'number') || application.report_available) && (
          <>
            <button className={styles.secondaryButton} onClick={() => viewInterviewReport(application._id)}>
              <i className="fa fa-file-text-o" aria-hidden="true"></i> View Interview Report
            </button>
            <button className={styles.secondaryButton} onClick={() => viewProctoringReport(application._id)}>
                <i className="fa fa-eye" aria-hidden="true"></i> See Proctoring Result
            </button>
          </>
        )}
        <button
          className={styles.secondaryButton}
          onClick={() => {
            const token = getToken();
            const base = application.cv_url?.startsWith('http') ? application.cv_url : `${process.env.REACT_APP_API_URL}${application.cv_url || ''}`;
            const url = token ? `${base}?token=${encodeURIComponent(token)}` : base;
            window.open(url, '_blank', 'noopener');
          }}
          aria-label={`View CV for ${application.student_name}`}
        >
          <i className="fa fa-file-pdf-o" aria-hidden="true"></i> View CV
        </button>
      </div>
    </div>
  );
};

export default CandidateCard;

import React from 'react';
import styles from 'features/recruiter/pages/RecruiterDashboard.module.css';
import { getToken } from "shared/utils/session";
import { normalizeStatus, statusLabel, applicationStatusLabel } from "shared/utils/applicationStatus";

const CandidateCard = ({ application, updateApplicationStatus, viewInterviewReport, viewProctoringReport }) => {
  const candidateName = String(application.student_name || application.candidate_name || "Candidate");
  const appliedDate = application.applied_at ? new Date(application.applied_at) : null;
  const appliedLabel = appliedDate && Number.isFinite(appliedDate.getTime()) ? appliedDate.toLocaleDateString('en-IN', { timeZone:'Asia/Kolkata' }) : "Not available";
  const cvScorePct = (typeof application.cv_score === 'number')
    ? Math.round(application.cv_score)
    : (typeof application.similarity_score === 'number' ? Math.round(application.similarity_score * 100) : null);
  // Pre-shortlisted invitees skip CV scoring — the recruiter already selected
  // them, so the score is deliberately N/A rather than a computed number.
  const cvScoreWaived = Boolean(application.cv_score_waived) && cvScorePct === null;
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

  // Identity summary written by /register-face — the live capture is
  // similarity-scored against the candidate's uploaded ID card in the
  // background (score-only, never blocking) and the score is shown here so
  // the recruiter can judge who actually sat the interview.
  const identity = application.identity_verification;
  const identityChip = (() => {
    if (!identity || !identity.status) return null;
    const score = typeof identity.score === 'number' ? Math.round(identity.score) : null;
    const scoreText = score !== null ? `Face match ${score}%` : null;
    switch (identity.status) {
      case 'scored':
        if (score === null) return { text: 'Face match scored', className: styles.identityChipPending };
        return identity.matched === false
          ? { text: `⚠ ${scoreText}`, className: styles.identityChipMismatch }
          : { text: `✓ ${scoreText}`, className: styles.identityChipMatch };
      case 'score_pending':
        return { text: '🪪 Face match pending…', className: styles.identityChipPending };
      case 'score_unavailable':
      case 'unverified_system_unavailable':
        return { text: 'Face match unavailable', className: styles.identityChipUnknown };
      // Legacy statuses written before scoring became background-only:
      case 'verified':
        return { text: scoreText ? `✓ ${scoreText}` : '✓ ID Verified', className: styles.identityChipMatch };
      case 'registered_new':
        return { text: '🪪 ID Registered (1st interview)', className: styles.identityChipPending };
      case 'mismatch':
      case 'mismatch_blocked':
        return { text: scoreText ? `⚠ ${scoreText}` : '⚠ ID Mismatch', className: styles.identityChipMismatch };
      case 'unverified_monitor':
        return { text: scoreText ? `⚠ ${scoreText}` : 'ID Unverified', className: styles.identityChipUnknown };
      default:
        return null;
    }
  })();

  return (
    <div className={styles.candidateCard}>
      <div className={styles.candidateInfo}>
        <div className={styles.candidateAvatar}>
          {candidateName.trim().split(/\s+/).slice(0,2).map(n => n[0]).join('')}
        </div>
        <div className={styles.candidateDetails}>
          <h3>{candidateName}</h3>
          <p>{application.student_email}</p>
          <p>{application.student_profile?.phone || 'No phone provided'}</p>
          <span className={styles.jobBadge}>{application.job_title}</span>
          {application.candidate_account_type === 'invited' && (
            <span
              className={styles.invitedBadge}
              title="This candidate was invited by you — their account was created through a recruiter invite."
            >
              ✉ Invited
            </span>
          )}
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
            {appliedLabel}
          </span>
        </div>
        {identityChip && (
          <div className={styles.scoreItem}>
            <span className={styles.scoreLabel}>Identity</span>
            <span
              className={`${styles.identityChip} ${identityChip.className}`}
              title="Similarity between the interview face capture and the candidate's uploaded ID card (advisory — it never blocks the interview)"
            >
              {identityChip.text}
            </span>
          </div>
        )}
        {cvScoreWaived ? (
          <div className={styles.scoreItem}>
            <span className={styles.scoreLabel}>CV Score</span>
            <span
              className={`${styles.identityChip} ${styles.identityChipPending}`}
              title="CV scoring was skipped — you pre-shortlisted this candidate via an interview invite, so you decide based on the interview."
            >
              N/A — pre-shortlisted
            </span>
          </div>
        ) : cvScorePct !== null && (
          <div className={styles.scoreItem}>
            <div className={styles.scoreLabelRow}>
              <span className={styles.scoreLabel}>CV Score</span>
              <span className={styles.scoreValue}>{cvScorePct}%</span>
            </div>
            <div className={styles.scoreBar}>
              <div className={styles.scoreFill} style={{ width: `${cvScorePct}%`, background: '#4a90e2' }} />
            </div>
          </div>
        )}
        {interviewScorePct !== null && (
          <div className={styles.scoreItem}>
            <div className={styles.scoreLabelRow}>
              <span className={styles.scoreLabel}>Interview</span>
              <span className={styles.scoreValue}>{interviewScorePct}%</span>
            </div>
            <div className={styles.scoreBar}>
              <div className={styles.scoreFill} style={{ width: `${interviewScorePct}%`, background: '#27ae60' }} />
            </div>
          </div>
        )}
        {proctoringScorePct !== null && (
          <div className={styles.scoreItem}>
            <div className={styles.scoreLabelRow}>
              <span className={styles.scoreLabel}>Proctoring</span>
              <span className={styles.scoreValue}>{proctoringScorePct}%</span>
            </div>
            <div className={styles.scoreBar}>
              <div className={styles.scoreFill} style={{ width: `${proctoringScorePct}%`, background: '#8e44ad' }} />
            </div>
          </div>
        )}
      </div>

      <div className={styles.candidateMeta}>
        <p><i className="fa fa-calendar" aria-hidden="true"></i> Applied: {appliedLabel}</p>
        <p><i className="fa fa-briefcase" aria-hidden="true"></i> {application.student_profile?.experience || 'No experience listed'}</p>
        <p><i className="fa fa-map-marker" aria-hidden="true"></i> {application.student_profile?.location || 'No location provided'}</p>
      </div>

      <div className={styles.candidateActions}>
        <select
          className={styles.statusSelect}
          value={normalizeStatus(application.status)}
          onChange={(e) => updateApplicationStatus(application._id, e.target.value)}
          title={`Current: ${applicationStatusLabel(application)} - Can only progress forward`}
          aria-label={`Update application status for ${candidateName}`}
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
          disabled={!application.cv_url}
          title={!application.cv_url ? "No CV document available" : "Open CV document"}
          aria-label={`View CV for ${candidateName}`}
        >
          <i className="fa fa-file-pdf-o" aria-hidden="true"></i> View CV
        </button>
      </div>
    </div>
  );
};

export default CandidateCard;

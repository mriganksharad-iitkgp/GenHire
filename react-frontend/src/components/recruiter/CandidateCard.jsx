import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';

const CandidateCard = ({ application, displayStatus, updateApplicationStatus, viewInterviewReport, viewProctoringReport }) => {
  const cvScorePct = (typeof application.cv_score === 'number')
    ? Math.round(application.cv_score)
    : (typeof application.similarity_score === 'number' ? Math.round(application.similarity_score * 100) : null);
  const interviewScorePct = (typeof application.interview_score === 'number')
    ? Math.round(application.interview_score)
    : null;

  // Define the status progression hierarchy
  const statusHierarchy = ['pending', 'reviewed', 'shortlisted', 'interviewed', 'selected', 'rejected'];
  
  // Get available status options based on current status (one-way progression)
  const getAvailableStatusOptions = (currentStatus) => {
    const currentIndex = statusHierarchy.indexOf(currentStatus);
    
    // If current status is not found, default to all options
    if (currentIndex === -1) {
      return statusHierarchy;
    }
    
    // Allow current status and all subsequent statuses
    const availableStatuses = statusHierarchy.slice(currentIndex);
    
    // Special case: if interviewed, can go to either selected or rejected
    if (currentStatus === 'interviewed') {
      return ['interviewed', 'selected', 'rejected'];
    }
    
    // Special case: if selected or rejected, no further progression
    if (currentStatus === 'selected' || currentStatus === 'rejected') {
      return [currentStatus];
    }
    
    return availableStatuses;
  };
  
  const availableStatuses = getAvailableStatusOptions(application.status);

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
            {displayStatus(application.status)}
          </span>
        </div>
        <div className={styles.scoreItem}>
          <span className={styles.scoreLabel}>Applied</span>
          <span className={styles.scoreText}>
            {new Date(application.applied_at).toLocaleDateString()}
          </span>
        </div>
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
      </div>

      <div className={styles.candidateMeta}>
        <p><i className="fa fa-calendar"></i> Applied: {new Date(application.applied_at).toLocaleDateString()}</p>
        <p><i className="fa fa-briefcase"></i> {application.student_profile?.experience || 'No experience listed'}</p>
        <p><i className="fa fa-map-marker"></i> {application.student_profile?.location || 'No location provided'}</p>
      </div>

      <div className={styles.candidateActions}>
        <select 
          className={styles.statusSelect}
          value={application.status}
          onChange={(e) => updateApplicationStatus(application._id, e.target.value)}
          title={`Current: ${displayStatus(application.status)} - Can only progress forward`}
        >
          {availableStatuses.map(status => (
            <option key={status} value={status}>
              {status === 'pending' && 'Pending'}
              {status === 'reviewed' && 'Reviewed'}
              {status === 'shortlisted' && 'Shortlisted'}
              {status === 'interviewed' && 'Interviewed'}
              {status === 'selected' && 'Selected'}
              {status === 'rejected' && 'Rejected'}
            </option>
          ))}
        </select>
        {((typeof application.interview_score === 'number') || application.report_available) && (
          <>
            <button className={styles.secondaryButton} onClick={() => viewInterviewReport(application._id)}>
              <i className="fa fa-file-text-o"></i> View Interview Report
            </button>
            <button className={styles.secondaryButton} onClick={() => viewProctoringReport(application._id)}>
                <i className="fa fa-eye"></i> See Proctoring Result
            </button>
          </>
        )}
        <button
          className={styles.secondaryButton}
          onClick={() => {
            const token = localStorage.getItem('companyxyz-token');
            const base = application.cv_url?.startsWith('http') ? application.cv_url : `${process.env.REACT_APP_API_URL}${application.cv_url || ''}`;
            const url = token ? `${base}?token=${encodeURIComponent(token)}` : base;
            window.open(url, '_blank', 'noopener');
          }}
        >
          <i className="fa fa-file-pdf-o"></i> View CV
        </button>
      </div>
    </div>
  );
};

export default CandidateCard;

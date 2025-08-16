import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';

const CandidateCard = ({ application, displayStatus, updateApplicationStatus, viewInterviewReport }) => {
  const cvScorePct = (typeof application.cv_score === 'number')
    ? Math.round(application.cv_score)
    : (typeof application.similarity_score === 'number' ? Math.round(application.similarity_score * 100) : null);
  const interviewScorePct = (typeof application.interview_score === 'number')
    ? Math.round(application.interview_score)
    : null;

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
        >
          <option value="pending">Pending</option>
          <option value="reviewed">Reviewed</option>
          <option value="shortlisted">Shortlisted</option>
          <option value="interviewed">Interviewed</option>
          <option value="selected">Selected</option>
          <option value="rejected">Rejected</option>
        </select>
        {((typeof application.interview_score === 'number') || application.report_available) && (
          <button className={styles.secondaryButton} onClick={() => viewInterviewReport(application._id)}>
            <i className="fa fa-file-text-o"></i> View Interview Report
          </button>
        )}
        <button
          className={styles.secondaryButton}
          onClick={() => {
            const token = localStorage.getItem('companyxyz-token');
            const base = application.cv_url?.startsWith('http') ? application.cv_url : `http://localhost:5000${application.cv_url || ''}`;
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

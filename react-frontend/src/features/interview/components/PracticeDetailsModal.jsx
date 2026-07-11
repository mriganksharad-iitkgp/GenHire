import React from 'react';
import styles from './PracticeDetailsModal.module.css';

const PracticeDetailsModal = ({ isOpen, onClose, session, getRoleName, getRoleIcon }) => {
  if (!isOpen || !session) return null;

  const roles = [
    { id: 'software-engineer', name: 'Software Engineer', icon: 'fa-code', description: 'Full stack development, algorithms, system design' },
    { id: 'data-scientist', name: 'Data Scientist', icon: 'fa-line-chart', description: 'Machine learning, statistics, data analysis' },
    { id: 'product-manager', name: 'Product Manager', icon: 'fa-tasks', description: 'Product strategy, user research, stakeholder management' },
    { id: 'business-analyst', name: 'Business Analyst', icon: 'fa-briefcase', description: 'Requirements gathering, process improvement, analytics' },
    { id: 'fullstack-developer', name: 'Full Stack Developer', icon: 'fa-laptop', description: 'Frontend & backend development, databases, APIs' },
    { id: 'devops-engineer', name: 'DevOps Engineer', icon: 'fa-server', description: 'CI/CD, infrastructure, cloud services, automation' }
  ];

  const roleInfo = roles.find(r => r.id === session.role) || {};

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h2>
            <i className={`fa ${getRoleIcon?.(session.role) || roleInfo.icon || 'fa-briefcase'}`}></i>
            Practice Session Details
          </h2>
          <button className={styles.closeButton} onClick={onClose}>
            <i className="fa fa-times"></i>
          </button>
        </div>

        <div className={styles.modalBody}>
          {/* Role Information */}
          <div className={styles.section}>
            <h3><i className="fa fa-briefcase"></i> Role Information</h3>
            <div className={styles.roleCard}>
              <div className={styles.roleHeader}>
                <div className={styles.roleIcon}>
                  <i className={`fa ${getRoleIcon?.(session.role) || roleInfo.icon || 'fa-briefcase'}`}></i>
                </div>
                <div className={styles.roleInfo}>
                  <h4>{getRoleName?.(session.role) || roleInfo.name || session.role}</h4>
                  {roleInfo.description && (
                    <p className={styles.roleDescription}>{roleInfo.description}</p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Session Information */}
          <div className={styles.section}>
            <h3><i className="fa fa-info-circle"></i> Session Information</h3>
            <div className={styles.infoGrid}>
              <div className={styles.infoCard}>
                <div className={styles.infoIcon}>
                  <i className="fa fa-hashtag"></i>
                </div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>Session ID</span>
                  <span className={styles.infoValue}>{session.session_id}</span>
                </div>
              </div>

              <div className={styles.infoCard}>
                <div className={styles.infoIcon}>
                  <i className="fa fa-calendar"></i>
                </div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>Date & Time</span>
                  <span className={styles.infoValue}>
                    {new Date(session.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata',
                      dateStyle: 'medium',
                      timeStyle: 'short'
                    })}
                  </span>
                </div>
              </div>

              <div className={styles.infoCard}>
                <div className={styles.infoIcon}>
                  <i className="fa fa-clock-o"></i>
                </div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>Status</span>
                  <span className={`${styles.infoValue} ${styles.statusBadge}`}>
                    {session.status === 'completed' || session.status === 'ended' ? 'Completed' : 'In Progress'}
                  </span>
                </div>
              </div>

              <div className={styles.infoCard}>
                <div className={styles.infoIcon}>
                  <i className="fa fa-map-marker"></i>
                </div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>Mode</span>
                  <span className={styles.infoValue}>Practice Interview</span>
                </div>
              </div>
            </div>
          </div>

          {/* Performance Scores */}
          <div className={styles.section}>
            <h3><i className="fa fa-line-chart"></i> Performance Scores</h3>
            <div className={styles.scoresContainer}>
              <div className={styles.scoreCard}>
                <div className={styles.scoreIcon} style={{ background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)' }}>
                  <i className="fa fa-file-text"></i>
                </div>
                <div className={styles.scoreInfo}>
                  <span className={styles.scoreLabel}>CV Match Score</span>
                  <div className={styles.scoreValue}>
                    <span className={styles.scoreNumber}>{Math.round((session.cv_score || 0) * 100)}%</span>
                    <div className={styles.scoreBar}>
                      <div 
                        className={styles.scoreBarFill} 
                        style={{ width: `${Math.round((session.cv_score || 0) * 100)}%`, background: '#3b82f6' }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>

              <div className={styles.scoreCard}>
                <div className={styles.scoreIcon} style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}>
                  <i className="fa fa-comments"></i>
                </div>
                <div className={styles.scoreInfo}>
                  <span className={styles.scoreLabel}>Interview Performance</span>
                  <div className={styles.scoreValue}>
                    <span className={styles.scoreNumber}>{session.interview_score || 0}%</span>
                    <div className={styles.scoreBar}>
                      <div 
                        className={styles.scoreBarFill} 
                        style={{ width: `${session.interview_score || 0}%`, background: '#10b981' }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>

              <div className={styles.scoreCard}>
                <div className={styles.scoreIcon} style={{ background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' }}>
                  <i className="fa fa-eye"></i>
                </div>
                <div className={styles.scoreInfo}>
                  <span className={styles.scoreLabel}>Proctoring Score</span>
                  <div className={styles.scoreValue}>
                    <span className={styles.scoreNumber}>{session.proctoring_score || 90}%</span>
                    <div className={styles.scoreBar}>
                      <div 
                        className={styles.scoreBarFill} 
                        style={{ width: `${session.proctoring_score || 90}%`, background: '#f59e0b' }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* CV Source Information */}
          {session.cv_source && (
            <div className={styles.section}>
              <h3><i className="fa fa-file-pdf-o"></i> CV Source</h3>
              <div className={styles.card}>
                <div className={styles.cardDetail}>
                  <i className="fa fa-check-circle" style={{ color: '#10b981', marginRight: '8px' }}></i>
                  {session.cv_source === 'cv_pdf_selected' && 'Selected CV PDF'}
                  {session.cv_source === 'cv_pdf_primary' && 'Primary CV PDF'}
                  {session.cv_source === 'cv_manual_entry' && 'Manual CV Details'}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className={styles.modalFooter}>
          <button className={styles.closeBtn} onClick={onClose}>
            <i className="fa fa-times"></i> Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default PracticeDetailsModal;

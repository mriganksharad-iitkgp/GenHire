import React from 'react';
import styles from './CVDetailsModal.module.css';

const CVDetailsModal = ({ isOpen, onClose, cvDetails }) => {
  if (!isOpen || !cvDetails) return null;

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h2>
            <i className="fa fa-file-text-o"></i> Profile CV Details
          </h2>
          <button className={styles.closeButton} onClick={onClose}>
            <i className="fa fa-times"></i>
          </button>
        </div>

        <div className={styles.modalBody}>
          {/* Education Section */}
          {cvDetails.education && cvDetails.education.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-graduation-cap"></i> Education</h3>
              {cvDetails.education.map((edu, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{edu.degree}</div>
                  <div className={styles.cardSubtitle}>{edu.institution}</div>
                  <div className={styles.cardMeta}>
                    <span><i className="fa fa-book"></i> {edu.field_of_study}</span>
                    <span><i className="fa fa-calendar"></i> {edu.year_duration}</span>
                  </div>
                  {edu.grade && <div className={styles.cardDetail}>Grade: {edu.grade}</div>}
                </div>
              ))}
            </div>
          )}

          {/* Work Experience Section */}
          {cvDetails.work_experience && cvDetails.work_experience.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-briefcase"></i> Work Experience</h3>
              {cvDetails.work_experience.map((work, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{work.job_title}</div>
                  <div className={styles.cardSubtitle}>{work.company}</div>
                  <div className={styles.cardMeta}>
                    <span><i className="fa fa-calendar"></i> {work.duration}</span>
                  </div>
                  {work.responsibilities && (
                    <div className={styles.cardDetail}>{work.responsibilities}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Skills Section */}
          {cvDetails.skills && cvDetails.skills.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-code"></i> Skills</h3>
              <div className={styles.tagsContainer}>
                {cvDetails.skills.map((skill, index) => (
                  <span key={index} className={styles.tag}>
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Projects Section */}
          {cvDetails.projects && cvDetails.projects.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-folder-open"></i> Projects</h3>
              {cvDetails.projects.map((project, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{project.title}</div>
                  <div className={styles.cardDetail}>{project.description}</div>
                  {project.technologies && (
                    <div className={styles.cardMeta}>
                      <span><i className="fa fa-wrench"></i> {project.technologies}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Certifications Section */}
          {cvDetails.certifications && cvDetails.certifications.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-certificate"></i> Certifications</h3>
              {cvDetails.certifications.map((cert, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{cert.name}</div>
                  <div className={styles.cardSubtitle}>{cert.issuer}</div>
                  {cert.date && (
                    <div className={styles.cardMeta}>
                      <span><i className="fa fa-calendar"></i> {cert.date}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Achievements Section */}
          {cvDetails.achievements && cvDetails.achievements.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-trophy"></i> Achievements</h3>
              {cvDetails.achievements.map((achievement, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{achievement.title}</div>
                  {achievement.organization && (
                    <div className={styles.cardSubtitle}>{achievement.organization}</div>
                  )}
                  <div className={styles.cardMeta}>
                    {achievement.date && (
                      <span><i className="fa fa-calendar"></i> {achievement.date}</span>
                    )}
                    {achievement.level && (
                      <span><i className="fa fa-trophy"></i> {achievement.level}</span>
                    )}
                  </div>
                  {achievement.description && (
                    <div className={styles.cardDetail}>{achievement.description}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Languages Section */}
          {cvDetails.languages && cvDetails.languages.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-language"></i> Languages</h3>
              <div className={styles.tagsContainer}>
                {cvDetails.languages.map((lang, index) => (
                  <span key={index} className={styles.tag}>
                    {typeof lang === 'string' ? lang : `${lang.language}${lang.proficiency ? ` (${lang.proficiency})` : ''}`}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Competitions Section */}
          {cvDetails.competitions && cvDetails.competitions.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-star"></i> Competitions</h3>
              {cvDetails.competitions.map((comp, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{comp.name}</div>
                  {comp.organizer && (
                    <div className={styles.cardSubtitle}>{comp.organizer}</div>
                  )}
                  <div className={styles.cardMeta}>
                    {comp.position && (
                      <span><i className="fa fa-trophy"></i> {comp.position}</span>
                    )}
                    {comp.date && (
                      <span><i className="fa fa-calendar"></i> {comp.date}</span>
                    )}
                  </div>
                  {comp.description && (
                    <div className={styles.cardDetail}>{comp.description}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Internships Section */}
          {cvDetails.internships && cvDetails.internships.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-building-o"></i> Internships</h3>
              {cvDetails.internships.map((intern, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{intern.position}</div>
                  <div className={styles.cardSubtitle}>{intern.company}</div>
                  <div className={styles.cardMeta}>
                    {intern.duration && (
                      <span><i className="fa fa-clock-o"></i> {intern.duration}</span>
                    )}
                    {intern.location && (
                      <span><i className="fa fa-map-marker"></i> {intern.location}</span>
                    )}
                  </div>
                  {intern.description && (
                    <div className={styles.cardDetail}>{intern.description}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Positions Held Section */}
          {cvDetails.positionsHeld && cvDetails.positionsHeld.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-user"></i> Positions Held</h3>
              {cvDetails.positionsHeld.map((position, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{position.title}</div>
                  <div className={styles.cardSubtitle}>{position.organization}</div>
                  <div className={styles.cardMeta}>
                    {position.duration && (
                      <span><i className="fa fa-clock-o"></i> {position.duration}</span>
                    )}
                    {position.teamSize && (
                      <span><i className="fa fa-users"></i> Team Size: {position.teamSize}</span>
                    )}
                    {position.location && (
                      <span><i className="fa fa-map-marker"></i> {position.location}</span>
                    )}
                  </div>
                  {position.responsibilities && (
                    <div className={styles.cardDetail}>
                      <strong>Responsibilities:</strong> {position.responsibilities}
                    </div>
                  )}
                  {position.achievements && (
                    <div className={styles.cardDetail}>
                      <strong>Achievements:</strong> {position.achievements}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Coursework Section */}
          {cvDetails.coursework && cvDetails.coursework.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-book"></i> Relevant Coursework</h3>
              {cvDetails.coursework.map((course, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{course.course}</div>
                  {course.institution && (
                    <div className={styles.cardSubtitle}>{course.institution}</div>
                  )}
                  <div className={styles.cardMeta}>
                    {course.duration && (
                      <span><i className="fa fa-clock-o"></i> {course.duration}</span>
                    )}
                    {course.certification && (
                      <span><i className="fa fa-certificate"></i> {course.certification}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Extracurricular Activities Section */}
          {cvDetails.extracurricular && cvDetails.extracurricular.length > 0 && (
            <div className={styles.section}>
              <h3><i className="fa fa-users"></i> Extracurricular Activities</h3>
              {cvDetails.extracurricular.map((activity, index) => (
                <div key={index} className={styles.card}>
                  <div className={styles.cardTitle}>{activity.activity}</div>
                  {activity.role && (
                    <div className={styles.cardSubtitle}>{activity.role}</div>
                  )}
                  {activity.duration && (
                    <div className={styles.cardMeta}>
                      <span><i className="fa fa-clock-o"></i> {activity.duration}</span>
                    </div>
                  )}
                  {activity.description && (
                    <div className={styles.cardDetail}>{activity.description}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Salary Expectations Section */}
          {cvDetails.salary_expectations && (
            <div className={styles.section}>
              <h3><i className="fa fa-money"></i> Salary Expectations</h3>
              <div className={styles.card}>
                <div className={styles.cardDetail}>{cvDetails.salary_expectations}</div>
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

export default CVDetailsModal;

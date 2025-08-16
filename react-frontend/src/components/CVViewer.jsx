import React, { useEffect, useMemo, useState } from 'react';
import styles from './CVViewer.module.css';

const CVViewer = ({ isOpen, onClose, candidate }) => {
  // Handle Escape key to close modal
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      // Prevent background scrolling
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  // Build a view URL for the PDF
  const pdfUrl = useMemo(() => {
    // If application-shaped data with _id present, use the secure backend route
  if (candidate && candidate._id) {
      // Frontend runs on port 3000; backend on 5000
      return `http://localhost:5000/api/applications/${candidate._id}/cv`;
    }
  return candidate?.cvUrl || candidate?.student_profile?.cv_path || '#';
  }, [candidate]);

  // Local Blob URL for embedded preview (so we can attach Authorization)
  const [blobUrl, setBlobUrl] = useState(null);

  useEffect(() => {
    let revoked = false;
    let objectUrl = null;
    const loadPdf = async () => {
      if (!isOpen || !pdfUrl || pdfUrl === '#') return;
      try {
        // Try fetching with Authorization; if cross-origin and no auth needed, fallback to using the URL directly
        const token = localStorage.getItem('companyxyz-token');
        const res = await fetch(pdfUrl, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (!res.ok) {
          // If unauthorized or other error, skip embedding
          setBlobUrl(null);
          return;
        }
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!revoked) setBlobUrl(objectUrl);
      } catch (e) {
        setBlobUrl(null);
      }
    };
    loadPdf();
    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [isOpen, pdfUrl]);

  // After all hooks are declared, we can conditionally render nothing
  if (!isOpen || !candidate) return null;

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleDownloadCV = () => {
    // Best-effort: if backend exposes a CV path/url on the application/student, use it; otherwise noop
    const displayName = (candidate.name || candidate.student_name || 'candidate').replace(/\s+/g, '_');
    const href = blobUrl || pdfUrl;
    if (href === '#') return;
    const link = document.createElement('a');
    link.href = href;
    link.download = `${displayName}_CV.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Sample CV data - in a real app, this would come from the backend
  const cvData = {
    personalInfo: {
      name: candidate.name || candidate.student_name,
      email: candidate.email || candidate.student_email,
      phone: candidate.phone || candidate.student_profile?.phone,
      location: candidate.location || candidate.student_profile?.location,
      experience: candidate.experience || candidate.student_profile?.experience
    },
    summary: "Experienced professional with a strong background in business development and strategic partnerships. Proven track record of driving revenue growth and building lasting client relationships.",
    experience: [
      {
        position: "Senior Business Development Manager",
        company: "Tech Solutions Inc.",
        duration: "2020 - Present",
        responsibilities: [
          "Led business development initiatives resulting in 40% revenue growth",
          "Managed key client relationships worth $2M+ annually",
          "Developed and executed strategic partnership agreements"
        ]
      },
      {
        position: "Business Development Associate",
        company: "Growth Partners LLC",
        duration: "2018 - 2020",
        responsibilities: [
          "Identified and pursued new business opportunities",
          "Conducted market research and competitive analysis",
          "Supported senior team in client presentations"
        ]
      }
    ],
    education: [
      {
        degree: "MBA in Business Administration",
        institution: "Stanford University",
        year: "2018"
      },
      {
        degree: "Bachelor of Commerce",
        institution: "UC Berkeley",
        year: "2016"
      }
    ],
    skills: candidate.skills || ["Business Development", "Strategic Planning", "Client Relations"]
  };

  return (
    <div className={styles.modalOverlay} onClick={handleOverlayClick}>
      <div className={styles.modalContent}>
        <div className={styles.modalHeader}>
          <h2>CV - {candidate.name}</h2>
          <div className={styles.headerActions}>
            <button 
              className={styles.downloadButton}
              onClick={handleDownloadCV}
              title="Download CV"
            >
              <i className="fa fa-download"></i> Download
            </button>
            <button 
              className={styles.closeButton} 
              onClick={onClose}
              title="Close"
            >
              <i className="fa fa-times"></i>
            </button>
          </div>
        </div>

        <div className={styles.cvContent}>
          {/* Embedded PDF preview */}
      {(blobUrl || (pdfUrl && pdfUrl !== '#')) && (
            <section className={styles.section}>
              <h3>CV Document</h3>
              <div className={styles.pdfContainer}>
        <iframe title="cv-pdf" src={blobUrl || pdfUrl} className={styles.pdfFrame} />
              </div>
            </section>
          )}

          {/* Personal Information */}
          <section className={styles.section}>
            <h3>Personal Information</h3>
            <div className={styles.personalInfo}>
              <div className={styles.infoItem}>
                <strong>Name:</strong> {cvData.personalInfo.name}
              </div>
              <div className={styles.infoItem}>
                <strong>Email:</strong> {cvData.personalInfo.email}
              </div>
              <div className={styles.infoItem}>
                <strong>Phone:</strong> {cvData.personalInfo.phone}
              </div>
              <div className={styles.infoItem}>
                <strong>Location:</strong> {cvData.personalInfo.location}
              </div>
              <div className={styles.infoItem}>
                <strong>Experience:</strong> {cvData.personalInfo.experience}
              </div>
            </div>
          </section>

          {/* Professional Summary */}
          <section className={styles.section}>
            <h3>Professional Summary</h3>
            <p className={styles.summary}>{cvData.summary}</p>
          </section>

          {/* Work Experience */}
          <section className={styles.section}>
            <h3>Work Experience</h3>
            {cvData.experience.map((exp, index) => (
              <div key={index} className={styles.experienceItem}>
                <div className={styles.experienceHeader}>
                  <h4>{exp.position}</h4>
                  <span className={styles.duration}>{exp.duration}</span>
                </div>
                <p className={styles.company}>{exp.company}</p>
                <ul className={styles.responsibilities}>
                  {exp.responsibilities.map((resp, idx) => (
                    <li key={idx}>{resp}</li>
                  ))}
                </ul>
              </div>
            ))}
          </section>

          {/* Education */}
          <section className={styles.section}>
            <h3>Education</h3>
            {cvData.education.map((edu, index) => (
              <div key={index} className={styles.educationItem}>
                <h4>{edu.degree}</h4>
                <p>{edu.institution} - {edu.year}</p>
              </div>
            ))}
          </section>

          {/* Skills */}
          <section className={styles.section}>
            <h3>Skills</h3>
            <div className={styles.skillsContainer}>
              {cvData.skills.map((skill, index) => (
                <span key={index} className={styles.skillTag}>
                  {skill}
                </span>
              ))}
            </div>
          </section>

          {/* CV Match Score */}
          <section className={styles.section}>
            <h3>CV Analysis</h3>
            <div className={styles.matchScore}>
              <div className={styles.scoreItem}>
                <span className={styles.scoreLabel}>CV Match Score:</span>
                <div className={styles.scoreBar}>
                  <div 
                    className={styles.scoreFill}
                    style={{ width: `${candidate.cvMatchScore || 80}%` }}
                  ></div>
                  <span className={styles.scoreText}>{candidate.cvMatchScore || 80}%</span>
                </div>
              </div>
              {candidate.interviewScore && (
                <div className={styles.scoreItem}>
                  <span className={styles.scoreLabel}>Interview Score:</span>
                  <div className={styles.scoreBar}>
                    <div 
                      className={styles.scoreFill}
                      style={{ width: `${candidate.interviewScore}%` }}
                    ></div>
                    <span className={styles.scoreText}>{candidate.interviewScore}%</span>
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default CVViewer;

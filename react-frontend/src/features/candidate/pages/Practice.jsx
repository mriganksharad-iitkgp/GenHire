import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Toast from "shared/components/ui/Toast";
import SkeletonCard from "shared/components/ui/SkeletonCard";
import InterviewReportModal from "features/interview/components/InterviewReportModal";
import Pagination from "shared/components/ui/Pagination";
import CVSelectionModal from "features/candidate/components/CVSelectionModal";
import CVDetailsModal from "features/candidate/components/CVDetailsModal";
import PracticeDetailsModal from "features/interview/components/PracticeDetailsModal";
import JDDetailsModal from "features/recruiter/components/JDDetailsModal";
import { PRACTICE_ROLE_OPTIONS } from "shared/constants/jobTaxonomy";
import styles from "./Practice.module.css";
import { getToken, getUser, clearSession, isLoggedIn } from "shared/utils/session";
import { authedFetch } from "shared/api/client";

const Practice = () => {
  const navigate = useNavigate();
  const DIFFICULTIES = [
    {
      id: "easy",
      label: "Easy",
      icon: "fa-leaf",
      color: "#22c55e",
      bg: "#f0fdf4",
      border: "#86efac",
      desc: "Broad questions, forgiving pace — ideal for warming up or beginners.",
    },
    {
      id: "medium",
      label: "Medium",
      icon: "fa-bar-chart",
      color: "#6366f1",
      bg: "#eef2ff",
      border: "#a5b4fc",
      desc: "Standard depth and follow-ups — the typical real-world interview experience.",
    },
    {
      id: "hard",
      label: "Hard",
      icon: "fa-bolt",
      color: "#ef4444",
      bg: "#fef2f2",
      border: "#fca5a5",
      desc: "Challenging probing questions and tight pacing — sharpen under pressure.",
    },
  ];

  const [selectedRole, setSelectedRole] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [uploadedJD, setUploadedJD] = useState(null);
  const [isStarting, setIsStarting] = useState(false);
  const [sessionLaunched, setSessionLaunched] = useState(false);
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [pendingDeepLink, setPendingDeepLink] = useState(null);
  const [practiceHistory, setPracticeHistory] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [selectedReport, setSelectedReport] = useState(null);
  const [showReportModal, setShowReportModal] = useState(false);
  const [showCVModal, setShowCVModal] = useState(false);
  const [proctoringEnabled, setProctoringEnabled] = useState(false);

  // Pagination state for practice history
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  // Toast state
  const [toast, setToast] = useState(null);

  // Show toast function
  const showToast = (message, type = "info") => {
    setToast({ message, type });
  };

  // Predefined roles for quick practice
  const roles = PRACTICE_ROLE_OPTIONS;

  // Fetch practice history on component mount
  useEffect(() => {
    fetchPracticeHistory();
  }, []);

  // When user returns from GenHire secure browser, reset loading state and refresh history
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        setIsStarting(false);
        if (sessionLaunched) {
          setSessionLaunched(false);
          showToast("Welcome back! Your practice report will appear in history once the session is processed.", "info");
          fetchPracticeHistory();
        }
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [sessionLaunched]);

  // Fetch practice interview history
  const fetchPracticeHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const token = getToken();
      const response = await authedFetch(
        `${process.env.REACT_APP_API_URL}/api/practice/history`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (response.ok) {
        const data = await response.json();
        setPracticeHistory(data.sessions || []);
      }
    } catch (error) {
      console.error("Error fetching practice history:", error);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // View practice interview report
  const viewPracticeReport = async (sessionId) => {
    try {
      const token = getToken();
      const response = await authedFetch(
        `${process.env.REACT_APP_API_URL}/api/practice/${sessionId}/report`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (response.ok) {
        const report = await response.json();
        setSelectedReport(report);
        setShowReportModal(true);
      } else {
        showToast("Failed to load practice report", "error");
      }
    } catch (error) {
      console.error("Error fetching practice report:", error);
      showToast("Error loading practice report", "error");
    }
  };

  // Handle JD file upload
  const handleJDUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.type !== "application/pdf") {
        showToast("Please upload a PDF file", "error");
        return;
      }
      setUploadedJD(file);
      showToast("Job Description uploaded successfully!", "success");
    }
  };

  // Start practice interview - Show CV selection modal first
  const handleStartPractice = () => {
    // Validation
    if (!selectedRole) {
      showToast("Please select a role to practice", "error");
      return;
    }

    if (selectedRole === "custom" && !uploadedJD) {
      showToast("Please upload a job description for custom practice", "error");
      return;
    }

    // Show CV selection modal
    setShowCVModal(true);
  };

  // Actually start practice with selected CV
  const handleCVSelectionSubmit = async (cvSelection) => {
    setIsStarting(true);

    try {
      const formData = new FormData();
      formData.append("role", selectedRole);
      formData.append("difficulty", difficulty);
      formData.append("proctoring_enabled", proctoringEnabled ? "true" : "false");

      if (selectedRole === "custom" && uploadedJD) {
        formData.append("jd", uploadedJD);
      }

      // Add CV ID if selected
      if (cvSelection.cv_id) {
        formData.append("cv_id", cvSelection.cv_id);
      }

      const token = getToken();
      const response = await authedFetch(
        `${process.env.REACT_APP_API_URL}/api/practice/start`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        },
      );

      if (!response.ok) {
        const errorData = await response.json();
        const error = new Error(
          errorData.error || "Failed to start practice interview",
        );
        error.status = response.status;
        error.errorCode = errorData.error_code;
        error.redirect = errorData.redirect;
        throw error;
      }

      const data = await response.json();

      // Handle practice session launch
      if (window.electronAPI) {
        // If already inside secure browser, just navigate
        navigate(`/interview/${data.session_id}`, {
          state: {
            isPractice: true,
            practiceRole: selectedRole,
            sessionId: data.session_id,
            initialQuestion: data.initial_questions?.[0] || "",
            similarityScore: data.similarity_score || 0,
            cvScore: data.cv_score || 0,
            usageDeduction: data.usage_deduction || null,
            walletQuota: data.quota || null,
            // Pacing config so practice runs identically to real interviews
            questionDeadline: data.question_deadline || null,
            questionTimeoutSeconds: data.question_timeout_seconds || null,
            maxQuestions: data.max_questions || null,
          },
        });
        return;
      }

      showToast(`Launching Secure Browser for practice session...`, 'info');
      setSessionLaunched(true);

      // Generate the initialization payload for practice mode
      const payload = {
        isPractice: true,
        sessionId: data.session_id,
        initialQuestion: data.initial_questions?.[0] || "",
        similarityScore: data.similarity_score || 0,
        questionDeadline: data.question_deadline || null,
        questionTimeoutSeconds: data.question_timeout_seconds || null,
        maxQuestions: data.max_questions || null,
        proctoringConfig: {
          voice_detection: proctoringEnabled,
          object_detection: proctoringEnabled,
          eyeball_tracking: proctoringEnabled,
          gaze_heatmap: proctoringEnabled
        },
        token: getToken(),
        apiUrl: process.env.REACT_APP_API_URL || window.location.origin
      };

      const encodedPayload = btoa(JSON.stringify(payload));
      const customUri = `secure-interview://start?initData=${encodeURIComponent(encodedPayload)}`;

      // Store for retry after install
      setPendingDeepLink(customUri);

      // Fire deep link via hidden iframe
      const iframe = document.createElement("iframe");
      iframe.style.display = "none";
      iframe.src = customUri;
      document.body.appendChild(iframe);
      setTimeout(() => { if (document.body.contains(iframe)) document.body.removeChild(iframe); }, 5000);

      // If window still has focus after 4s → GenHire not installed
      const timeoutId = setTimeout(() => {
        if (document.hasFocus()) {
          const link = document.createElement('a');
          link.href = 'https://storage.googleapis.com/genhire-downloads/Genhire.exe';
          link.download = 'Genhire.exe';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          setShowDownloadModal(true);
        }
        setIsStarting(false);
      }, 4000);

      window.addEventListener('blur', () => {
        clearTimeout(timeoutId);
        setIsStarting(false);
      }, { once: true });

    } catch (error) {
      console.error("Error starting practice interview:", error);
      if (error?.status === 402) {
        showToast(
          error.message ||
            "Practice credits exhausted. Please upgrade your candidate plan.",
          "error",
        );
        const redirectPath = error?.redirect || "/candidate/subscription";
        navigate(redirectPath);
      } else {
        showToast(
          error.message || "Failed to start practice interview",
          "error",
        );
      }
      setIsStarting(false);
    }
  };

  // Helper function to get role icon
  function getRoleIcon(roleId) {
    const role = roles.find((r) => r.id === roleId);
    return role ? role.icon : "fa-briefcase";
  }

  // Helper function to get role name
  function getRoleName(roleId) {
    const role = roles.find((r) => r.id === roleId);
    return role ? role.name : roleId;
  }

  // State for CV details modal
  const [showCvDetailsModal, setShowCvDetailsModal] = useState(false);
  const [selectedCvDetails, setSelectedCvDetails] = useState(null);
  const [showPracticeDetailsModal, setShowPracticeDetailsModal] =
    useState(false);
  const [selectedPracticeSession, setSelectedPracticeSession] = useState(null);

  // Handle viewing CV for practice session
  const handleViewPracticeCV = async (session) => {
    // If cv_id exists, open PDF
    if (session.cv_id) {
      try {
        const token = getToken();
        const url = `${process.env.REACT_APP_API_URL}/api/cv/${session.cv_id}/preview`;

        const response = await authedFetch(url, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error("Failed to load CV");
        }

        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        window.open(blobUrl, "_blank");
      } catch (err) {
        console.error("Error opening CV:", err);
        showToast("Failed to open CV", "error");
      }
    } else {
      // If no cv_id, show manual CV details modal
      try {
        const token = getToken();
        const response = await authedFetch(
          `${process.env.REACT_APP_API_URL}/api/cv-details`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          },
        );

        if (response.ok) {
          const data = await response.json();
          setSelectedCvDetails(data.cv_details);
          setShowCvDetailsModal(true);
        } else {
          showToast("CV details not found", "info");
        }
      } catch (err) {
        console.error("Error fetching CV details:", err);
        showToast("Failed to load CV details", "error");
      }
    }
  };

  // State for JD details modal
  const [showJdDetailsModal, setShowJdDetailsModal] = useState(false);
  const [selectedJdSession, setSelectedJdSession] = useState(null);

  // Handle viewing practice session JD details
  const handleViewPracticeJD = (session) => {
    setSelectedJdSession(session);
    setShowJdDetailsModal(true);
  };

  return (
    <div className={styles.practiceContainer}>
      {/* Toast notifications */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      <div className={styles.content}>
        <div className={styles.welcomeSection}>
          <h2>Practice Interview Mode</h2>
          <p>
            Master your interview skills with AI-powered practice sessions.
            Select a role, practice in a realistic environment, and receive
            instant personalized feedback.
          </p>
        </div>

        <div className={styles.practiceContent}>
          {/* Role Selection */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>
              <i className="fa fa-briefcase"></i> Select Practice Role
            </h3>
            <div className={styles.rolesGrid}>
              {roles.map((role) => (
                <div
                  key={role.id}
                  className={`${styles.roleCard} ${selectedRole === role.id ? styles.selected : ""}`}
                  onClick={() => setSelectedRole(role.id)}
                >
                  <div className={styles.roleIcon}>
                    <i className={`fa ${role.icon}`}></i>
                  </div>
                  <h4>{role.name}</h4>
                  {selectedRole === role.id && (
                    <div className={styles.selectedBadge}>
                      <i className="fa fa-check-circle"></i>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* JD Upload (only for custom role) */}
          {selectedRole === "custom" && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>
                <i className="fa fa-file-pdf-o"></i> Upload Job Description
              </h3>

              <div className={styles.uploadSection}>
                <div className={styles.uploadCard}>
                  <div className={styles.uploadHeader}>
                    <h4>Job Description</h4>
                    <span className={styles.required}>
                      Required for custom practice
                    </span>
                  </div>
                  <div className={styles.uploadArea}>
                    <input
                      type="file"
                      id="jd-upload"
                      accept=".pdf"
                      onChange={handleJDUpload}
                      className={styles.fileInput}
                    />
                    <label htmlFor="jd-upload" className={styles.uploadLabel}>
                      {uploadedJD ? (
                        <>
                          <i
                            className="fa fa-check-circle"
                            style={{ color: "#10b981" }}
                          ></i>
                          <span>{uploadedJD.name}</span>
                          <span className={styles.uploadSubtext}>
                            Click to change
                          </span>
                        </>
                      ) : (
                        <>
                          <i className="fa fa-cloud-upload"></i>
                          <span>Click to upload Job Description</span>
                          <span className={styles.uploadSubtext}>
                            PDF format only
                          </span>
                        </>
                      )}
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Difficulty Selection */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>
              <i className="fa fa-sliders"></i> Interview Difficulty
            </h3>
            <div className={styles.difficultyGrid}>
              {DIFFICULTIES.map((d) => {
                const active = difficulty === d.id;
                return (
                  <div
                    key={d.id}
                    className={`${styles.difficultyCard} ${active ? styles.difficultyActive : ""}`}
                    style={active ? { background: d.bg, borderColor: d.border } : {}}
                    onClick={() => setDifficulty(d.id)}
                    role="radio"
                    aria-checked={active}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === " " && setDifficulty(d.id)}
                  >
                    <div
                      className={styles.difficultyIcon}
                      style={{ color: active ? d.color : "#94a3b8" }}
                    >
                      <i className={`fa ${d.icon}`}></i>
                    </div>
                    <div className={styles.difficultyLabel}
                      style={{ color: active ? d.color : "#1e293b" }}
                    >
                      {d.label}
                    </div>
                    <div className={styles.difficultyDesc}>{d.desc}</div>
                    {active && (
                      <div className={styles.difficultyCheck} style={{ color: d.color }}>
                        <i className="fa fa-check-circle"></i>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Proctoring */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>
              <i className="fa fa-shield"></i> Practice Proctoring
            </h3>
            <div className={styles.uploadSection}>
              <div className={styles.uploadCard}>
                <div className={styles.uploadHeader}>
                  <h4>Enable Proctoring</h4>
                  <span className={styles.required}>Optional</span>
                </div>
                <label style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "14px", color: "#334155" }}>
                  <input
                    type="checkbox"
                    checked={proctoringEnabled}
                    onChange={(e) => setProctoringEnabled(e.target.checked)}
                  />
                  Turn on proctoring for practice interview
                </label>
                <p style={{ marginTop: "10px", marginBottom: 0, fontSize: "13px", color: "#64748b" }}>
                  Credit deduction: {proctoringEnabled ? "50" : "30"} credits per practice session.
                </p>
              </div>
            </div>
          </div>

          {/* Start Button */}
          <div className={styles.actionSection}>
            <button
              className={styles.startButton}
              onClick={handleStartPractice}
              disabled={isStarting || !selectedRole}
            >
              {isStarting ? (
                <>
                  <i className="fa fa-spinner fa-spin"></i> Starting Practice
                  Interview...
                </>
              ) : (
                <>
                  <i className="fa fa-play-circle"></i> Start Practice Interview
                </>
              )}
            </button>
          </div>

          {/* Practice History Section */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>
              <i className="fa fa-history"></i> Practice History
            </h3>

            {isLoadingHistory ? (
              <div>
                {Array.from({ length: 3 }).map((_, i) => (
                  <SkeletonCard key={i} variant="practice" />
                ))}
              </div>
            ) : practiceHistory.length === 0 ? (
              <div className={styles.emptyState}>
                <i className="fa fa-inbox"></i>
                <p>
                  No practice interviews yet. Start your first practice session
                  above!
                </p>
              </div>
            ) : (
              <>
                <div className={styles.historyGrid}>
                  {(() => {
                    const completedSessions = practiceHistory.filter(
                      (session) =>
                        session.status === "completed" ||
                        session.status === "ended",
                    );
                    const startIndex = (currentPage - 1) * itemsPerPage;
                    const endIndex = startIndex + itemsPerPage;
                    const paginatedSessions = completedSessions.slice(
                      startIndex,
                      endIndex,
                    );
                    const totalPages = Math.ceil(
                      completedSessions.length / itemsPerPage,
                    );

                    return (
                      <>
                        {paginatedSessions.map((session) => (
                          <div
                            key={session.session_id}
                            className={styles.applicationCard}
                            data-status="ended"
                          >
                            {/* Card Header - Matching ApplicationsList */}
                            <div className={styles.applicationHeader}>
                              <div className={styles.companyAvatar}>
                                <div className={styles.practiceLogoWrapper}>
                                  <i
                                    className={`fa ${getRoleIcon(session.role)}`}
                                  ></i>
                                </div>
                              </div>
                              <div className={styles.jobTitleWrap}>
                                <h3>{getRoleName(session.role)}</h3>
                                <div className={styles.companySubtle}>
                                  Practice Mode
                                </div>
                              </div>
                              <div className={styles.headerBadges}>
                                <span
                                  className={`${styles.statusBadge} ${styles.ended}`}
                                >
                                  ENDED
                                </span>
                              </div>
                            </div>

                            {/* Application Details - Matching ApplicationsList */}
                            <div className={styles.applicationDetails}>
                              <div className={styles.metaRow}>
                                <div className={styles.metaItem}>
                                  <i className="fa fa-building"></i>
                                  <span>Practice Session</span>
                                </div>
                                <div className={styles.metaItem}>
                                  <i className="fa fa-map-marker"></i>
                                  <span>Online</span>
                                </div>
                                <div className={styles.metaItem}>
                                  <i className="fa fa-calendar"></i>
                                  <span>
                                    Completed{" "}
                                    {new Date(
                                      session.created_at,
                                    ).toLocaleDateString()}
                                  </span>
                                </div>
                              </div>
                              <div className={styles.tagsRow}>
                                <span className={styles.chip}>
                                  <i className="fa fa-history"></i> Practice
                                </span>
                              </div>
                            </div>

                            {/* Application Actions - Matching ApplicationsList with scores */}
                            <div className={styles.applicationActions}>
                              <div className={styles.scoresRow}>
                                <div className={styles.scorePill}>
                                  <span className={styles.pillLabel}>
                                    CV Score
                                  </span>
                                  <span className={styles.pillValue}>
                                    {Math.round((session.cv_score || 0) * 100)}%
                                  </span>
                                  <div className={styles.miniBar}>
                                    <div
                                      style={{
                                        width: `${Math.round((session.cv_score || 0) * 100)}%`,
                                        backgroundColor: "#3b82f6",
                                      }}
                                    ></div>
                                  </div>
                                </div>
                                <div className={styles.scorePill}>
                                  <span className={styles.pillLabel}>
                                    Interview
                                  </span>
                                  <span className={styles.pillValue}>
                                    {session.interview_score || 0}%
                                  </span>
                                  <div className={styles.miniBar}>
                                    <div
                                      style={{
                                        width: `${session.interview_score || 0}%`,
                                        backgroundColor: "#10b981",
                                      }}
                                    ></div>
                                  </div>
                                </div>
                                <div className={styles.scorePill}>
                                  <span className={styles.pillLabel}>
                                    Proctoring
                                  </span>
                                  <span className={styles.pillValue}>
                                    {session.proctoring_score || 90}%
                                  </span>
                                  <div className={styles.miniBar}>
                                    <div
                                      style={{
                                        width: `${session.proctoring_score || 90}%`,
                                        backgroundColor: "#f59e0b",
                                      }}
                                    ></div>
                                  </div>
                                </div>
                              </div>
                              <div className={styles.actionButtons}>
                                <button
                                  className={styles.cvButton}
                                  onClick={() => handleViewPracticeCV(session)}
                                  title="View CV used for this practice"
                                >
                                  <i className="fa fa-file-text"></i> View CV
                                </button>
                                <button
                                  className={styles.detailsButton}
                                  onClick={() => handleViewPracticeJD(session)}
                                  title="View job description"
                                >
                                  <i className="fa fa-file-text-o"></i> View JD
                                </button>
                                <button
                                  className={styles.reportButton}
                                  onClick={() =>
                                    viewPracticeReport(session.session_id)
                                  }
                                >
                                  <i className="fa fa-file-text-o"></i> Report
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}

                        {/* Pagination for Practice History */}
                        {totalPages > 1 && (
                          <Pagination
                            currentPage={currentPage}
                            totalPages={totalPages}
                            onPageChange={setCurrentPage}
                            totalItems={completedSessions.length}
                            itemsPerPage={itemsPerPage}
                          />
                        )}
                      </>
                    );
                  })()}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Interview Report Modal */}
      {showReportModal && selectedReport && (
        <InterviewReportModal
          isOpen={showReportModal}
          onClose={() => {
            setShowReportModal(false);
            setSelectedReport(null);
          }}
          report={selectedReport}
          cvScore={selectedReport.cv_score || 0}
          interviewScore={selectedReport.interview_score || 0}
        />
      )}

      {/* CV Selection Modal */}
      <CVSelectionModal
        isOpen={showCVModal}
        onClose={() => setShowCVModal(false)}
        onSubmit={handleCVSelectionSubmit}
        jobTitle={`Practice Interview - ${getRoleName(selectedRole)}`}
        mode="practice"
      />

      {/* CV Details Modal */}
      <CVDetailsModal
        isOpen={showCvDetailsModal}
        onClose={() => setShowCvDetailsModal(false)}
        cvDetails={selectedCvDetails}
      />

      {/* Practice Details Modal */}
      <PracticeDetailsModal
        isOpen={showPracticeDetailsModal}
        onClose={() => setShowPracticeDetailsModal(false)}
        session={selectedPracticeSession}
        getRoleName={getRoleName}
        getRoleIcon={getRoleIcon}
      />

      {/* JD Details Modal */}
      <JDDetailsModal
        isOpen={showJdDetailsModal}
        onClose={() => setShowJdDetailsModal(false)}
        session={selectedJdSession}
        getRoleName={getRoleName}
        getRoleIcon={getRoleIcon}
      />

      {/* GenHire not installed — download modal */}
      {showDownloadModal && (
        <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.7)',zIndex:9999,display:'flex',alignItems:'center',justifyContent:'center'}}>
          <div style={{background:'#1e293b',border:'1px solid #334155',borderRadius:'16px',padding:'36px 40px',maxWidth:'480px',width:'90%',color:'#f1f5f9',fontFamily:'inherit'}}>
            <div style={{fontSize:'2.5rem',marginBottom:'12px'}}>📥</div>
            <h2 style={{margin:'0 0 8px',fontSize:'1.4rem',color:'#f1f5f9'}}>Install GenHire Secure Browser</h2>
            <p style={{margin:'0 0 20px',color:'#94a3b8',fontSize:'0.95rem'}}>
              GenHire was not detected on this device. Your installer download has started automatically.
            </p>
            <div style={{background:'#0f172a',borderRadius:'10px',padding:'16px 20px',marginBottom:'24px'}}>
              <p style={{margin:'0 0 10px',color:'#7dd3fc',fontWeight:600,fontSize:'0.9rem'}}>Follow these steps:</p>
              <ol style={{margin:0,paddingLeft:'20px',color:'#cbd5e1',fontSize:'0.9rem',lineHeight:'1.9'}}>
                <li>Open <strong>Genhire.exe</strong> from your Downloads folder</li>
                <li>Click <strong>Install</strong> — the app will launch automatically</li>
                <li>Return here and click <strong>Retry</strong> below</li>
              </ol>
            </div>
            <div style={{display:'flex',gap:'12px',flexWrap:'wrap'}}>
              <button onClick={() => {
                const link = document.createElement('a');
                link.href = 'https://storage.googleapis.com/genhire-downloads/Genhire.exe';
                link.download = 'Genhire.exe';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
              }} style={{flex:1,padding:'10px 16px',background:'transparent',border:'1px solid #475569',borderRadius:'8px',color:'#94a3b8',cursor:'pointer',fontSize:'0.9rem'}}>
                Download Again
              </button>
              <button onClick={() => {
                if (!pendingDeepLink) return;
                setShowDownloadModal(false);
                const iframe = document.createElement("iframe");
                iframe.style.display = "none";
                iframe.src = pendingDeepLink;
                document.body.appendChild(iframe);
                setTimeout(() => { if (document.body.contains(iframe)) document.body.removeChild(iframe); }, 5000);
              }} style={{flex:2,padding:'10px 16px',background:'#3b82f6',border:'none',borderRadius:'8px',color:'#fff',cursor:'pointer',fontWeight:600,fontSize:'0.95rem'}}>
                Retry — Launch Interview
              </button>
            </div>
            <button onClick={() => setShowDownloadModal(false)} style={{marginTop:'16px',width:'100%',padding:'8px',background:'transparent',border:'none',color:'#64748b',cursor:'pointer',fontSize:'0.85rem'}}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Practice;

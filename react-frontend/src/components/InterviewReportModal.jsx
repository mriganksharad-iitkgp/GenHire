import React, { useEffect, useMemo, useState } from "react";
import styles from "./JobDetailsModal.module.css";
import GazeHeatmapPanel from "./GazeHeatmapPanel";
import { getToken } from "../utils/sessionManager";

// Human-readable rendering of the identity_verification verdict set by
// /register-face (see face_verification_service.py on the backend).
const IDENTITY_DISPLAY = {
  verified: {
    label: "Identity Verified",
    color: "#166534",
    background: "#f0fdf4",
    border: "#bbf7d0",
    note: "The captured face matched this account's registered identity.",
  },
  registered_new: {
    label: "Identity Registered (First Interview)",
    color: "#1e40af",
    background: "#eff6ff",
    border: "#bfdbfe",
    note: "This was the candidate's first interview on this account — the photo below was enrolled as their identity baseline for all future interviews.",
  },
  mismatch_blocked: {
    label: "Identity Mismatch — Blocked",
    color: "#991b1b",
    background: "#fef2f2",
    border: "#fecdd3",
    note: "The captured face repeatedly failed to match the account's registered identity; the attempt was locked.",
  },
  unverified_monitor: {
    label: "Identity Mismatch (Not Enforced)",
    color: "#9a3412",
    background: "#fff7ed",
    border: "#fed7aa",
    note: "The face did not match the registered identity, but verification was running in monitor mode so the interview was allowed.",
  },
  unverified_system_unavailable: {
    label: "Identity Not Verified",
    color: "#9a3412",
    background: "#fff7ed",
    border: "#fed7aa",
    note: "The identity check could not run for this session (face verification was unavailable). The captured photo is shown for manual review.",
  },
  practice_captured: {
    label: "Practice Capture",
    color: "#475569",
    background: "#f8fafc",
    border: "#e2e8f0",
    note: "Face captured for practice proctoring — identity is not enforced in practice mode.",
  },
  skipped: {
    label: "Identity Check Disabled",
    color: "#475569",
    background: "#f8fafc",
    border: "#e2e8f0",
    note: "Face verification was disabled at the time of this interview.",
  },
};

export default function InterviewReportModal({
  isOpen,
  onClose,
  report,
  cvScore,
  interviewScore,
}) {
  const [tab, setTab] = useState("summary"); // summary | transcript | gaze | raw
  const [capturedFaceUrl, setCapturedFaceUrl] = useState(null);
  const [referenceFaceUrl, setReferenceFaceUrl] = useState(null);

  const identity = report?.identity_verification || null;

  // Fetch identity photos with the auth token and expose them as blob URLs —
  // a plain <img src> can't send the Authorization header the endpoint needs.
  useEffect(() => {
    if (!isOpen || !report?.session_id || !identity) return undefined;

    let cancelled = false;
    const objectUrls = [];

    const fetchImage = async (kind, setter) => {
      try {
        const res = await fetch(
          `${process.env.REACT_APP_API_URL}/api/interviews/${report.session_id}/face-image/${kind}`,
          { headers: { Authorization: `Bearer ${getToken()}` } },
        );
        if (!res.ok || cancelled) return;
        const blob = await res.blob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        objectUrls.push(url);
        setter(url);
      } catch {
        /* photo unavailable — section still shows the verdict */
      }
    };

    if (identity.has_captured_image) fetchImage("captured", setCapturedFaceUrl);
    // The reference photo is only informative when it differs from the capture
    // (i.e. not a first-interview enrollment).
    if (identity.has_reference_image && identity.status !== "registered_new") {
      fetchImage("reference", setReferenceFaceUrl);
    }

    return () => {
      cancelled = true;
      objectUrls.forEach((u) => URL.revokeObjectURL(u));
      setCapturedFaceUrl(null);
      setReferenceFaceUrl(null);
    };
  }, [isOpen, report?.session_id, identity]);

  const finalScore = useMemo(() => {
    if (typeof interviewScore === "number") return Math.round(interviewScore);
    if (typeof report?.final_score === "number")
      return Math.round(report.final_score);
    return null;
  }, [interviewScore, report]);

  const cvScorePct = useMemo(() => {
    if (typeof cvScore === "number") return Math.round(cvScore);
    if (typeof report?.cv_score === "number")
      return Math.round(report.cv_score);
    return null;
  }, [cvScore, report]);

  const proctoringPct = useMemo(() => {
    return typeof report?.proctoring_score === "number"
      ? Math.round(report.proctoring_score)
      : null;
  }, [report]);

  // Try to coerce evaluation to structured object when possible
  const evaluationObj = useMemo(() => {
    const ev = report?.evaluation;
    if (!ev) return null;
    if (typeof ev === "object") return ev;
    if (typeof ev === "string") {
      try {
        return JSON.parse(ev);
      } catch {
        return { summary: ev };
      }
    }
    return null;
  }, [report]);

  // Extract qualitative assessment for display (matches Chat.jsx format)
  const qualitativeAssessment = useMemo(() => {
    const ev = report?.evaluation;
    if (!ev) return null;

    // If it's an object, look for qualitative_assessment field
    if (typeof ev === "object") {
      return ev.qualitative_assessment || ev.summary || null;
    }

    // If it's a string, try to parse it
    if (typeof ev === "string") {
      try {
        const parsed = JSON.parse(ev);
        return parsed.qualitative_assessment || parsed.summary || ev;
      } catch {
        return ev;
      }
    }

    return null;
  }, [report]);

  const prettyJSON = useMemo(
    () => JSON.stringify(report || {}, null, 2),
    [report],
  );

  const scoreChip = (label, val, color) => (
    <div
      style={{
        background: "#f7faff",
        border: `1px solid ${color}`,
        color: "#1f2d3d",
        borderRadius: 12,
        padding: "10px 14px",
        minWidth: 140,
      }}
    >
      <div style={{ fontSize: 12, color: "#5f6b7a", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div
          style={{
            position: "relative",
            width: 56,
            height: 8,
            background: "#e9eef5",
            borderRadius: 6,
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              bottom: 0,
              width: `${Math.max(0, Math.min(100, val || 0))}%`,
              background: color,
              borderRadius: 6,
            }}
          />
        </div>
        <div style={{ fontWeight: 700 }}>{val != null ? `${val}%` : "—"}</div>
      </div>
    </div>
  );

  const SectionTitle = ({ children }) => (
    <h3 style={{ margin: "12px 0 10px", fontSize: 16, color: "#2b3543" }}>
      {children}
    </h3>
  );

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* ignore */
    }
  };

  const downloadJSON = () => {
    try {
      const blob = new Blob([prettyJSON], {
        type: "application/json;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `interview-report-${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      /* ignore */
    }
  };

  const TabButton = ({ id, children }) => (
    <button
      onClick={() => setTab(id)}
      style={{
        padding: "10px 14px",
        border: "1px solid #e1e7ef",
        borderBottom: tab === id ? "2px solid #4a90e2" : "1px solid #e1e7ef",
        background: tab === id ? "#f8fbff" : "white",
        color: tab === id ? "#1f2d3d" : "#5f6b7a",
        borderTopLeftRadius: 8,
        borderTopRightRadius: 8,
        fontSize: 13,
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );

  // Only decide rendering after hooks are called to satisfy rules-of-hooks
  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent} style={{ maxWidth: 920 }}>
        <div className={styles.modalHeader}>
          <div className={styles.headerContent}>
            <div className={styles.titleSection}>
              <h2
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  margin: 0,
                }}
              >
                <span
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    background: "linear-gradient(135deg,#4a90e2,#357abd)",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "white",
                    fontSize: 18,
                  }}
                >
                  📝
                </span>
                Interview Report
              </h2>
              <span className={styles.subtitle}>
                Detailed interview analysis and evaluation
              </span>
            </div>
            <div className={styles.headerActions}>
              <button className={styles.closeButton} onClick={onClose}>
                <i className="fa fa-times"></i>
              </button>
            </div>
          </div>
        </div>
        <div className={styles.modalBody}>
          {/* Score overview */}
          <div
            style={{
              display: "flex",
              gap: 16,
              flexWrap: "wrap",
              marginBottom: 10,
            }}
          >
            {cvScorePct != null && scoreChip("CV Score", cvScorePct, "#4a90e2")}
            {finalScore != null &&
              scoreChip("Interview Score", finalScore, "#27ae60")}
            {proctoringPct != null &&
              scoreChip("Proctoring Score", proctoringPct, "#8e44ad")}
          </div>

          {evaluationObj?.interview_metadata?.ended_early_reason === "technical_difficulty" && (
            <div
              style={{
                background: "#fff3cd",
                color: "#856404",
                border: "1px solid #ffe69c",
                borderRadius: 6,
                padding: "8px 12px",
                marginBottom: 10,
                fontSize: 14,
              }}
            >
              ⚠️ This interview ended early due to a technical difficulty on our
              end (not the candidate's performance) after question{" "}
              {evaluationObj.interview_metadata.questions_asked ?? "?"}. Consider
              this when reviewing the score below.
            </div>
          )}

          {report?.proctoring_status === "incomplete" && (
            <div
              style={{
                background: "#fff3cd",
                color: "#856404",
                border: "1px solid #ffe69c",
                borderRadius: 6,
                padding: "8px 12px",
                marginBottom: 10,
                fontSize: 14,
              }}
            >
              ⚠️ Proctoring data could not be collected for this interview (camera
              access denied, or the eye-tracking script failed to load) — there is
              no proctoring score to show. This is not evidence of cheating; it
              means the check couldn't run at all.
            </div>
          )}

          {/* Tabs */}
          <div
            style={{
              display: "flex",
              gap: 6,
              borderBottom: "1px solid #e1e7ef",
              marginTop: 14,
            }}
          >
            <TabButton id="summary">Summary</TabButton>
            <TabButton id="transcript">Transcript</TabButton>
            <TabButton id="gaze">Gaze Analysis</TabButton>
            <TabButton id="raw">Raw</TabButton>
          </div>

          {/* Tab content */}
          <div style={{ paddingTop: 14 }}>
            {tab === "summary" && (
              <div>
                {/* Candidate identity verification — who actually sat this interview */}
                {identity && (
                  <div style={{ marginBottom: 18 }}>
                    <SectionTitle>🪪 Candidate Identity</SectionTitle>
                    {(() => {
                      const display =
                        IDENTITY_DISPLAY[identity.status] || {
                          label: "Identity Status Unknown",
                          color: "#475569",
                          background: "#f8fafc",
                          border: "#e2e8f0",
                          note: "No identity verdict was recorded for this session.",
                        };
                      return (
                        <div
                          style={{
                            background: display.background,
                            border: `1px solid ${display.border}`,
                            borderRadius: 10,
                            padding: "12px 14px",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 10,
                              flexWrap: "wrap",
                            }}
                          >
                            <span
                              style={{
                                color: display.color,
                                fontWeight: 700,
                                fontSize: 14,
                              }}
                            >
                              {display.label}
                            </span>
                            {typeof identity.distance === "number" &&
                              typeof identity.threshold === "number" && (
                                <span style={{ color: "#5f6b7a", fontSize: 12 }}>
                                  match distance {identity.distance.toFixed(3)} (threshold{" "}
                                  {identity.threshold.toFixed(3)})
                                </span>
                              )}
                          </div>
                          <div
                            style={{
                              color: "#5f6b7a",
                              fontSize: 13,
                              marginTop: 6,
                              lineHeight: 1.5,
                            }}
                          >
                            {display.note}
                          </div>
                          {(capturedFaceUrl || referenceFaceUrl) && (
                            <div
                              style={{
                                display: "flex",
                                gap: 16,
                                marginTop: 12,
                                flexWrap: "wrap",
                              }}
                            >
                              {capturedFaceUrl && (
                                <div style={{ textAlign: "center" }}>
                                  <img
                                    src={capturedFaceUrl}
                                    alt="Face captured at interview"
                                    style={{
                                      maxHeight: 160,
                                      maxWidth: 220,
                                      borderRadius: 8,
                                      border: "1px solid #e1e7ef",
                                      display: "block",
                                    }}
                                  />
                                  <div
                                    style={{
                                      fontSize: 12,
                                      color: "#5f6b7a",
                                      marginTop: 6,
                                    }}
                                  >
                                    {identity.status === "registered_new"
                                      ? "Enrolled identity photo"
                                      : "Captured at this interview"}
                                  </div>
                                </div>
                              )}
                              {referenceFaceUrl && (
                                <div style={{ textAlign: "center" }}>
                                  <img
                                    src={referenceFaceUrl}
                                    alt="Registered account identity"
                                    style={{
                                      maxHeight: 160,
                                      maxWidth: 220,
                                      borderRadius: 8,
                                      border: "1px solid #e1e7ef",
                                      display: "block",
                                    }}
                                  />
                                  <div
                                    style={{
                                      fontSize: 12,
                                      color: "#5f6b7a",
                                      marginTop: 6,
                                    }}
                                  >
                                    Registered account identity
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* Display quantitative metrics if available - matches Chat.jsx format */}
                {evaluationObj?.quantitative && (
                  <div>
                    <SectionTitle>Performance Metrics</SectionTitle>
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fit, minmax(200px, 1fr))",
                        gap: "20px",
                        marginBottom: "25px",
                      }}
                    >
                      {evaluationObj.quantitative.number_of_questions && (
                        <div
                          style={{
                            background:
                              "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
                            padding: "20px",
                            borderRadius: "12px",
                            color: "white",
                            textAlign: "center",
                            boxShadow: "0 4px 15px rgba(79, 172, 254, 0.4)",
                          }}
                        >
                          <div
                            style={{
                              fontSize: "14px",
                              opacity: 0.9,
                              marginBottom: "8px",
                            }}
                          >
                            Questions Answered
                          </div>
                          <div style={{ fontSize: "32px", fontWeight: "bold" }}>
                            {evaluationObj.quantitative.number_of_questions}
                          </div>
                        </div>
                      )}
                      {evaluationObj.quantitative.average_relevance_score && (
                        <div
                          style={{
                            background:
                              "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                            padding: "20px",
                            borderRadius: "12px",
                            color: "white",
                            textAlign: "center",
                            boxShadow: "0 4px 15px rgba(102, 126, 234, 0.4)",
                          }}
                        >
                          <div
                            style={{
                              fontSize: "14px",
                              opacity: 0.9,
                              marginBottom: "8px",
                            }}
                          >
                            Relevance Score
                          </div>
                          <div style={{ fontSize: "32px", fontWeight: "bold" }}>
                            {Math.round(
                              evaluationObj.quantitative
                                .average_relevance_score,
                            )}
                            %
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                <SectionTitle>📋 Evaluation Summary</SectionTitle>
                {qualitativeAssessment ? (
                  <div
                    style={{
                      background: "#f8f9fa",
                      padding: "20px",
                      borderRadius: "12px",
                      marginBottom: "20px",
                      border: "1px solid #e9ecef",
                    }}
                  >
                    <div
                      style={{
                        color: "#495057",
                        lineHeight: "1.6",
                      }}
                    >
                      {qualitativeAssessment.split("\n").map((line, index) => (
                        <p key={index} style={{ marginBottom: "8px" }}>
                          {line}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : evaluationObj ? (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr",
                      gap: 10,
                    }}
                  >
                    {evaluationObj.summary && (
                      <div
                        style={{
                          background: "#f8f9fb",
                          padding: 12,
                          borderRadius: 8,
                        }}
                      >
                        {evaluationObj.summary}
                      </div>
                    )}
                    {Array.isArray(evaluationObj.strengths) &&
                      evaluationObj.strengths.length > 0 && (
                        <div>
                          <div
                            style={{
                              fontSize: 13,
                              color: "#5f6b7a",
                              marginBottom: 6,
                            }}
                          >
                            Strengths
                          </div>
                          <ul style={{ margin: 0, paddingLeft: 18 }}>
                            {evaluationObj.strengths.map((s, i) => (
                              <li key={i}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    {Array.isArray(evaluationObj.areas_of_improvement) &&
                      evaluationObj.areas_of_improvement.length > 0 && (
                        <div>
                          <div
                            style={{
                              fontSize: 13,
                              color: "#5f6b7a",
                              marginBottom: 6,
                            }}
                          >
                            Areas of Improvement
                          </div>
                          <ul style={{ margin: 0, paddingLeft: 18 }}>
                            {evaluationObj.areas_of_improvement.map((w, i) => (
                              <li key={i}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    {!evaluationObj.summary &&
                      !evaluationObj.strengths &&
                      !evaluationObj.areas_of_improvement && (
                        <div
                          style={{
                            background: "#f8f9fb",
                            padding: 12,
                            borderRadius: 8,
                          }}
                        >
                          No structured evaluation provided.
                        </div>
                      )}
                  </div>
                ) : (
                  <div
                    style={{
                      background: "#f8f9fb",
                      padding: 12,
                      borderRadius: 8,
                    }}
                  >
                    No evaluation details available.
                  </div>
                )}
              </div>
            )}

            {tab === "transcript" && (
              <div>
                <SectionTitle>Conversation Transcript</SectionTitle>
                <div
                  style={{
                    background: "#f8f9fa",
                    padding: 12,
                    borderRadius: 8,
                    maxHeight: 360,
                    overflow: "auto",
                  }}
                >
                  {Array.isArray(report?.transcript) &&
                  report.transcript.length > 0 ? (
                    report.transcript.map((turn, i) => {
                      const isAI =
                        turn.role === "assistant" || turn.role === "ai";
                      return (
                        <div
                          key={i}
                          style={{
                            display: "flex",
                            gap: 10,
                            marginBottom: 10,
                            alignItems: "flex-start",
                          }}
                        >
                          <div
                            style={{
                              width: 28,
                              height: 28,
                              borderRadius: "50%",
                              background: isAI ? "#4a90e2" : "#27ae60",
                              color: "white",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 13,
                              flexShrink: 0,
                            }}
                          >
                            {isAI ? "AI" : "C"}
                          </div>
                          <div
                            style={{
                              background: isAI ? "#eaf2ff" : "#eafaf1",
                              border: `1px solid ${isAI ? "#cfe0ff" : "#bfe8d1"}`,
                              padding: "10px 12px",
                              borderRadius: 10,
                              maxWidth: "100%",
                              whiteSpace: "pre-wrap",
                            }}
                          >
                            <div>{turn.text}</div>
                            {turn.ai_probability !== undefined && turn.ai_probability !== null && (
                              <div style={{
                                marginTop: 8,
                                paddingTop: 8,
                                borderTop: `1px solid ${isAI ? "#cfe0ff" : "#bfe8d1"}`,
                                fontSize: 12,
                                display: "flex",
                                alignItems: "center",
                                gap: 6,
                                color: turn.ai_probability >= 0.8 ? "#d32f2f" : turn.ai_probability >= 0.4 ? "#f57c00" : "#388e3c"
                              }}>
                                <span>🤖</span>
                                <strong>AI Probability:</strong> {Math.round(turn.ai_probability * 100)}%
                                {turn.ai_probability >= 0.8 && " (High likelihood of AI generation)"}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div
                      style={{
                        background: "#fff",
                        border: "1px dashed #dfe6ee",
                        padding: 12,
                        borderRadius: 8,
                      }}
                    >
                      Transcript not available in this build. See Raw for more
                      details.
                    </div>
                  )}
                </div>
              </div>
            )}

            {tab === "gaze" && (
              <div>
                <SectionTitle>Gaze Analysis</SectionTitle>
                {report?.gaze_recorder_analysis || report?.gaze_recorder_points_path ? (
                  <div
                    style={{
                      background: "#0b1020",
                      borderRadius: 12,
                      padding: "20px 18px",
                    }}
                  >
                    <GazeHeatmapPanel
                      analysis={report?.gaze_recorder_analysis}
                      pointsPath={report?.gaze_recorder_points_path}
                      apiUrl={process.env.REACT_APP_API_URL}
                    />
                  </div>
                ) : (
                  <div
                    style={{
                      background: "#f8f9fb",
                      border: "1px dashed #dfe6ee",
                      padding: 18,
                      borderRadius: 8,
                      color: "#5f6b7a",
                      fontSize: 13,
                    }}
                  >
                    No gaze tracking data was recorded for this interview session.
                    Eye-tracking may have been skipped or the calibration did not
                    complete successfully.
                  </div>
                )}
              </div>
            )}

            {tab === "raw" && (
              <div>
                <SectionTitle>Raw Report JSON</SectionTitle>
                <div
                  style={{
                    background: "#0b1020",
                    color: "#d7e2ff",
                    borderRadius: 8,
                    overflow: "hidden",
                  }}
                >
                  <pre
                    style={{
                      margin: 0,
                      padding: 12,
                      maxHeight: 360,
                      overflow: "auto",
                    }}
                  >
                    {prettyJSON}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>
        <div className={styles.modalFooter}>
          <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
            <button
              className={styles.secondaryButton}
              onClick={() => copyToClipboard(prettyJSON)}
            >
              Copy JSON
            </button>
            <button className={styles.secondaryButton} onClick={downloadJSON}>
              Download JSON
            </button>
            <button className={styles.secondaryButton} onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

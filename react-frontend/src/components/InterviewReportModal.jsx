import React, { useMemo, useState } from "react";
import styles from "./JobDetailsModal.module.css";

export default function InterviewReportModal({
  isOpen,
  onClose,
  report,
  cvScore,
  interviewScore,
}) {
  const [tab, setTab] = useState("summary"); // summary | transcript | raw

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
            <TabButton id="raw">Raw</TabButton>
          </div>

          {/* Tab content */}
          <div style={{ paddingTop: 14 }}>
            {tab === "summary" && (
              <div>
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
                            {turn.text}
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

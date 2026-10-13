import React, { useEffect, useMemo, useRef, useState } from "react";
import { Check, Download, ShieldCheck, X } from "lucide-react";
import { API_BASE } from "shared/api/client";
import { getToken } from "shared/utils/session";
import GazeHeatmapPanel from "./GazeHeatmapPanel";
import { interviewScore as resultScore, scorePercent, parseEvaluation } from "../utils/session";
import styles from "../pages/InterviewExperience.module.css";

const identityLabels = {
  score_pending: "Face comparison processing", scored: "Face comparison complete",
  score_unavailable: "Face comparison unavailable", verified: "Identity verified",
  registered_new: "Identity registered", mismatch_blocked: "Identity mismatch recorded",
  unverified_monitor: "Identity comparison requires review", unverified_system_unavailable: "Identity check unavailable",
  practice_captured: "Practice face captured", skipped: "Identity check disabled",
};
const readable = (value) => String(value || "").replaceAll("_", " ");
const scoreText = (score) => score == null ? "Unavailable" : `${score}%`;
const reportText = (value, fallback = "") => value == null || value === "" ? fallback : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);

export default function InterviewReportModal({ isOpen, onClose, report, cvScore, interviewScore, apiBase = API_BASE }) {
  const [tab, setTab] = useState("summary"); const [photos, setPhotos] = useState({}); const [copied, setCopied] = useState(false);
  const dialogRef = useRef(null); const closeRef = useRef(onClose); closeRef.current = onClose; const identity = report?.identity_verification;
  const evaluation = useMemo(() => parseEvaluation(report?.evaluation), [report?.evaluation]);
  const prettyJSON = useMemo(() => JSON.stringify(report || {}, null, 2), [report]);
  const monitoring = report?.proctoring_report || {}; const coverage = monitoring.coverage || {};
  const finalScore = resultScore(report) ?? (report?.interview_score == null && Object.hasOwn(report || {}, "interview_score") ? null : scorePercent(interviewScore));
  const cv = Object.hasOwn(report || {}, "cv_score") ? scorePercent(report.cv_score) : scorePercent(cvScore);
  const proctor = ["incomplete", "disabled"].includes(report?.proctoring_status || monitoring.status) ? null : scorePercent(report?.proctoring_score ?? monitoring.final_score);
  const pending = evaluation.pending_answers > 0 || report?.cv_score_status === "pending";
  const questions = Array.isArray(evaluation.per_question_evaluations) ? evaluation.per_question_evaluations : [];
  const pairs = Array.isArray(report?.qa_pairs) ? report.qa_pairs : questions;
  const transcript = Array.isArray(report?.transcript) && report.transcript.length ? report.transcript.filter(turn => turn && typeof turn === "object") : pairs.filter(item => item && typeof item === "object").flatMap(item => [{ role:"assistant", text:item.question }, { role:"candidate", text:item.answer }]);
  const feedback = evaluation.qualitative_assessment || evaluation.summary;
  const feedbackText = reportText(feedback?.summary ?? feedback, "Evaluation details are unavailable. Review the transcript and scoring coverage.");
  const events = Array.isArray(monitoring.events) ? monitoring.events.filter(event => event && typeof event === "object") : [];
  const missingChecks = Array.isArray(monitoring.missing_checks) ? monitoring.missing_checks : [];
  const interruptionCounts = monitoring.interruption_counts || report?.integrity?.counts_by_type || {};
  const interruptionEvents = monitoring.interruption_policy?.events || report?.integrity?.events || [];
  const capabilities = monitoring.capabilities && typeof monitoring.capabilities === "object" && !Array.isArray(monitoring.capabilities) ? monitoring.capabilities : {};

  useEffect(() => {
    if (!isOpen) return;
    setTab("summary"); setCopied(false); const previous = document.activeElement; dialogRef.current?.focus();
    const keyboard = (event) => {
      if (event.key === "Escape") { closeRef.current(); return; }
      if (event.key !== "Tab") return;
      const items = [...(dialogRef.current?.querySelectorAll('button:not(:disabled),a[href],textarea,input,[tabindex="0"]') || [])];
      const first = items[0]; const last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", keyboard);
    return () => { document.removeEventListener("keydown", keyboard); previous?.focus?.(); };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !report?.session_id || !identity) return;
    let cancelled = false; const urls = []; setPhotos({});
    ["captured", "reference"].forEach((kind) => {
      if (!identity[`has_${kind}_image`]) return;
      fetch(`${apiBase}/interviews/${report.session_id}/face-image/${kind}`, { headers: { Authorization: `Bearer ${getToken()}` } })
        .then(async (response) => { if (!response.ok) return; const blob = await response.blob(); if (cancelled) return;
          const url = URL.createObjectURL(blob); urls.push(url); setPhotos((previous) => ({ ...previous, [kind]: url }));
        }).catch(() => {});
    });
    return () => { cancelled = true; urls.forEach((url) => URL.revokeObjectURL(url)); };
  }, [isOpen, report?.session_id, identity, apiBase]);

  const download = () => {
    const url = URL.createObjectURL(new Blob([prettyJSON], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `genhire-interview-${report?.session_id || "report"}.json`;
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  if (!isOpen) return null;
  const tabs = [["summary", "Evaluation"], ["transcript", "Transcript"], ["monitoring", "Proctoring"], ...(report?.gaze_recorder_analysis || report?.gaze_recorder_points_path ? [["gaze", "Gaze analysis"]] : []), ["raw", "Report data"]];
  return <div className={styles.reportOverlay} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={dialogRef} tabIndex={-1} className={styles.reportDialog} role="dialog" aria-modal="true" aria-labelledby="interview-report-title">
      <header className={styles.reportHeader}><div><span className={styles.eyebrow}>GenHire assessment</span><h2 id="interview-report-title">Your interview report</h2></div><button className={styles.textButton} onClick={onClose} aria-label="Close interview report"><X size={22} /></button></header>
      <div className={styles.reportBody}>
        {report?.status === "terminated" && <div className={styles.error}>This attempt ended under the monitoring policy: {report?.integrity?.count ?? 0} interruptions. Coverage gaps require human review and do not by themselves establish cheating.</div>}
        <div className={styles.scoreGrid}>{[["Interview", finalScore], ["CV match", cv], ["Proctoring", proctor]].map(([label, score]) => <div key={label} className={styles.scoreCard}><span>{label}</span><strong>{scoreText(score)}</strong></div>)}</div>
        {pending && <p className={styles.note} role="status">Scoring is still processing. Available scores reflect the answers evaluated so far.</p>}
        {evaluation.score_status && evaluation.score_status !== "complete" && <p className={styles.note}>Rubric evaluation: {readable(evaluation.score_status)}. {evaluation.scored_answers ?? 0} of {evaluation.total_answers ?? transcript.length / 2} answers evaluated.</p>}
        {evaluation.interview_metadata?.ended_early_reason === "technical_difficulty" && <div className={styles.error}>A technical difficulty ended this interview early. Review the available answers when interpreting the scores.</div>}
        <div className={styles.reportTabs} role="tablist" aria-label="Report sections">{tabs.map(([id, label]) => <button key={id} role="tab" id={`report-tab-${id}`} aria-selected={tab === id} aria-controls={`report-panel-${id}`} className={tab === id ? styles.activeTab : ""} onClick={() => setTab(id)}>{label}</button>)}</div>
        <div role="tabpanel" id={`report-panel-${tab}`} aria-labelledby={`report-tab-${tab}`} className={styles.reportSection}>
          {tab === "summary" && <>
            <h3>Evaluation and feedback</h3><div className={styles.reportCopy}>{feedbackText}</div>
            {["strengths", "areas_of_improvement"].map((key) => Array.isArray(evaluation[key]) && evaluation[key].length > 0 && <section key={key}><h3>{key === "strengths" ? "Strengths" : "Areas to improve"}</h3><ul>{evaluation[key].map((item, index) => <li key={index}>{String(item)}</li>)}</ul></section>)}
            {!!questions.length && <section><h3>Answer breakdown and preparation</h3>
              <p className={styles.note}>Suggested answers use your CV and the job requirements. Replace bracketed details with your real experience; these examples do not change your interview score.</p>
              {questions.filter(item => item && typeof item === "object").map((item, index) => <details className={styles.answerBreakdown} key={index}>
                <summary>Question {item.question_number || index + 1}: {reportText(item.question)}</summary>
                {item.question_metadata?.topic_area && <p className={styles.note}>{reportText(item.question_metadata.topic_area)}</p>}
                <h4>Your answer</h4><p>{reportText(item.answer, "No answer provided")}</p>
                <p className={styles.note}>{item.evaluation?.evaluation_status === "pending" ? "Evaluation processing" : `Answer quality: ${scoreText(scorePercent(item.evaluation?.answer_score == null ? null : item.evaluation.answer_score * 100))} | Communication: ${scoreText(scorePercent(item.evaluation?.language_score == null ? null : item.evaluation.language_score * 100))}`}</p>
                {item.evaluation?.feedback && <p>{reportText(item.evaluation.feedback)}</p>}
                <div className={styles.preparationAnswer}><h4>A stronger answer to practice</h4>
                  {item.suggested_answer ? <><p>{reportText(item.suggested_answer)}</p>{item.improvement_tip && <p><strong>Preparation tip: </strong>{reportText(item.improvement_tip)}</p>}</>
                    : <p className={styles.note}>{item.suggested_answer_status === "unavailable" ? "The preparation service could not produce a suggested answer. Your original answer and evaluation are retained." : "Suggested answers were not generated for this older report."}</p>}
                </div>
              </details>)}
            </section>}
            {identity && <section className={styles.identityReport}><h3><ShieldCheck size={18} /> {identityLabels[identity.status] || readable(identity.status)}</h3><p className={styles.note}>{identity.status === "practice_captured" ? "This capture was used for practice monitoring." : identity.status === "score_pending" ? "Face comparison is processing in the background." : "Face comparison supports manual identity review. Compare the captured image and reference alongside the session evidence."}{identity.score != null && ` Similarity: ${scorePercent(identity.score)}%.`}</p><div className={styles.identityPhotos}>{Object.entries(photos).map(([kind, url]) => <figure key={kind}><img src={url} alt={kind === "captured" ? "Face captured for this interview" : "Candidate identity reference"} /><figcaption>{kind === "captured" ? "Interview capture" : "Identity reference"}</figcaption></figure>)}</div></section>}
          </>}
          {tab === "transcript" && <><h3>Conversation transcript</h3>{transcript.length ? transcript.map((turn, index) => <article className={styles.transcriptTurn} key={index}><strong>{["assistant", "ai"].includes(turn.role) ? "Interviewer" : "Candidate"}</strong><p>{reportText(turn.text || turn.content, "No answer provided")}</p></article>) : <p className={styles.note}>No transcript was recorded for this session.</p>}</>}
          {tab === "monitoring" && <><h3>Monitoring coverage</h3><p>{reportText(monitoring.summary, "Monitoring evidence is unavailable for this session.")}</p><p className={styles.note}>Camera warnings require human review. A detection is not a decision about cheating or interview performance.</p><div className={styles.coverageGrid}>{[["Coverage", readable(monitoring.status || report?.proctoring_status || "unavailable")], ["Laptop frames analyzed", coverage.desktop_analyzed_frames ?? "Unavailable"], ["Phone frames analyzed", coverage.mobile_analyzed_frames ?? "Unavailable"], ["Phone required", coverage.dual_camera_required ? "Yes" : "No"], ["Phone connection gaps", coverage.mobile_coverage_gaps ?? 0]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{reportText(value)}</strong></div>)}</div>
            {!!missingChecks.length && <p className={styles.note}>Checks unavailable: {missingChecks.map(readable).join(", ")}. These gaps are recorded without adding violations.</p>}
            <h3>Available checks</h3><div className={styles.checksList}>{Object.entries(capabilities).filter(([, available]) => available).map(([key]) => <span key={key}><Check size={15} />{readable(key)}</span>)}</div>
            <h3>Monitoring interruptions</h3><p className={styles.note}>Interruptions contribute to the final monitoring score. Technical coverage gaps carry smaller deductions than leaving the interview window; warnings require human review.</p>
            <div className={styles.coverageGrid}>{Object.entries(interruptionCounts).map(([type,count]) => <div key={type}><span>{readable(type)}</span><strong>{count}</strong></div>)}</div>
            {!!interruptionEvents.length && <ol className={styles.monitoringEvents}>{interruptionEvents.map((event,index) => <li key={index}><strong>{event.message || readable(event.reason)}</strong><span>{readable(event.source)} · Interruption {event.count}</span></li>)}</ol>}<h3>Recorded warnings</h3>{events.length ? <ol className={styles.monitoringEvents}>{events.map((event, index) => <li key={index}><strong>{reportText(event.message) || readable(event.type)}</strong><span>{event.source === "desktop" ? "Laptop" : readable(event.source)}{event.timestamp && ` · ${new Date(event.timestamp).toLocaleTimeString()}`}</span></li>)}</ol> : <p className={styles.note}>{proctor == null ? "No analyzed warning evidence is available." : "No monitoring warnings were recorded."}</p>}
          </>}
          {tab === "gaze" && <GazeHeatmapPanel analysis={report?.gaze_recorder_analysis} pointsPath={report?.gaze_recorder_points_path} apiUrl={process.env.REACT_APP_API_URL} />}
          {tab === "raw" && <pre className={styles.rawReport}>{prettyJSON}</pre>}
        </div>
      </div>
      <footer className={styles.reportFooter}><button className={styles.secondary} onClick={async () => { try { await navigator.clipboard.writeText(prettyJSON); setCopied(true); } catch { setCopied(false); } }}>{copied ? "Copied" : "Copy report data"}</button><button className={styles.secondary} onClick={download}><Download size={16} /> Download report</button><button className={styles.primary} onClick={onClose}>Done</button></footer>
    </section>
  </div>;
}

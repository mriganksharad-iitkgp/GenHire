import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import io from "socket.io-client";
import QRCode from "react-qr-code";
import { Camera, Check, ChevronRight, CircleAlert, Headphones, Mic, ShieldCheck, Smartphone, Volume2 } from "lucide-react";
import { API_BASE } from "shared/api/client";
import { getToken } from "shared/utils/session";
import ConfirmDialog from "shared/components/ui/ConfirmDialog";
import Modal from "shared/components/ui/Modal";
import InterviewReportModal from "../components/InterviewReportModal";
import AnswerComposer from "../components/AnswerComposer";
import { interviewRequest, interviewScore, isPracticeSession, mediaMimeType, microphoneLevel, mobilePairingUrl, recordingPartId, reconcileAnswer, scorePercent, socketAcknowledgement, terminalPhase, transcriptionAudio } from "../utils/session";
import styles from "./InterviewExperience.module.css";

const THINK_SECONDS = 30;
const SILENCE_SECONDS = 8;
const CACHE_KEY = "genhire-interview-session";
const formatTime = (value) => `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;

function initialSession(interviewId, location) {
  const state = location.state || {};
  if (state.sessionId) return { session_id: state.sessionId, initial_questions: [state.initialQuestion], similarity_score: state.similarityScore,
    cv_score: state.cvScore, max_questions: state.maxQuestions, is_practice: state.isPractice, application_id: state.applicationId };
  try {
    const cached = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null");
    if (cached && (cached.session_id === interviewId || (interviewId === "start" && cached.application_id === state.applicationId))) return cached;
  } catch { /* no cached session */ }
  return null;
}

export default function Chat({ interviewId, apiBase = API_BASE, webOrigin = process.env.REACT_APP_FRONTEND_URL || window.location.origin, onReturn, launchState }) {
  const routerLocation = useLocation(); const routerNavigate = useNavigate();
  const location = useMemo(() => launchState ? { ...routerLocation, state: launchState } : routerLocation, [launchState, routerLocation]);
  const navigate = onReturn || routerNavigate;
  const socketUrl = apiBase.replace(/\/api\/?$/, "");
  const [session, setSession] = useState(() => initialSession(interviewId, location));
  const [phase, setPhase] = useState("loading"); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [deviceError, setDeviceError] = useState(""); const [cameraReady, setCameraReady] = useState(false);
  const [micReady, setMicReady] = useState(false); const [micLevel, setMicLevel] = useState(0); const [speakerTested, setSpeakerTested] = useState(false);
  const [rulesAccepted, setRulesAccepted] = useState(false); const [faceCaptured, setFaceCaptured] = useState(false);
  const [phone, setPhone] = useState({ ready: false, status: "disconnected" }); const [connected, setConnected] = useState(false);
  const [proctoring, setProctoring] = useState(null); const [warning, setWarning] = useState(null); const [warningCount, setWarningCount] = useState(0);
  const [question, setQuestion] = useState(""); const [questionCount, setQuestionCount] = useState(1); const [speechState, setSpeechState] = useState("idle");
  const [hasSpoken, setHasSpoken] = useState(false); const [answerCountdown, setAnswerCountdown] = useState(THINK_SECONDS);
  const [draft, setDraft] = useState(""); const [pendingAnswer, setPendingAnswer] = useState(null); const [elapsed, setElapsed] = useState(0);
  const [answerMode, setAnswerMode] = useState("voice"); const answerModeRef = useRef("voice");
  const [showModeConfirm, setShowModeConfirm] = useState(false);
  const [modeToConfirm, setModeToConfirm] = useState("text");
  const modeConfirmRef = useRef(false);
  const [questionDeadline, setQuestionDeadline] = useState(null); const [questionRemaining, setQuestionRemaining] = useState(null);
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
  const [audioRetryAvailable, setAudioRetryAvailable] = useState(false); const recordedAnswerRef = useRef(null);
  const [result, setResult] = useState(null); const [uploadStatus, setUploadStatus] = useState("idle"); const [showReport, setShowReport] = useState(false);
  const [showEndConfirm, setShowEndConfirm] = useState(false); const [pauseReason, setPauseReason] = useState("");
  const aliveRef = useRef(true); const initializationRef = useRef(false); const phaseRef = useRef(phase); const sessionRef = useRef(session);
  const questionRef = useRef(question); const videoRef = useRef(null); const streamRef = useRef(null); const contextRef = useRef(null); const analyserRef = useRef(null);
  const socketRef = useRef(null); const audioRef = useRef(null); const speechRequestRef = useRef(0); const audioCacheRef = useRef(new Map());
  const answerRecorderRef = useRef(null); const answerChunksRef = useRef([]); const archiveRecorderRef = useRef(null); const archiveChunksRef = useRef([]);
  const archivePartsRef = useRef([]); const archiveUploadRef = useRef(false); const submitRequestRef = useRef(false);
  const startedAtRef = useRef(null); const answerStartRef = useRef(0); const lastSpeechRef = useRef(0);
  const spokeRef = useRef(false); const processingRef = useRef(false); const pauseRef = useRef(""); const submitRecordingRef = useRef(null);
  const actionsRef = useRef({}); const lastWarningRef = useRef({}); const draftRef = useRef(draft); draftRef.current = draft;
  const request = useCallback((path, options = {}, timeout = 15000) => interviewRequest(apiBase, path, getToken(), options, timeout), [apiBase]);
  const isPractice = isPracticeSession(location, session || {}); const dualRequired = session?.dual_proctoring_required === true;
  const maxQuestions = session?.max_questions || 10; const phoneUrl = mobilePairingUrl(session, webOrigin);
  const deviceReady = cameraReady && micReady && speakerTested === true;
  phaseRef.current = phase; sessionRef.current = session; questionRef.current = question; pauseRef.current = pauseReason;

  const bindVideo = useCallback((element) => { videoRef.current = element; if (element && streamRef.current) element.srcObject = streamRef.current; }, []);
  const notify = useCallback((message, type = "notice", source = "laptop") => {
    const key = `${source}:${type}`; if (Date.now() - (lastWarningRef.current[key] || 0) < 8000) return;
    lastWarningRef.current[key] = Date.now(); setWarning({ message, type, source }); if (type !== "notice") setWarningCount((count) => count + 1);
  }, []);
  const stopPlayback = useCallback(() => {
    speechRequestRef.current += 1;
    if (audioRef.current) { audioRef.current.onended = null; audioRef.current.pause(); audioRef.current.src = ""; audioRef.current = null; }
  }, []);

  // Existing sessions are resumed from the server, never charged by another /start.
  useEffect(() => {
    if (initializationRef.current) return; initializationRef.current = true;
    async function initialize() {
      try {
        const existing = sessionRef.current; let data;
        if (existing?.session_id || (interviewId && interviewId !== "start")) data = await request(`/interviews/${existing?.session_id || interviewId}/session`);
        else {
          if (!location.state?.applicationId) throw new Error("Open this interview from your applications page so we can load the correct role.");
          try { data = await request("/interviews/start", { method: "POST", body: JSON.stringify({ application_id: location.state.applicationId }) }, 15000); }
          catch (failure) {
            if (failure.code !== "session_recovery_required" || !failure.details?.session_id) throw failure;
            data = await request(`/interviews/${failure.details.session_id}/session`);
          }
        }
        if (!aliveRef.current) return;
        const merged = { ...existing, ...data }; setSession(merged); sessionRef.current = merged;
        try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ ...merged, application_id: merged.application_id || location.state?.applicationId })); } catch { /* restricted storage must not prevent an interview */ }
        setQuestion(merged.current_question || merged.initial_questions?.[0] || existing?.initial_questions?.[0] || ""); setQuestionCount(merged.question_count || 1);
        setQuestionDeadline(merged.question_deadline ?? null);
        if (terminalPhase(merged)) { setResult(merged); setPhase(terminalPhase(merged)); }
        else if (merged.interview_complete) actionsRef.current.finish();
        else if (merged.engine_available === false) { setError("This session's live interviewer is unavailable. Finish with your saved answers, then return to your dashboard. Your submitted answers will be retained."); setPhase("recovery_failed"); }
        else { setFaceCaptured(!!merged.identity_captured); setPhase("devices"); }
      } catch (failure) { if (aliveRef.current) { setError(failure.message); setPhase("start_failed"); } }
    }
    initialize();
  }, [interviewId, location.state, request]);

  useEffect(() => {
    if (!session?.session_id || !question || !["devices", "face", "phone", "ready"].includes(phase) || audioCacheRef.current.has(question)) return;
    request("/speech/synthesize", { method: "POST", body: JSON.stringify({ text: question, session_id: session.session_id }) }, 5000)
      .then((data) => { if (data.audio_base64) audioCacheRef.current.set(question, `data:audio/mp3;base64,${data.audio_base64}`); }).catch(() => {});
  }, [session?.session_id, question, request, phase]);

  const enableDevices = async () => {
    if (busy) return; setBusy(true); setDeviceError(""); setMicReady(false); setCameraReady(false);
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("Use the GenHire kiosk browser or a current Chrome, Edge or Safari browser with HTTPS camera access.");
      streamRef.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15 } }, audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (!aliveRef.current) { stream.getTracks().forEach((track) => track.stop()); return; }
      streamRef.current = stream; if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
      setCameraReady(stream.getVideoTracks().some((track) => track.readyState === "live" && !track.muted) && !!videoRef.current?.videoWidth);
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) throw new Error("Your browser cannot test the microphone. Open the GenHire kiosk browser.");
      await contextRef.current?.close().catch(() => {}); const context = new AudioContextClass(); await context.resume();
      const analyser = context.createAnalyser(); analyser.fftSize = 1024; context.createMediaStreamSource(stream).connect(analyser);
      contextRef.current = context; analyserRef.current = analyser;
      stream.getTracks().forEach((track) => { track.onended = () => {
        if (phaseRef.current === "active") { setCameraReady(false); setMicReady(false); actionsRef.current.pause("Your camera or microphone stopped. Reconnect your devices to continue."); }
        else { setCameraReady(false); setMicReady(false); setDeviceError("A device was disconnected. Enable your camera and microphone again."); }
      }; });
    } catch (failure) {
      const messages = { NotAllowedError: "Camera or microphone permission was denied. Allow both in your browser settings, then retry.", NotFoundError: "We could not find a camera and microphone. Connect them and retry.", NotReadableError: "Another app may be using your devices. Close it and retry." };
      setDeviceError(messages[failure.name] || failure.message);
    } finally { if (aliveRef.current) setBusy(false); }
  };
  // One stream/analyser covers setup, voice activity and archival video.
  useEffect(() => {
    const samples = new Uint8Array(1024);
    const timer = setInterval(() => {
      if (!analyserRef.current) return; analyserRef.current.getByteTimeDomainData(samples);
      const level = microphoneLevel(samples); setMicLevel(level);
      if (level >= 4) { setMicReady(true); if (answerRecorderRef.current?.state === "recording" && !pauseRef.current) { spokeRef.current = true; setHasSpoken(true); lastSpeechRef.current = Date.now(); } }
      if (phaseRef.current !== "active" || answerModeRef.current !== "voice" || modeConfirmRef.current || pauseRef.current || processingRef.current || answerRecorderRef.current?.state !== "recording") return;
      const remaining = spokeRef.current ? SILENCE_SECONDS - (Date.now() - lastSpeechRef.current) / 1000 : THINK_SECONDS - (Date.now() - answerStartRef.current) / 1000;
      setAnswerCountdown(Math.max(0, Math.ceil(remaining)));
      if (remaining <= 0 || Date.now() - answerStartRef.current > 180000) submitRecordingRef.current?.(!spokeRef.current);
    }, 120); return () => clearInterval(timer);
  }, []);
  const testSpeaker = async () => {
    setDeviceError("");
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext; const context = contextRef.current || new AudioContextClass(); await context.resume();
      const oscillator = context.createOscillator(); const gain = context.createGain(); oscillator.connect(gain); gain.connect(context.destination); oscillator.frequency.value = 660;
      gain.gain.setValueAtTime(0.12, context.currentTime); gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.7); oscillator.start(); oscillator.stop(context.currentTime + 0.7);
      if (!contextRef.current) oscillator.onended = () => context.close(); setSpeakerTested("played");
    } catch { setDeviceError("We could not play the test sound. Check your output device and volume, then retry."); }
  };

  useEffect(() => {
    if (!session?.session_id) return;
    const socket = io(socketUrl, { auth: { token: getToken() }, reconnection: true, timeout: 8000 }); socketRef.current = socket;
    const onPhone = (data) => { setPhone((previous) => ({ ...previous, ...data, receivedAt: Date.now(), ready: data.ready === true }));
      if (data.ready === false && phaseRef.current === "active" && sessionRef.current?.dual_proctoring_required) actionsRef.current.pause("Your phone camera is unavailable. Keep its companion page visible and reconnect to continue."); };
    socket.on("connect", () => {
      socketAcknowledgement(socket, "join_interview_session", { session_id: session.session_id }).then(() => {
        if (!aliveRef.current || socketRef.current !== socket) return; setConnected(true);
      }).catch((failure) => { setConnected(false); notify(failure.message); });
    });
    socket.on("disconnect", () => { setConnected(false); if (phaseRef.current === "active") actionsRef.current.pause("Your connection to interview monitoring was lost. We are reconnecting."); });
    socket.on("connect_error", () => setConnected(false)); socket.on("mobile_connected", onPhone); socket.on("mobile_status_dashboard", onPhone);
    socket.on("mobile_disconnected", () => { setPhone({ ready: false, status: "disconnected" }); if (phaseRef.current === "active" && sessionRef.current?.dual_proctoring_required) actionsRef.current.pause("Your phone camera disconnected. Keep its companion page open and reconnect to continue."); });
    socket.on("proctoring_status", setProctoring); socket.on("proctoring_alert", (data) => { if (data.session_id && data.session_id !== session.session_id) return; const message = data.message || data.status; if (message && message !== "Status: OK") notify(message, data.type || "proctoring", data.source || "laptop"); });
    const canvas = document.createElement("canvas"); canvas.width = 640; canvas.height = 480;
    const frames = setInterval(() => { if (phaseRef.current !== "active" || !socket.connected || !videoRef.current || videoRef.current.readyState < 2) return;
      canvas.getContext("2d").drawImage(videoRef.current, 0, 0, 640, 480); socket.emit("proctoring_frame", { session_id: session.session_id, image: canvas.toDataURL("image/jpeg", 0.55) }); }, 1250);
    return () => { clearInterval(frames); socket.disconnect(); if (socketRef.current === socket) socketRef.current = null; };
    // UI phases must not reconnect the socket or interrupt the phone.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.session_id, notify, socketUrl]);

  const stopAnswer = useCallback(async () => {
    const recorder = answerRecorderRef.current; if (!recorder || recorder.state === "inactive") return null;
    return new Promise((resolve) => { recorder.onstop = () => { const blob = new Blob(answerChunksRef.current, { type: recorder.mimeType }); answerChunksRef.current = []; answerRecorderRef.current = null; resolve(blob); }; recorder.stop(); });
  }, []);
  const beginListening = useCallback(() => {
    if (phaseRef.current !== "active" || pauseRef.current || processingRef.current || !streamRef.current || answerRecorderRef.current?.state === "recording") return;
    if (answerModeRef.current === "text") { setSpeechState("idle"); return; }
    try { const stream = new MediaStream(streamRef.current.getAudioTracks()); const mimeType = mediaMimeType("audio"); const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
      recordedAnswerRef.current = null; setAudioRetryAvailable(false); answerChunksRef.current = []; recorder.ondataavailable = (event) => { if (event.data.size) answerChunksRef.current.push(event.data); }; answerRecorderRef.current = recorder;
      spokeRef.current = false; setHasSpoken(false); answerStartRef.current = Date.now(); lastSpeechRef.current = Date.now(); setAnswerCountdown(THINK_SECONDS); recorder.start(1000); setSpeechState("listening");
    } catch (failure) { setError(`Could not record your answer: ${failure.message}. You can use the text answer below.`); setSpeechState("idle"); }
  }, []);
  const speak = useCallback(async (text) => {
    stopPlayback(); const requestId = speechRequestRef.current; setSpeechState("speaking");
    const finished = () => { if (requestId !== speechRequestRef.current || phaseRef.current !== "active") return; audioRef.current = null; beginListening(); };
    try { let src = audioCacheRef.current.get(text);
      if (!src) { const data = await request("/speech/synthesize", { method: "POST", body: JSON.stringify({ text, session_id: sessionRef.current.session_id }) }, 4000); if (data.audio_base64) src = `data:audio/mp3;base64,${data.audio_base64}`; }
      if (requestId !== speechRequestRef.current || phaseRef.current !== "active" || pauseRef.current) return;
      if (!src) { finished(); return; } const audio = new Audio(src); audioRef.current = audio; audio.onended = finished; audio.onerror = finished;
      await audio.play().catch(() => { notify("Audio playback is unavailable. Read the question on screen and answer when ready."); finished(); });
    } catch { if (requestId === speechRequestRef.current) { notify("The voice service is taking too long. Read this question and continue."); finished(); } }
  }, [beginListening, notify, request, stopPlayback]);
  const startArchive = useCallback(() => {
    if (archiveRecorderRef.current?.state === "recording") return; const mimeType = mediaMimeType("video");
    const recorder = new MediaRecorder(streamRef.current, { ...(mimeType ? { mimeType } : {}), videoBitsPerSecond: 500000, audioBitsPerSecond: 32000 });
    const chunks = []; archiveChunksRef.current = chunks;
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: recorder.mimeType });
      if (blob.size) archivePartsRef.current.push({ id: recordingPartId(), blob, uploaded: false });
      chunks.length = 0;
    };
    recorder.onerror = () => actionsRef.current.pause("Your interview recording stopped. Check your camera and resume to continue.");
    recorder.start(2000); archiveRecorderRef.current = recorder;
  }, []);
  const captureFace = async () => {
    if (busy || !deviceReady) return; if (!videoRef.current?.videoWidth) { setError("Your camera preview is still loading. Please retry in a moment."); return; }
    setBusy(true); setError("");
    try { const canvas = document.createElement("canvas"); canvas.width = videoRef.current.videoWidth; canvas.height = videoRef.current.videoHeight; canvas.getContext("2d").drawImage(videoRef.current, 0, 0);
      await request(`/interviews/${session.session_id}/register-face`, { method: "POST", body: JSON.stringify({ image: canvas.toDataURL("image/jpeg", 0.85) }) }); setFaceCaptured(true); setPhase(dualRequired ? "phone" : "ready");
    } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  const activate = async () => {
    if (busy || !deviceReady || !faceCaptured || !rulesAccepted || !connected || (dualRequired && !phone.ready)) return; setBusy(true); setError("");
    try { if (!document.fullscreenElement && !window.electronAPI && document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen().catch(() => notify("Fullscreen could not be enabled. Use the GenHire kiosk browser for a secure interview."));
      const data = await request(`/interviews/${session.session_id}/activate`, { method: "POST", body: JSON.stringify({ camera_ready: cameraReady, microphone_ready: micReady, speaker_ready: speakerTested === true }) });
      await socketAcknowledgement(socketRef.current, "start_proctoring", { session_id: session.session_id });
      if (dualRequired) await socketAcknowledgement(socketRef.current, "control_mobile_recording", { session_id: session.session_id, action: "start" });
      if (data.current_question) { setQuestion(data.current_question); questionRef.current = data.current_question; }
      setQuestionDeadline(data.question_deadline ?? session.question_deadline ?? null);
      startArchive(); phaseRef.current = "active"; setPhase("active"); setPauseReason(""); pauseRef.current = "";
      startedAtRef.current = Date.now() - elapsed * 1000; speak(questionRef.current);
    } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };

  const uploadArchive = useCallback(async () => {
    if (archiveUploadRef.current || !archivePartsRef.current.some((part) => !part.uploaded)) return;
    archiveUploadRef.current = true; setUploadStatus("uploading");
    try { for (const part of archivePartsRef.current) {
      if (part.uploaded) continue; const form = new FormData(); const blob = part.blob;
      form.append("recording", blob, `interview-${sessionRef.current.session_id}.${blob.type.includes("mp4") ? "mp4" : "webm"}`); form.append("recording_part", part.id);
      await request(`/interviews/${sessionRef.current.session_id}/upload-recording`, { method: "POST", body: form }, 120000); part.uploaded = true; part.blob = null;
    } setUploadStatus("success");
    } catch { setUploadStatus("error"); }
    finally { archiveUploadRef.current = false; }
  }, [request]);
  const finish = useCallback(async () => {
    if (["ending", "completed", "discarded"].includes(phaseRef.current)) return; processingRef.current = true; phaseRef.current = "ending"; setPhase("ending"); setShowEndConfirm(false); setError(""); stopPlayback(); await stopAnswer();
    const recorder = archiveRecorderRef.current;
    if (recorder && recorder.state !== "inactive") await new Promise((resolve) => { recorder.addEventListener("stop", resolve, { once: true }); recorder.stop(); });
    if (socketRef.current?.connected) {
      const commands = [socketAcknowledgement(socketRef.current, "stop_proctoring", { session_id: sessionRef.current.session_id })];
      if (sessionRef.current.dual_proctoring_required) commands.push(socketAcknowledgement(socketRef.current, "control_mobile_recording", { session_id: sessionRef.current.session_id, action: "stop" }));
      Promise.allSettled(commands); // REST completion freezes server monitoring; transport ACKs must not delay the report.
    }
    streamRef.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    await contextRef.current?.close().catch(() => {}); contextRef.current = null; analyserRef.current = null;
    uploadArchive(); // Independent storage: no WASM download/remux blocks evaluation.
    try { const practice = isPracticeSession(location, sessionRef.current); const data = await request(`/${practice ? "practice" : "interviews"}/${sessionRef.current.session_id}/end`, { method: "POST" }, 15000);
      setResult(data); const nextPhase = terminalPhase(data) || "completed"; phaseRef.current = nextPhase; setPhase(nextPhase);
      try { sessionStorage.removeItem(CACHE_KEY); sessionStorage.setItem("credits-needs-refresh", "true"); } catch { /* results are persisted on the server */ }
    } catch (failure) { setError(failure.message); setPhase("end_failed"); }
    finally { processingRef.current = false; socketRef.current?.disconnect(); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); }
  }, [location, request, stopAnswer, stopPlayback, uploadArchive]);
  actionsRef.current.finish = finish;
  const submitAnswer = useCallback(async (answer) => {
    if (phaseRef.current !== "active" || submitRequestRef.current) return;
    if (pauseRef.current) { setPendingAnswer({ answer, question: questionRef.current }); setSpeechState("idle"); processingRef.current = false; return; }
    const submittedQuestion = questionRef.current; submitRequestRef.current = true; processingRef.current = true; setSpeechState("thinking"); setError("");
    try { const practice = isPracticeSession(location, sessionRef.current); const data = await request(`/${practice ? "practice" : "interviews"}/${sessionRef.current.session_id}/answer`, { method: "POST", body: JSON.stringify({ question: submittedQuestion, answer }) }, 20000);
      setPendingAnswer(null); setDraft(""); recordedAnswerRef.current = null; setAudioRetryAvailable(false); if (data.interview_complete) { processingRef.current = false; await finish(); return; }
      if (!data.next_question) throw new Error("The next question is unavailable. Please retry your saved answer."); setQuestion(data.next_question); questionRef.current = data.next_question;
      setQuestionDeadline(data.question_deadline ?? null);
      setQuestionCount((count) => data.progress?.questions_asked != null ? data.progress.questions_asked + 1 : data.repeated_question ? count : count + 1); processingRef.current = false;
      speak(data.next_question);
    } catch (failure) {
      // A timed-out POST may already have saved its answer. Read the authority
      // before retrying so it can never be sent against the following question.
      try {
        const latest = await request(`/interviews/${sessionRef.current.session_id}/session`, {}, 6000);
        const recovered = reconcileAnswer(latest, submittedQuestion, answer); sessionRef.current = { ...sessionRef.current, ...latest }; setSession(sessionRef.current);
        if (recovered.terminal) { setResult(latest); phaseRef.current = recovered.terminal; setPhase(recovered.terminal); setPendingAnswer(null); return; }
        if (recovered.finish) { setPendingAnswer(null); processingRef.current = false; await finish(); return; }
        if (recovered.accepted && recovered.question) {
          setQuestion(recovered.question); questionRef.current = recovered.question; setQuestionCount(recovered.questionCount);
          setQuestionDeadline(latest.question_deadline ?? null);
          setPendingAnswer(null); setDraft(""); processingRef.current = false; notify("Your answer was saved. Continuing with the next question."); speak(recovered.question); return;
        }
        if (latest.engine_available === false) { setError("The live interviewer is unavailable. End with your saved answers to generate your report."); actionsRef.current.pause("The interviewer connection could not be restored. You can finish with your saved answers."); return; }
      } catch { /* keep the local answer until the same request can be retried */ }
      setError(failure.message); setPendingAnswer({ answer, question: submittedQuestion }); setSpeechState("idle");
    } finally { processingRef.current = false; submitRequestRef.current = false; }
  }, [finish, location, notify, request, speak]);
  const submitRecording = useCallback(async (skip = false, retry = false) => {
    if (processingRef.current || phaseRef.current !== "active" || pauseRef.current) return; processingRef.current = true; setSpeechState("transcribing"); setError("");
    try { const blob = retry ? recordedAnswerRef.current : await stopAnswer(); if (skip) { await submitAnswer(""); return; } if (!blob?.size) throw new Error("No answer was recorded. Please retry or type your answer.");
      recordedAnswerRef.current = blob;
      const audio = await transcriptionAudio(blob, streamRef.current); const data = await request("/speech/transcribe", { method: "POST", body: JSON.stringify({ ...audio, session_id: sessionRef.current.session_id }) }, 35000);
      const answer = data.transcript?.trim(); if (!answer) throw new Error("We could not hear your answer clearly. Please retry or use a text answer."); await submitAnswer(answer);
    } catch (failure) { processingRef.current = false; setAudioRetryAvailable(!!recordedAnswerRef.current?.size); setError(failure.message); setSpeechState("idle"); }
  }, [request, stopAnswer, submitAnswer]);
  submitRecordingRef.current = submitRecording;
  const changeAnswerMode = async (mode) => {
    if (processingRef.current || pauseRef.current || mode === answerModeRef.current) return;
    answerModeRef.current = mode; setAnswerMode(mode); modeConfirmRef.current = false; setShowModeConfirm(false);
    stopPlayback(); processingRef.current = true;
    try {
      await stopAnswer();
      recordedAnswerRef.current = null; setAudioRetryAvailable(false); setHasSpoken(false); spokeRef.current = false;
      setSpeechState("idle");
    } finally { processingRef.current = false; }
    if (mode === "voice") beginListening();
  };
  const requestAnswerMode = mode => {
    if (mode === answerModeRef.current || processingRef.current || pauseRef.current) return;
    if ((mode === "text" && (hasSpoken || audioRetryAvailable)) || (mode === "voice" && draft.trim())) {
      modeConfirmRef.current = true; setModeToConfirm(mode); setShowModeConfirm(true);
    }
    else changeAnswerMode(mode);
  };
  const pause = useCallback(async (reason) => {
    if (pauseRef.current || phaseRef.current !== "active") return; pauseRef.current = reason; setPauseReason(reason);
    modeConfirmRef.current = false; setShowModeConfirm(false); stopPlayback(); const blob = await stopAnswer();
    if (blob?.size && spokeRef.current) actionsRef.current.interruptedAudio = blob; setSpeechState("idle");
  }, [stopAnswer, stopPlayback]);
  actionsRef.current.pause = pause;
  const resume = async () => {
    if (!connected || (dualRequired && !phone.ready) || busy) return;
    if (!streamRef.current?.getTracks().every((track) => track.readyState === "live")) { await enableDevices(); return; }
    if (!deviceReady) { setDeviceError("Say a short sentence so we can check your microphone again."); return; }
    setBusy(true);
    try {
      await socketAcknowledgement(socketRef.current, "start_proctoring", { session_id: session.session_id });
      if (dualRequired) await socketAcknowledgement(socketRef.current, "control_mobile_recording", { session_id: session.session_id, action: "start" });
      startArchive();
    } catch (failure) { setDeviceError(failure.message); setBusy(false); return; }
    setBusy(false); setPauseReason(""); pauseRef.current = ""; setError("");
    if (actionsRef.current.interruptedAudio) {
      setSpeechState("transcribing"); processingRef.current = true;
      try { const audio = await transcriptionAudio(actionsRef.current.interruptedAudio, streamRef.current); const data = await request("/speech/transcribe", { method: "POST", body: JSON.stringify({ ...audio, session_id: session.session_id }) }, 35000);
        setDraft(data.transcript || ""); answerModeRef.current = "text"; setAnswerMode("text"); actionsRef.current.interruptedAudio = null; setError("Your interrupted answer has been restored. Review and send it, or record the question again.");
      } catch (failure) { setError(failure.message); } finally { processingRef.current = false; setSpeechState("idle"); }
    } else if (pendingAnswer !== null || draftRef.current.trim() || answerModeRef.current === "text") setSpeechState("idle"); else speak(questionRef.current);
  };
  const refreshPhoneLink = async () => {
    if (busy) return; setBusy(true); setDeviceError("");
    try {
      const latest = await request(`/interviews/${session.session_id}/session`);
      if (terminalPhase(latest) || latest.engine_available === false) throw new Error("This interview is no longer available. Finish with your saved answers to return safely.");
      if (!latest.mobile_pairing_token) throw new Error("A phone pairing link is unavailable. Please retry.");
      setSession(previous => ({ ...previous, mobile_pairing_token: latest.mobile_pairing_token }));
    } catch (failure) { setDeviceError(failure.message); }
    finally { setBusy(false); }
  };
  useEffect(() => {
    if (phase !== "active" || !Number.isFinite(questionDeadline)) { setQuestionRemaining(null); return; }
    const update = () => setQuestionRemaining(Math.max(0, Math.ceil(questionDeadline - Date.now() / 1000)));
    update(); const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [phase, questionDeadline]);
  useEffect(() => {
    if (phase !== "active") return; const tick = setInterval(() => setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000)), 1000);
    const violation = (type) => { if (pauseRef.current) return; notify("Keep this interview window in view. Leaving the interview is recorded for review.", type); socketRef.current?.emit("proctoring_violation", { session_id: sessionRef.current.session_id, type }); };
    const visibility = () => { if (document.hidden) violation("tab_switch"); }; const fullscreen = () => { if (!document.fullscreenElement && !window.electronAPI) violation("fullscreen_exit"); };
    const offline = () => pause("You are offline. Reconnect to continue; submitted answers are saved.");
    window.electronAPI?.onAppSwitched(() => violation("window_blur"));
    document.addEventListener("visibilitychange", visibility); document.addEventListener("fullscreenchange", fullscreen); window.addEventListener("offline", offline);
    return () => { clearInterval(tick); document.removeEventListener("visibilitychange", visibility); document.removeEventListener("fullscreenchange", fullscreen); window.removeEventListener("offline", offline); };
  }, [phase, notify, pause]);
  useEffect(() => {
    if (!["active", "ending", "end_failed", "recovery_failed"].includes(phase) && !["uploading", "error"].includes(uploadStatus)) return;
    const beforeUnload = event => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [phase, uploadStatus]);
  useEffect(() => {
    if (!window.electronAPI) return;
    if (phase === "active") window.electronAPI.enableKiosk(); else window.electronAPI.disableKiosk();
    return () => window.electronAPI.disableKiosk();
  }, [phase]);
  useEffect(() => {
    if (!dualRequired) return;
    const timer = setInterval(() => setPhone((previous) => {
      if (!previous.ready || Date.now() - previous.receivedAt < 15000) return previous;
      if (phaseRef.current === "active") actionsRef.current.pause("Your phone camera stopped sending frames. Keep its page open and reconnect to continue.");
      return { ...previous, ready: false, status: "disconnected" };
    }), 1000);
    return () => clearInterval(timer);
  }, [dualRequired]);
  useEffect(() => {
    if (phase !== "completed" || !session?.session_id) return;
    let cancelled = false; let timer; let attempts = 0;
    const refresh = async () => {
      try {
        const latest = await request(`/interviews/${session.session_id}/session`, {}, 8000);
        if (cancelled) return; setResult(latest);
        const pending = latest.cv_score_status === "pending" || latest.evaluation?.pending_answers > 0 || latest.identity_verification?.status === "score_pending";
        if (!pending) return;
      } catch { /* an already saved report remains available during a retry */ }
      if (!cancelled && ++attempts < 30) timer = setTimeout(refresh, 5000);
    };
    timer = setTimeout(refresh, 2500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [phase, session?.session_id, request]);
  useEffect(() => { aliveRef.current = true; return () => {
    aliveRef.current = false; stopPlayback(); socketRef.current?.disconnect();
    [answerRecorderRef.current, archiveRecorderRef.current].forEach((recorder) => { if (recorder && recorder.state !== "inactive") { try { recorder.onstop = null; recorder.stop(); } catch { /* already stopped */ } } });
    streamRef.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); }); contextRef.current?.close().catch(() => {});
  }; }, [stopPlayback]);

  const back = () => {
    if (uploadStatus === "uploading") return;
    if (uploadStatus === "error") { setShowLeaveConfirm(true); return; }
    navigate(isPractice ? "/practice" : "/applications");
  };
  const renderVideo = () => <video ref={bindVideo} autoPlay playsInline muted className={styles.preview} aria-label="Your camera preview" />;
  const renderError = (message) => message && <div className={styles.error} role="alert"><CircleAlert size={18} /><span>{message}</span></div>;
  const leaveConfirm = <ConfirmDialog isOpen={showLeaveConfirm} onClose={() => setShowLeaveConfirm(false)} onConfirm={() => navigate(isPractice ? "/practice" : "/applications")}
    title="Leave without uploading the recording?" message="Your report is saved. The recording is still on this device and will be lost if you leave. You can cancel and retry the upload."
    confirmText="Leave without recording" />;
  const step = phase === "devices" ? 0 : phase === "face" ? 1 : phase === "phone" ? 2 : 3;
  if (["loading", "start_failed", "ending", "end_failed", "recovery_failed"].includes(phase)) return <main className={styles.shell}><div className={styles.centerCard}>
    <span className={styles.brand}><ShieldCheck size={20} /> GenHire interview</span>{["loading", "ending"].includes(phase) && <div className={styles.spinner} />}
    <h1>{phase === "loading" ? "Preparing your interview" : phase === "ending" ? "Your answers are saved" : phase === "end_failed" ? "Complete your report" : phase === "recovery_failed" ? "Recover your saved answers" : "Unable to open the interview"}</h1>
    <p>{phase === "loading" ? "Loading your role and question. Device checks come next." : phase === "ending" ? "Generating your evaluation. Your recording uploads separately." : "Retry to continue with the same session."}</p>{renderError(error)}
    {["end_failed", "recovery_failed"].includes(phase) && <button className={styles.primary} onClick={finish}>{phase === "recovery_failed" ? "Finish with saved answers" : "Retry report generation"}</button>}{phase === "start_failed" && <button className={styles.primary} onClick={() => window.location.reload()}>Retry</button>}
    <button className={styles.textButton} disabled={uploadStatus === "uploading"} onClick={back}>Back to {isPractice ? "practice" : "applications"}</button>
  {leaveConfirm}</div></main>;
  if (["completed", "discarded"].includes(phase)) {
    const report = { ...session, ...result, session_id: session?.session_id, cv_score: scorePercent(result?.cv_score ?? session?.cv_score ?? (session?.similarity_score == null ? null : session.similarity_score * 100)) };
    return <main className={styles.shell}><section className={styles.resultCard}><div className={styles.successIcon}><Check size={30} /></div><span className={styles.eyebrow}>{isPractice ? "Practice feedback" : "Interview complete"}</span>
      <h1>{phase === "discarded" ? "No answers were submitted" : "Your interview report is ready"}</h1><p>{phase === "discarded" ? result?.message || "This attempt was discarded. Return and start a fresh session." : "Review your performance, CV match and monitoring coverage below."}</p>
      {phase !== "discarded" && <><div className={styles.scoreGrid}>{[["Interview score", interviewScore(result), result?.evaluation?.pending_answers > 0], ["CV match", report.cv_score, result?.cv_score_status === "pending"], ["Proctoring score", result?.proctoring_status === "incomplete" ? null : scorePercent(result?.proctoring_score), false]].map(([label, score, pending]) => <div className={styles.scoreCard} key={label}><span>{label}</span><strong>{score == null ? pending ? "Processing" : "Unavailable" : `${score}%`}</strong>{pending && score != null && <small>Updating remaining checks</small>}</div>)}</div>
        {(result?.evaluation?.pending_answers > 0 || result?.cv_score_status === "pending") && <p className={styles.note} role="status">Some scoring checks are finishing in the background. This report refreshes automatically; you can also reopen it from your dashboard.</p>}
        {result?.proctoring_status === "incomplete" && <p className={styles.note}>Monitoring coverage was incomplete. The report explains which checks were available.</p>}<button className={styles.primary} onClick={() => setShowReport(true)}>View evaluation and transcript <ChevronRight size={18} /></button></>}
      {uploadStatus === "uploading" && <p className={styles.note} role="status">Recording upload is in progress. Keep this page open until it finishes.</p>}{uploadStatus === "success" && <p className={styles.note}>Your recording was saved.</p>}{uploadStatus === "error" && <div className={styles.error}>Your report is saved, but the recording upload failed. <button onClick={uploadArchive}>Retry upload</button></div>}
      <button className={styles.textButton} disabled={uploadStatus === "uploading"} onClick={back}>Back to {isPractice ? "practice" : "applications"}</button><InterviewReportModal apiBase={apiBase} isOpen={showReport} onClose={() => setShowReport(false)} report={report} cvScore={report.cv_score} interviewScore={interviewScore(result)} />
    {leaveConfirm}</section></main>;
  }
  if (phase !== "active") return <main className={styles.shell}><div className={styles.setupLayout}>
    <aside className={styles.setupAside}><span className={styles.brand}><ShieldCheck size={22} /> GenHire</span><span className={styles.eyebrow}>{isPractice ? "Practice interview" : "Your next opportunity"}</span><h1>Prepare for your interview</h1><p>Check your camera, microphone and speakers, register your face, then start your interview.</p>
      <ol className={styles.steps}>{["Laptop checks", "Face registration", ...(dualRequired ? ["Connect your phone"] : []), "Start interview"].map((label, index) => { const position = !dualRequired && index === 2 ? 3 : index; return <li key={label} className={position === step ? styles.currentStep : position < step ? styles.doneStep : ""}><span>{position < step ? <Check size={16} /> : index + 1}</span>{label}</li>; })}</ol>
      <div className={styles.privacyNote}><ShieldCheck size={20} /><p>Your camera remains visible. Monitoring warnings are recorded for review; a warning alone is not a decision about your performance.</p></div>
    </aside><section className={styles.setupCard}>
      <span className={styles.eyebrow}>{phase === "devices" ? "Step 1 · Your laptop" : phase === "face" ? "Step 2 · Face registration" : phase === "phone" ? "Step 3 · Second camera" : "Ready to begin"}</span>
      <h2>{phase === "devices" ? "Check your devices" : phase === "face" ? "Center your face in the preview" : phase === "phone" ? "Connect your mobile camera" : "Start your interview"}</h2>
      <p>{phase === "devices" ? "Allow camera and microphone access, speak a short sentence, then check your speakers." : phase === "face" ? "Sit in good light with only your face visible. We'll capture one image for this session." : phase === "phone" ? "Your recruiter requires a second view. Scan this private QR code on your phone, enable its camera, and leave the page open." : "The interviewer asks one question at a time. Take a moment to think, answer naturally, and use Send answer whenever you're finished."}</p>
      {phase === "devices" && <><div className={styles.devicePreview}>{renderVideo()}{!cameraReady && <span className={styles.cameraPlaceholder}><Camera size={32} />Camera preview</span>}</div>
        <div className={styles.deviceRow}><Camera size={20} /><span>Camera</span><strong className={cameraReady ? styles.good : ""}>{cameraReady ? "Ready" : "Waiting for permission"}</strong></div><div className={styles.deviceRow}><Mic size={20} /><span>Microphone <span className={styles.meter}><i style={{ width: `${micLevel}%` }} /></span></span><strong className={micReady ? styles.good : ""}>{micReady ? "Sound detected" : "Say a short sentence"}</strong></div>
        <div className={styles.deviceRow}><Headphones size={20} /><span>Speakers</span><button className={styles.secondary} onClick={testSpeaker}><Volume2 size={15} />Play test sound</button></div>{speakerTested === "played" && <button className={styles.secondary} onClick={() => setSpeakerTested(true)}>I heard the sound <Check size={16} /></button>}{speakerTested === true && <p className={styles.good}><Check size={16} /> Speakers confirmed</p>}
        {renderError(deviceError)}<div className={styles.actions}><button className={styles.secondary} onClick={enableDevices} disabled={busy}>{busy ? "Checking devices…" : cameraReady ? "Retry device checks" : "Enable camera and microphone"}</button><button className={styles.primary} disabled={!deviceReady || busy} onClick={() => { setError(""); setPhase(faceCaptured ? dualRequired ? "phone" : "ready" : "face"); }}>Continue <ChevronRight size={17} /></button></div></>}
      {phase === "face" && <><div className={styles.facePreview}>{renderVideo()}<span className={styles.faceGuide} /></div><p className={styles.note}>{isPractice ? "This capture is used only for practice monitoring." : "Your capture is compared with your uploaded identity card in the background and included in the evaluation report."}</p>{renderError(error)}<div className={styles.actions}><button className={styles.secondary} onClick={() => setPhase("devices")}>Back</button><button className={styles.primary} onClick={captureFace} disabled={busy}>{busy ? "Capturing face…" : "Capture my face"}<Camera size={18} /></button></div></>}
      {phase === "phone" && <><div className={styles.phonePairing}>{phoneUrl ? <div className={styles.qr}><QRCode value={phoneUrl} size={172} /></div> : <div className={styles.error}>The private phone link is unavailable. Reload this session to refresh it.</div>}<div><Smartphone size={30} /><h3>{phone.ready ? "Phone camera is ready" : "Waiting for your phone"}</h3><p>Place it beside you, aimed at you, your laptop and desk. Keep it plugged in and turn off auto-lock.</p><span className={`${styles.badge} ${phone.ready ? styles.goodBadge : ""}`}>{phone.ready ? "Camera and microphone connected" : phone.status === "connected" ? "Phone connected · enable its camera" : "Scan the QR code"}</span></div></div><p className={styles.note}>This private link grants access only to this interview's companion camera.</p><button className={styles.primary} disabled={!phone.ready} onClick={() => setPhase("ready")}>Continue <ChevronRight size={18} /></button></>}
      {phase === "ready" && <><div className={styles.readySummary}><Check size={18} /> Camera, microphone and speakers checked<br /><Check size={18} /> Face captured{dualRequired && <><br /><Check size={18} /> Second camera {phone.ready ? "ready" : "disconnected"}</>}</div><label className={styles.consent}><input type="checkbox" checked={rulesAccepted} onChange={(event) => setRulesAccepted(event.target.checked)} /><span>I'm in a quiet, well-lit place and have time to finish. I'll keep my face visible, stay in this window and use no outside help{dualRequired ? ". My phone is positioned only as the required second camera" : ""}.</span></label><p className={styles.note}>{maxQuestions} questions · Usually 15–20 minutes · Your answer starts after the interviewer finishes speaking.</p>
        {!connected && renderError("Connecting to interview monitoring. Check your internet connection if this takes more than a few seconds.")}{dualRequired && !phone.ready && renderError("Your phone disconnected. Reopen its companion page before starting.")}{renderError(error)}<div className={styles.actions}><button className={styles.secondary} onClick={() => setPhase(dualRequired ? "phone" : "face")}>Back</button><button className={styles.primary} onClick={activate} disabled={busy || !deviceReady || !rulesAccepted || !connected || (dualRequired && !phone.ready)}>{busy ? "Starting…" : "Start interview"}<ChevronRight size={18} /></button></div></>}
    </section></div></main>;

  return <main className={styles.interviewShell}><header className={styles.interviewHeader}><span className={styles.brand}><ShieldCheck size={22} /> GenHire <small>{isPractice ? "Practice" : "Interview"}</small></span><span>Question {questionCount} of {maxQuestions}</span><span className={styles.elapsed}>{formatTime(elapsed)}</span></header><div className={styles.progressTrack} role="progressbar" aria-label="Interview question progress" aria-valuemin={1} aria-valuemax={maxQuestions} aria-valuenow={Math.min(questionCount, maxQuestions)}><i style={{ width: `${Math.min(100, (questionCount / maxQuestions) * 100)}%` }} /></div>
    {warning && <div className={styles.warning} role="status"><CircleAlert size={20} /><div><strong>Monitoring notice {warningCount ? `· ${warningCount}` : ""}</strong><p>{warning.message}</p></div><button onClick={() => setWarning(null)} aria-label="Dismiss monitoring notice">×</button></div>}
    <section className={styles.interviewGrid}><article className={styles.conversation}><div className={styles.interviewerBadge}><span>A</span><div><strong>Alex</strong><small>Your AI interviewer</small></div><i className={speechState === "speaking" ? styles.speakingDot : ""} /></div><span className={styles.eyebrow}>{speechState === "thinking" ? "Preparing your next question" : "Let's talk about your experience"}</span><h1 className={styles.question}>{question}</h1>
      <div className={styles.conversationStatus} aria-live="polite">{answerMode === "text" && speechState === "idle" ? "Type your answer, then select Send text answer" : speechState === "speaking" ? "Alex is speaking…" : speechState === "transcribing" ? "Turning your answer into text…" : speechState === "thinking" ? "Your answer is being saved…" : speechState === "listening" ? hasSpoken ? answerCountdown <= 5 ? `Finished? Sending in ${answerCountdown}s of silence` : "Listening to your answer" : answerCountdown <= 15 ? `Answer when ready · moving on in ${answerCountdown}s` : "Take a moment, then answer naturally" : "Ready when you are"}</div>{renderError(error)}
      {pendingAnswer !== null && <div className={styles.savedAnswer}><p>Your answer is preserved for retry.</p><button className={styles.primary} disabled={!!pauseReason || speechState === "thinking"} onClick={() => submitAnswer(pendingAnswer.answer)}>Retry saved answer</button></div>}
      {questionRemaining !== null && <p className={styles.questionClock}>Question time remaining <strong>{formatTime(questionRemaining)}</strong>{questionRemaining === 0 && <span>Time limit reached. Submit to continue.</span>}</p>}
      <AnswerComposer mode={answerMode} onModeChange={requestAnswerMode} speechState={speechState} paused={!!pauseReason}
        pendingAnswer={pendingAnswer} audioRetryAvailable={audioRetryAvailable} hasSpoken={hasSpoken} draft={draft} onDraftChange={setDraft}
        onSendText={async () => { processingRef.current = true; stopPlayback(); await stopAnswer(); submitAnswer(draft.trim()); }}
        onSendVoice={() => submitRecording(false)} onRetryAudio={() => submitRecording(false, true)}
        onRepeat={async () => { await stopAnswer(); speak(question); }} onRecord={beginListening}
        onMoreTime={() => { answerStartRef.current = Date.now(); setAnswerCountdown(THINK_SECONDS); }} />
    </article><aside className={styles.monitorPanel}><div className={styles.candidatePreview}>{!pauseReason && renderVideo()}<span>You</span></div><h3><ShieldCheck size={19} /> Interview monitoring</h3><div className={styles.monitorRow}><span>Laptop camera</span><strong className={cameraReady ? styles.good : ""}>{cameraReady ? "Connected" : "Reconnect"}</strong></div><div className={styles.monitorRow}><span>Microphone</span><span className={styles.meter}><i style={{ width: `${micLevel}%` }} /></span></div>{dualRequired && <div className={styles.monitorRow}><span>Phone camera</span><strong className={phone.ready ? styles.good : ""}>{phone.ready ? "Connected" : "Reconnect"}</strong></div>}<div className={styles.monitorRow}><span>Live checks</span><strong>{!connected ? "Reconnecting" : proctoring?.available === false ? "Limited coverage" : proctoring?.analyzed_frames > 0 ? "Active" : "Connecting"}</strong></div>
      {proctoring?.capabilities?.object_detection === false && <p className={styles.note}>Object detection is unavailable. Camera recording and other available checks continue.</p>}<p className={styles.note}>Keep your face visible and your desk clear. Only the paired phone used for monitoring is permitted.</p><button className={styles.endButton} disabled={["transcribing", "thinking"].includes(speechState)} onClick={() => setShowEndConfirm(true)}>End interview</button></aside></section>
    <Modal isOpen={!!pauseReason} closeOnEsc={false} closeOnOverlayClick={false}
      overlayClassName={styles.pauseOverlay} contentClassName={`${styles.centerCard} ${styles.reconnectCard}`} ariaLabelledBy="reconnect-title">
      <CircleAlert size={30} /><h2 id="reconnect-title">Reconnect your devices</h2><p>{pauseReason}</p>
      <p className={styles.note}>Submitted answers are saved. Your interrupted answer and typed draft stay on this device. The question time limit continues during reconnection.</p>
      <div className={styles.recoveryPreview}>{pauseReason && renderVideo()}</div>
      <dl className={styles.recoveryChecks}>
        <div><dt>Monitoring connection</dt><dd>{connected ? "Connected" : "Reconnecting"}</dd></div>
        <div><dt>Laptop camera</dt><dd>{cameraReady ? "Ready" : "Needs permission or reconnection"}</dd></div>
        <div><dt>Microphone</dt><dd>{micReady ? "Sound detected" : "Speak a short sentence"}<span className={styles.meter}><i style={{ width: `${micLevel}%` }} /></span></dd></div>
        {dualRequired && <div><dt>Phone camera</dt><dd>{phone.ready ? "Ready" : "Reopen the companion page"}</dd></div>}
      </dl>
      {!connected && <button className={styles.secondary} onClick={() => socketRef.current?.connect()}>Retry connection</button>}
      {(!cameraReady || !micReady) && <button className={styles.secondary} onClick={enableDevices} disabled={busy}>{busy ? "Checking devices..." : "Retry device checks"}</button>}
      {dualRequired && !phone.ready && <div className={styles.recoveryPhone}>
        <p>Reopen the companion page on your phone, allow camera access and keep the screen unlocked. Scan this code again if the link expired.</p>
        {phoneUrl && <div className={styles.qr}><QRCode value={phoneUrl} size={140} /></div>}
        <button className={styles.secondary} onClick={refreshPhoneLink} disabled={busy}>Refresh phone pairing code</button>
      </div>}
      {renderError(deviceError)}
      <button className={styles.primary} onClick={resume} disabled={!connected || !deviceReady || (dualRequired && !phone.ready) || busy}>{busy ? "Checking devices..." : "Resume interview"}</button>
      <button className={styles.textButton} onClick={() => setShowEndConfirm(true)}>End with saved answers</button>
    </Modal>
    <ConfirmDialog isOpen={showEndConfirm} onClose={() => setShowEndConfirm(false)} onConfirm={finish} title="Finish this interview?"
      message={draft.trim() ? "Your typed draft has not been submitted. Cancel and choose Send text answer to include it. Finishing evaluates only your submitted answers." : "Your submitted answers will be evaluated. An answer currently being recorded will not be submitted. Use Send answer first if you want to include it."} confirmText="Finish interview" />
    <ConfirmDialog isOpen={showModeConfirm} onClose={() => { modeConfirmRef.current = false; lastSpeechRef.current = Date.now(); setShowModeConfirm(false); }}
      onConfirm={() => changeAnswerMode(modeToConfirm)} title={modeToConfirm === "text" ? "Switch to a typed answer?" : "Switch to a spoken answer?"}
      message={modeToConfirm === "text" ? "The current spoken recording has not been submitted. Switching discards that recording so you can type this answer instead. Your previously submitted answers stay saved." : "Your typed draft has not been submitted. Switching starts automatic voice capture. Submit your draft first to include it, or switch to answer this question aloud."}
      confirmText={modeToConfirm === "text" ? "Switch to typing" : "Switch to speaking"} confirmVariant="primary" />
  </main>;
}

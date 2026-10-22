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
import VoiceSphere from "../components/VoiceSphere";
import { playInterviewerSpeech } from "../utils/interviewerSpeech";
import { proctoringNotice } from "../utils/proctoringNotice";
import { startLiveCaptions } from "../utils/liveCaptions";
import { createVoiceTurn, voicePolicy } from "../utils/voiceActivity";
import { interviewRequest, interviewScore, isPracticeSession, mediaMimeType, microphoneLevel, mobilePairingUrl, recordingPartId, reconcileAnswer, scorePercent, socketAcknowledgement, terminalPhase, transcriptionAudio } from "../utils/session";
import styles from "./InterviewExperience.module.css";
import GenHireBrand from "shared/components/ui/GenHireBrand";
import { captureProgress, createFaceDetector, facePosition, faceSnapshot } from "../utils/faceCapture";

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
  const [showSpeakerCheck, setShowSpeakerCheck] = useState(false);
  const deviceRequestRef = useRef(false); const permissionAttemptedRef = useRef(false);
  const [rulesAccepted, setRulesAccepted] = useState(false); const [faceCaptured, setFaceCaptured] = useState(false);
  const [facePhoto, setFacePhoto] = useState(""); const facePhotoRef = useRef("");
  const faceResetRef = useRef(0);
  const [faceHint, setFaceHint] = useState("Preparing automatic capture…");
  const [faceProgress, setFaceProgress] = useState(0);
  const [phone, setPhone] = useState({ ready: false, status: "disconnected" }); const [connected, setConnected] = useState(false);
  const [proctoring, setProctoring] = useState(null); const [warning, setWarning] = useState(null);
  const [integrity, setIntegrity] = useState({ count: 0, counts_by_type: {} });
  const [turns, setTurns] = useState([]); const [captionNote, setCaptionNote] = useState("");
  const [aiCaption, setAiCaption] = useState(""); const [speechError, setSpeechError] = useState(""); const playbackRef = useRef(null);
  const voiceAudioRef = useRef({ microphone: null, speaker: null }); const speakerNodesRef = useRef(null);
  const liveCaptionsRef = useRef(null), captionGenerationRef = useRef(0), transcriptTailRef = useRef(null);
  const [question, setQuestion] = useState(""); const [questionCount, setQuestionCount] = useState(1); const [speechState, setSpeechState] = useState("idle");
  const [hasSpoken, setHasSpoken] = useState(false); const [answerCountdown, setAnswerCountdown] = useState(10);
  const [draft, setDraft] = useState(""); const [pendingAnswer, setPendingAnswer] = useState(null); const [elapsed, setElapsed] = useState(0);
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
  const startedAtRef = useRef(null); const voiceTurnRef = useRef(null); const setupLevelsRef = useRef([]);
  const spokeRef = useRef(false); const processingRef = useRef(false); const pauseRef = useRef(""); const submitRecordingRef = useRef(null);
  const actionsRef = useRef({}); const lastWarningRef = useRef({}); const draftRef = useRef(draft); draftRef.current = draft;
  const request = useCallback((path, options = {}, timeout = 15000) => interviewRequest(apiBase, path, getToken(), options, timeout), [apiBase]);
  const isPractice = isPracticeSession(location, session || {}); const dualRequired = session?.dual_proctoring_required === true;
  const timing = voicePolicy(session?.voice_policy);
  const maxQuestions = session?.max_questions || 12; const phoneUrl = mobilePairingUrl(session, webOrigin);
  const deviceReady = cameraReady && micReady && speakerTested === true;
  phaseRef.current = phase; sessionRef.current = session; questionRef.current = question; pauseRef.current = pauseReason;

  const bindVideo = useCallback((element) => { videoRef.current = element; if (element && streamRef.current) element.srcObject = streamRef.current; }, []);
  const notify = useCallback((message, type = "notice", source = "laptop") => {
    const key = `${source}:${type}`; if (Date.now() - (lastWarningRef.current[key] || 0) < 8000) return;
    lastWarningRef.current[key] = Date.now(); setWarning({ ...proctoringNotice(message, type, source), type, source });
  }, []);
  useEffect(() => { if (!warning) return; const timer = setTimeout(() => setWarning(null), 1800); return () => clearTimeout(timer); }, [warning]);
  useEffect(() => { transcriptTailRef.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" }); }, [turns, question, draft, aiCaption]);
  const stopPlayback = useCallback(() => {
    speechRequestRef.current += 1; playbackRef.current?.cancel(); playbackRef.current = null;
    speakerNodesRef.current?.source.disconnect(); speakerNodesRef.current?.analyser.disconnect(); speakerNodesRef.current = null; voiceAudioRef.current.speaker = null;
    if (audioRef.current) { audioRef.current.onended = null; audioRef.current.pause(); audioRef.current.src = ""; audioRef.current = null; }
  }, []);
  const applyIntegrity = useCallback((data) => {
    if (!data || (data.session_id && data.session_id !== sessionRef.current?.session_id)) return;
    setIntegrity(data);
    if (Object.keys(data.losses || {}).length && phaseRef.current === "active") {
      const message = Object.values(data.losses)[0].message;
      notify(`${message} The interruption is recorded for your final monitoring report.`, "interruption", "monitoring");
    }
  }, [notify]);
  const reportMonitoring = useCallback(async (interruption) => {
    if (phaseRef.current !== "active") return;
    const tracks = streamRef.current?.getTracks() || [];
    const data = await request(`/interviews/${sessionRef.current.session_id}/monitoring`, { method: "POST", body: JSON.stringify({
      visible: !document.hidden, focused: document.hasFocus(), secure_view: !!window.electronAPI || !!document.fullscreenElement,
      devices_ready: tracks.some(track => track.kind === "video" && track.readyState === "live" && !track.muted)
        && tracks.some(track => track.kind === "audio" && track.readyState === "live" && !track.muted), interruption }) }, 8000);
    applyIntegrity(data.integrity); return data;
  }, [request, applyIntegrity]);
  actionsRef.current.reportMonitoring = reportMonitoring;

  // Existing sessions are resumed from the server, never charged by another /start.
  useEffect(() => {
    if (initializationRef.current) return; initializationRef.current = true;
    async function initialize() {
      try {
        const existing = sessionRef.current; let data;
        if (existing?.session_id || (interviewId && interviewId !== "start")) data = await request(`/interviews/${existing?.session_id || interviewId}/session`);
        else {
          if (!location.state?.applicationId) throw new Error("Open this interview from your applications page so we can load the correct role.");
          try { data = await request("/interviews/start", { method: "POST", body: JSON.stringify({ application_id: location.state.applicationId }) }, 25000); }
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
        if (merged.integrity) setIntegrity(merged.integrity);
        setTurns(merged.transcript || []);
        if (terminalPhase(merged)) { setResult(merged); setPhase(terminalPhase(merged)); }
        else if (merged.interview_complete) actionsRef.current.finish();
        else if (merged.engine_available === false) { setError("This session's live interviewer is unavailable. Finish with your saved answers, then return to your dashboard. Your submitted answers will be retained."); setPhase("recovery_failed"); }
        else { setFaceCaptured(!!merged.identity_captured); setPhase("devices"); }
      } catch (failure) { if (aliveRef.current) { setError(failure.message); setPhase("start_failed"); } }
    }
    initialize();
  }, [interviewId, location.state, request]);

  const prefetchedQuestionRef = useRef("");
  useEffect(() => {
    if (!session?.session_id || !question || !["devices", "face", "phone", "ready"].includes(phase) || audioCacheRef.current.has(question)) return;
    // A phase change must not launch another paid TTS request while the first
    // request is still pending. Speech is optional and never gates setup.
    if (prefetchedQuestionRef.current === question) return;
    prefetchedQuestionRef.current = question;
    request("/speech/synthesize", { method: "POST", body: JSON.stringify({ text: question, session_id: session.session_id, with_timestamps: true }) }, 12000)
      .then((data) => { if (data.audio_base64) audioCacheRef.current.set(question, data); }).catch(() => {});
  }, [session?.session_id, question, request, phase]);

  // Warm the bundled detector during laptop checks. Inference is sampled only
  // on the face step and pauses as soon as a photo is captured.
  useEffect(() => {
    if (!cameraReady) return;
    let cancelled = false, detector, timer, lastVideoTime = -1, stability, lastReset = faceResetRef.current;
    const deadline = setTimeout(() => {
      if (!detector && !cancelled) setFaceHint("Automatic capture is unavailable. You can take the photo below.");
    }, 8000);
    createFaceDetector().then((loaded) => {
      if (cancelled) { loaded.close(); return; }
      detector = loaded; clearTimeout(deadline);
      timer = setInterval(() => {
        if (lastReset !== faceResetRef.current) { stability = null; lastVideoTime = -1; lastReset = faceResetRef.current; }
        const video = videoRef.current;
        if (phaseRef.current !== "face" || facePhotoRef.current || !video?.videoWidth || video.readyState < 2) { stability = null; return; }
        if (video.currentTime === lastVideoTime) return;
        lastVideoTime = video.currentTime;
        try {
          const result = detector.detectForVideo(video, performance.now());
          const position = facePosition(result.detections, video.videoWidth, video.videoHeight);
          stability = captureProgress(stability, position, performance.now());
          setFaceHint(position.message); setFaceProgress(stability.progress);
          if (stability.captured) {
            const photo = faceSnapshot(video); facePhotoRef.current = photo; setFacePhoto(photo); setError("");
          }
        } catch {
          clearInterval(timer); setFaceHint("Automatic capture is unavailable. You can take the photo below.");
        }
      }, 250);
    }).catch(() => { if (!cancelled) { clearTimeout(deadline); setFaceHint("Automatic capture is unavailable. You can take the photo below."); } });
    return () => { cancelled = true; clearTimeout(deadline); clearInterval(timer); detector?.close(); };
  }, [cameraReady]);

  const enableDevices = useCallback(async () => {
    if (deviceRequestRef.current) return; deviceRequestRef.current = true;
    setBusy(true); setDeviceError(""); setMicReady(false); setCameraReady(false);
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("Use the GenHire kiosk browser or a current Chrome, Edge or Safari browser with HTTPS camera access.");
      streamRef.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15 } }, audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (!aliveRef.current) { stream.getTracks().forEach((track) => track.stop()); return; }
      streamRef.current = stream; if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
      setCameraReady(stream.getVideoTracks().some((track) => track.readyState === "live" && !track.muted) && !!videoRef.current?.videoWidth);
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) throw new Error("Your browser cannot test the microphone. Open the GenHire kiosk browser.");
      await contextRef.current?.close().catch(() => {}); const context = new AudioContextClass();
      // A browser can suspend audio until a click. Do not leave setup busy while
      // waiting for that gesture; the microphone check offers an explicit retry.
      context.resume().catch(() => {});
      const analyser = context.createAnalyser(); analyser.fftSize = 1024; context.createMediaStreamSource(stream).connect(analyser);
      contextRef.current = context; analyserRef.current = analyser; voiceAudioRef.current.microphone = analyser;
      stream.getTracks().forEach((track) => { track.onended = track.onmute = () => {
        if (phaseRef.current === "active") { setCameraReady(false); setMicReady(false); actionsRef.current.reportMonitoring("device_lost").catch(() => {}); actionsRef.current.pause("Your camera or microphone stopped. Reconnect your devices to continue."); }
        else { setCameraReady(false); setMicReady(false); setDeviceError("A device was disconnected. Enable your camera and microphone again."); }
      }; });
    } catch (failure) {
      const messages = { NotAllowedError: "Camera or microphone permission was denied. Allow both in your browser settings, then retry.", NotFoundError: "We could not find a camera and microphone. Connect them and retry.", NotReadableError: "Another app may be using your devices. Close it and retry." };
      setDeviceError(messages[failure.name] || failure.message);
    } finally { deviceRequestRef.current = false; if (aliveRef.current) setBusy(false); }
  }, []);
  useEffect(() => {
    if (phase !== "devices" || permissionAttemptedRef.current) return;
    permissionAttemptedRef.current = true;
    enableDevices();
  }, [phase, enableDevices]);
  // One stream/analyser covers setup, voice activity and archival video.
  useEffect(() => {
    const samples = new Uint8Array(1024);
    const timer = setInterval(() => {
      if (!analyserRef.current) return; analyserRef.current.getByteTimeDomainData(samples);
      const level = microphoneLevel(samples); setMicLevel(level);
      if (level >= 4) setMicReady(true);
      if (["devices", "face", "phone", "ready"].includes(phaseRef.current)) {
        setupLevelsRef.current.push(level); if (setupLevelsRef.current.length > 60) setupLevelsRef.current.shift();
      }
      if (phaseRef.current !== "active" || pauseRef.current || processingRef.current || answerRecorderRef.current?.state !== "recording") return;
      const activity = voiceTurnRef.current?.sample(level, Date.now());
      if (!activity) return;
      spokeRef.current = activity.spoke; setHasSpoken(activity.spoke); setAnswerCountdown(activity.remaining);
      if (activity.submit) submitRecordingRef.current?.(activity.skip);
    }, 120); return () => clearInterval(timer);
  }, []);
  const testSpeaker = async () => {
    setDeviceError(""); setSpeakerTested(false);
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext; const context = contextRef.current || new AudioContextClass(); await context.resume();
      const oscillator = context.createOscillator(); const gain = context.createGain(); oscillator.connect(gain); gain.connect(context.destination); oscillator.frequency.value = 660;
      gain.gain.setValueAtTime(0.12, context.currentTime); gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.7); oscillator.start(); oscillator.stop(context.currentTime + 0.7);
      if (!contextRef.current) oscillator.onended = () => context.close(); setSpeakerTested("played");
    } catch { setDeviceError("We could not play the test sound. Check your output device and volume, then retry."); }
  };
  const continueSetup = () => {
    if (!cameraReady || !micReady || busy) return;
    setShowSpeakerCheck(false); setError("");
    setPhase(faceCaptured ? dualRequired ? "phone" : "ready" : "face");
  };
  const continueDevices = () => {
    if (!cameraReady || !micReady || busy) return;
    if (speakerTested === true) continueSetup();
    else { setShowSpeakerCheck(true); testSpeaker(); }
  };

  useEffect(() => {
    if (!session?.session_id) return;
    const socket = io(socketUrl, { auth: { token: getToken() }, transports: ["websocket", "polling"], tryAllTransports: true, reconnection: true, timeout: 8000 }); socketRef.current = socket;
    const onPhone = (data) => { setPhone((previous) => ({ ...previous, ...data, receivedAt: Date.now(), ready: data.ready === true }));
      if (data.ready === false && phaseRef.current === "active" && sessionRef.current?.dual_proctoring_required) notify("Your phone camera is unavailable. Keep its companion page visible; the coverage gap is recorded.", "mobile_unavailable", "phone"); };
    socket.on("connect", () => {
      socketAcknowledgement(socket, "join_interview_session", { session_id: session.session_id }).then(() => {
        if (!aliveRef.current || socketRef.current !== socket) return; setConnected(true); liveCaptionsRef.current?.reconnect();
      }).catch((failure) => { setConnected(false); notify(failure.message); });
    });
    socket.on("disconnect", () => { setConnected(false); if (phaseRef.current === "active") notify("Monitoring is reconnecting. Your spoken answer is still being recorded.", "connection", "laptop"); });
    socket.on("connect_error", () => setConnected(false)); socket.on("mobile_connected", onPhone); socket.on("mobile_status_dashboard", onPhone);
    socket.on("interview_integrity", applyIntegrity);
    socket.on("mobile_disconnected", () => { setPhone({ ready: false, status: "disconnected" }); if (phaseRef.current === "active" && sessionRef.current?.dual_proctoring_required) notify("Your phone camera disconnected. Reopen its companion page; this gap is recorded.", "mobile_unavailable", "phone"); });
    socket.on("proctoring_status", setProctoring); socket.on("proctoring_alert", (data) => { if (data.session_id && data.session_id !== session.session_id) return; const message = data.message || data.status; if (message && message !== "Status: OK") notify(message, data.type || "proctoring", data.source || "laptop"); });
    const canvas = document.createElement("canvas"); canvas.width = 640; canvas.height = 480;
    const frames = setInterval(() => { if (phaseRef.current !== "active" || !socket.connected || !videoRef.current || videoRef.current.readyState < 2) return;
      canvas.getContext("2d").drawImage(videoRef.current, 0, 0, 640, 480); socket.emit("proctoring_frame", { session_id: session.session_id, image: canvas.toDataURL("image/jpeg", 0.55) }); }, 1250);
    return () => { clearInterval(frames); socket.disconnect(); if (socketRef.current === socket) socketRef.current = null; };
    // UI phases must not reconnect the socket or interrupt the phone.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.session_id, notify, socketUrl]);

  const stopAnswer = useCallback(async () => {
    captionGenerationRef.current += 1; liveCaptionsRef.current?.cancel(); liveCaptionsRef.current = null;
    const recorder = answerRecorderRef.current; if (!recorder || recorder.state === "inactive") return null;
    return new Promise((resolve) => { recorder.onstop = () => { const blob = new Blob(answerChunksRef.current, { type: recorder.mimeType }); answerChunksRef.current = []; answerRecorderRef.current = null; resolve(blob); }; recorder.stop(); });
  }, []);
  const beginListening = useCallback(() => {
    if (phaseRef.current !== "active" || pauseRef.current || processingRef.current || !streamRef.current || answerRecorderRef.current?.state === "recording") return;
    try { const stream = new MediaStream(streamRef.current.getAudioTracks()); const mimeType = mediaMimeType("audio"); const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
      recordedAnswerRef.current = null; setAudioRetryAvailable(false); answerChunksRef.current = []; recorder.ondataavailable = (event) => { if (event.data.size) answerChunksRef.current.push(event.data); }; answerRecorderRef.current = recorder;
      const levels = [...setupLevelsRef.current].sort((a, b) => a - b);
      voiceTurnRef.current = createVoiceTurn(sessionRef.current?.voice_policy, Date.now(), levels[Math.floor(levels.length * .2)] || 0);
      // Every question, including number ten, gets a fresh answer window only
      // after its audio ends. Server generation/transport time is not answer time.
      setQuestionDeadline(Date.now() / 1000 + voicePolicy(sessionRef.current?.voice_policy).max_answer_seconds);
      spokeRef.current = false; setHasSpoken(false); setAnswerCountdown(voicePolicy(sessionRef.current?.voice_policy).initial_wait_seconds); recorder.start(1000); setSpeechState("listening"); setDraft(""); setCaptionNote("");
      const generation = ++captionGenerationRef.current;
      startLiveCaptions(contextRef.current, streamRef.current, socketRef.current, sessionRef.current.session_id,
        text => { if (aliveRef.current && generation === captionGenerationRef.current) {
          setDraft(text); voiceTurnRef.current?.observeTranscript(text, Date.now());
        } },
        note => { if (aliveRef.current && generation === captionGenerationRef.current) setCaptionNote(note); })
        .then(controller => { if (generation !== captionGenerationRef.current || !aliveRef.current) controller?.cancel(); else liveCaptionsRef.current = controller; });
    } catch (failure) { setError(`Could not record your answer: ${failure.message}. Reconnect your microphone, then choose Record answer again.`); setSpeechState("idle"); }
  }, []);
  const speak = useCallback(async (text) => {
    stopPlayback(); const requestId = speechRequestRef.current;
    setSpeechState("thinking"); setSpeechError(""); setAiCaption(""); setCaptionNote("");
    let data = audioCacheRef.current.get(text);
    if (!data) {
      try {
        data = await request("/speech/synthesize", { method: "POST", body: JSON.stringify({ text, session_id: sessionRef.current.session_id, with_timestamps: true }) }, 12000);
        if (data.audio_base64) audioCacheRef.current.set(text, data);
      } catch { /* Use the device voice, then surface a persistent retry if both fail. */ }
    }
    if (requestId !== speechRequestRef.current || phaseRef.current !== "active" || pauseRef.current) return;
    playbackRef.current = playInterviewerSpeech({ text, data, context: contextRef.current,
      onPlaying: () => setSpeechState("speaking"), onCaption: setAiCaption,
      onAnalyser: analyser => { voiceAudioRef.current.speaker = analyser; },
      onDone: () => { if (requestId === speechRequestRef.current && phaseRef.current === "active") beginListening(); },
      onError: message => { setSpeechError(message); setAiCaption(text); setSpeechState("idle"); },
    });
  }, [beginListening, request, stopPlayback]);
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
  const captureFace = () => {
    if (busy || !deviceReady) return;
    try { const photo = faceSnapshot(videoRef.current); facePhotoRef.current = photo; setFacePhoto(photo); setError(""); }
    catch (failure) { setError(failure.message); }
  };
  const retakeFace = () => {
    if (busy) return;
    faceResetRef.current += 1;
    facePhotoRef.current = ""; setFacePhoto(""); setFaceCaptured(false); setFaceProgress(0); setError("");
    setFaceHint("Center your face in the guide.");
  };
  const confirmFace = async () => {
    if (busy || !deviceReady || !facePhoto) return;
    setBusy(true); setError("");
    try {
      await request(`/interviews/${session.session_id}/register-face`, { method: "POST", body: JSON.stringify({ image: facePhoto }) }, 10000);
      setFaceCaptured(true); setPhase(dualRequired ? "phone" : "ready");
    } catch (failure) { setError(failure.name === "AbortError" || failure.code === "request_timeout" ? "Saving your photo took too long. Keep this photo and retry, or retake it." : failure.message); } finally { setBusy(false); }
  };
  const activate = async () => {
    if (busy || !deviceReady || !faceCaptured || !rulesAccepted || !connected || (dualRequired && !phone.ready)) return; setBusy(true); setError("");
    try { if (!document.fullscreenElement && !window.electronAPI) {
      if (!document.documentElement.requestFullscreen) throw new Error("Open this interview in the GenHire kiosk browser to keep monitoring active.");
      await document.documentElement.requestFullscreen();
    }
      const data = await request(`/interviews/${session.session_id}/activate`, { method: "POST", body: JSON.stringify({ camera_ready: cameraReady, microphone_ready: micReady, speaker_ready: speakerTested === true }) });
      await socketAcknowledgement(socketRef.current, "start_proctoring", { session_id: session.session_id });
      if (dualRequired && phone.ready) await socketAcknowledgement(socketRef.current, "control_mobile_recording", { session_id: session.session_id, action: "start" });
      if (data.current_question || data.first_question) { setQuestion(data.current_question || data.first_question); questionRef.current = data.current_question || data.first_question; }
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
    if (["ending", "completed", "discarded", "terminated"].includes(phaseRef.current)) return; processingRef.current = true; phaseRef.current = "ending"; setPhase("ending"); setPauseReason(""); pauseRef.current = ""; setShowEndConfirm(false); setError(""); stopPlayback(); await stopAnswer();
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
    try { const practice = isPracticeSession(location, sessionRef.current); const data = await request(`/${practice ? "practice" : "interviews"}/${sessionRef.current.session_id}/end`, { method: "POST", body: JSON.stringify({}) }, 15000);
      let report = data; const deadline = Date.now() + 120000;
      while (report.report_pending && aliveRef.current && Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        report = await request(`/${practice ? "practice" : "interviews"}/${sessionRef.current.session_id}/end`, { method: "POST", body: JSON.stringify({}) }, 15000);
      }
      if (report.report_pending) throw new Error("Your answers are saved. The report is still processing; retry to check its progress.");
      setResult(report); const nextPhase = terminalPhase(report) || "completed"; phaseRef.current = nextPhase; setPhase(nextPhase);
      try { sessionStorage.removeItem(CACHE_KEY); sessionStorage.setItem("credits-needs-refresh", "true"); } catch { /* results are persisted on the server */ }
    } catch (failure) { setError(failure.message); setPhase("end_failed"); }
    finally { processingRef.current = false; socketRef.current?.disconnect(); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); }
  }, [location, request, stopAnswer, stopPlayback, uploadArchive]);
  actionsRef.current.finish = finish;
  const submitAnswer = useCallback(async (answer) => {
    if (phaseRef.current !== "active" || submitRequestRef.current) return;
    if (pauseRef.current) { setPendingAnswer({ answer, question: questionRef.current }); setSpeechState("idle"); processingRef.current = false; return; }
    const submittedQuestion = questionRef.current; submitRequestRef.current = true; processingRef.current = true; setSpeechState("thinking"); setError("");
    try { const practice = isPracticeSession(location, sessionRef.current); const data = await request(`/${practice ? "practice" : "interviews"}/${sessionRef.current.session_id}/answer`, { method: "POST", body: JSON.stringify({ question: submittedQuestion, answer }) }, 25000);
      if (phaseRef.current !== "active") return;
      // A deliberate repeat is not an answered question in the transcript.
      if (!data.repeated_question) setTurns(previous => [...previous, { role: "assistant", text: submittedQuestion }, { role: "user", text: answer }]);
      setPendingAnswer(null); setDraft(""); recordedAnswerRef.current = null; setAudioRetryAvailable(false); if (data.interview_complete) { processingRef.current = false; await finish(); return; }
      if (!data.next_question) throw new Error("The next question is unavailable. Please retry your saved answer."); setQuestion(data.next_question); questionRef.current = data.next_question;
      setQuestionDeadline(data.question_deadline ?? null);
      setQuestionCount((count) => data.progress?.questions_asked != null ? data.progress.questions_asked + 1 : data.repeated_question ? count : count + 1); processingRef.current = false;
      speak(data.next_question);
    } catch (failure) {
      if (phaseRef.current !== "active") return;
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
    try { const blob = retry ? recordedAnswerRef.current : await stopAnswer(); if (skip) { await submitAnswer(""); return; } if (!blob?.size) throw new Error("No answer was recorded. Record your answer again.");
      recordedAnswerRef.current = blob;
      const audio = await transcriptionAudio(blob, streamRef.current); const data = await request("/speech/transcribe", { method: "POST", body: JSON.stringify({ ...audio, session_id: sessionRef.current.session_id }) }, 35000);
      const answer = data.transcript?.trim(); setDraft(answer || ""); if (!answer) throw new Error("We could not hear your answer clearly. Check your microphone and record your answer again."); await submitAnswer(answer);
    } catch (failure) { processingRef.current = false; setAudioRetryAvailable(!!recordedAnswerRef.current?.size); setError(failure.message); setSpeechState("idle"); }
  }, [request, stopAnswer, submitAnswer]);
  submitRecordingRef.current = submitRecording;
  const pause = useCallback(async (reason) => {
    if (pauseRef.current || phaseRef.current !== "active") return; pauseRef.current = reason; setPauseReason(reason);
    stopPlayback(); const blob = await stopAnswer();
    if (blob?.size && spokeRef.current) actionsRef.current.interruptedAudio = blob; setSpeechState("idle");
  }, [stopAnswer, stopPlayback]);
  actionsRef.current.pause = pause;
  const resume = async () => {
    if (!connected || busy) return;
    if (!streamRef.current?.getTracks().every((track) => track.readyState === "live")) { await enableDevices(); return; }
    if (!deviceReady) { setDeviceError("Say a short sentence so we can check your microphone again."); return; }
    setBusy(true);
    try {
      if (!document.fullscreenElement && !window.electronAPI) await document.documentElement.requestFullscreen();
      await reportMonitoring();
      await request(`/interviews/${session.session_id}/activate`, { method: "POST", body: JSON.stringify({ camera_ready: cameraReady, microphone_ready: micReady, speaker_ready: speakerTested === true }) });
      await socketAcknowledgement(socketRef.current, "start_proctoring", { session_id: session.session_id });
      if (dualRequired && phone.ready) await socketAcknowledgement(socketRef.current, "control_mobile_recording", { session_id: session.session_id, action: "start" });
      startArchive();
    } catch (failure) { setDeviceError(failure.message); setBusy(false); return; }
    setBusy(false); setPauseReason(""); pauseRef.current = ""; setError("");
    if (actionsRef.current.interruptedAudio) {
      setSpeechState("transcribing"); processingRef.current = true;
      try { const audio = await transcriptionAudio(actionsRef.current.interruptedAudio, streamRef.current); const data = await request("/speech/transcribe", { method: "POST", body: JSON.stringify({ ...audio, session_id: session.session_id }) }, 35000);
        setDraft(data.transcript || ""); setPendingAnswer({ answer: data.transcript || "", question: questionRef.current }); actionsRef.current.interruptedAudio = null; setError("Your interrupted spoken answer is restored. Send the saved answer or record again.");
      } catch (failure) { setError(failure.message); } finally { processingRef.current = false; setSpeechState("idle"); }
    } else if (pendingAnswer !== null || draftRef.current.trim()) setSpeechState("idle"); else speak(questionRef.current);
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
    const violation = (type) => { reportMonitoring(type).catch(() => {}); notify("Keep your interview window visible. This interruption is recorded for the final report.", type); };
    const visibility = () => { if (document.hidden) violation("tab_switch"); else reportMonitoring().catch(() => {}); }; const fullscreen = () => { if (!document.fullscreenElement && !window.electronAPI) violation("fullscreen_exit"); };
    const offline = () => notify("You are offline. Your recording continues; reconnect before sending your answer.", "connection");
    const blur = () => violation("window_blur");
    const focus = () => reportMonitoring().catch(() => {});
    window.electronAPI?.onAppSwitched(blur);
    const monitoring = setInterval(() => reportMonitoring().catch(() => notify("Monitoring updates are reconnecting. Your recording continues.", "connection")), 5000);
    reportMonitoring().catch(() => {});
    document.addEventListener("visibilitychange", visibility); document.addEventListener("fullscreenchange", fullscreen); window.addEventListener("offline", offline);
    window.addEventListener("blur", blur);
    window.addEventListener("focus", focus);
    return () => { clearInterval(tick); clearInterval(monitoring); document.removeEventListener("visibilitychange", visibility); document.removeEventListener("fullscreenchange", fullscreen); window.removeEventListener("offline", offline); window.removeEventListener("blur", blur); window.removeEventListener("focus", focus); };
  }, [phase, reportMonitoring, notify]);
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
      if (phaseRef.current === "active") notify("Your phone camera stopped sending frames. Reopen its page to restore coverage.", "mobile_unavailable", "phone");
      return { ...previous, ready: false, status: "disconnected" };
    }), 1000);
    return () => clearInterval(timer);
  }, [dualRequired, notify]);
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
    aliveRef.current = false; captionGenerationRef.current += 1; liveCaptionsRef.current?.cancel(); stopPlayback(); socketRef.current?.disconnect();
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
    <GenHireBrand label="Interview" />{["loading", "ending"].includes(phase) && <div className={styles.spinner} />}
    <h1>{phase === "loading" ? "Preparing your interview" : phase === "ending" ? "Your answers are saved" : phase === "end_failed" ? "Complete your report" : phase === "recovery_failed" ? "Recover your saved answers" : "Unable to open the interview"}</h1>
    <p>{phase === "loading" ? "Loading your role and question. Device checks come next." : phase === "ending" ? "Generating your evaluation. Your recording uploads separately." : "Retry to continue with the same session."}</p>{renderError(error)}
    {["end_failed", "recovery_failed"].includes(phase) && <button className={styles.primary} onClick={finish}>{phase === "recovery_failed" ? "Finish with saved answers" : "Retry report generation"}</button>}{phase === "start_failed" && <button className={styles.primary} onClick={() => window.location.reload()}>Retry</button>}
    <button className={styles.textButton} disabled={uploadStatus === "uploading"} onClick={back}>Back to {isPractice ? "practice" : "applications"}</button>
  {leaveConfirm}</div></main>;
  if (["completed", "discarded", "terminated"].includes(phase)) {
    const report = { ...session, ...result, session_id: session?.session_id, cv_score: scorePercent(result?.cv_score ?? session?.cv_score ?? (session?.similarity_score == null ? null : session.similarity_score * 100)) };
    return <main className={styles.shell}><section className={styles.resultCard}><div className={styles.successIcon}><Check size={30} /></div><span className={styles.eyebrow}>{isPractice ? "Practice feedback" : "Interview complete"}</span>
      <h1>{phase === "terminated" ? "This interview attempt has ended" : phase === "discarded" ? "No answers were submitted" : "Your interview report is ready"}</h1><p>{phase === "terminated" ? result?.message || "The monitoring policy ended this attempt. You cannot repeat this interview for the same application. Submitted answers are retained for recruiter review." : phase === "discarded" ? result?.message || "This attempt was discarded. Return and start a fresh session." : "Review your performance, CV match and monitoring coverage below."}</p>
      {phase === "completed" && <><div className={styles.scoreGrid}>{[["Interview score", interviewScore(result), result?.evaluation?.pending_answers > 0], ["CV match", report.cv_score, result?.cv_score_status === "pending"], ["Proctoring score", result?.proctoring_status === "incomplete" ? null : scorePercent(result?.proctoring_score), false]].map(([label, score, pending]) => <div className={styles.scoreCard} key={label}><span>{label}</span><strong>{score == null ? pending ? "Processing" : "Unavailable" : `${score}%`}</strong>{pending && score != null && <small>Updating remaining checks</small>}</div>)}</div>
        {(result?.evaluation?.pending_answers > 0 || result?.cv_score_status === "pending") && <p className={styles.note} role="status">Some scoring checks are finishing in the background. This report refreshes automatically; you can also reopen it from your dashboard.</p>}
        {result?.proctoring_status === "incomplete" && <p className={styles.note}>Monitoring coverage was incomplete. The report explains which checks were available.</p>}<button className={styles.primary} onClick={() => setShowReport(true)}>View evaluation and transcript <ChevronRight size={18} /></button></>}
      {uploadStatus === "uploading" && <p className={styles.note} role="status">Recording upload is in progress. Keep this page open until it finishes.</p>}{uploadStatus === "success" && <p className={styles.note}>Your recording was saved.</p>}{uploadStatus === "error" && <div className={styles.error}>Your report is saved, but the recording upload failed. <button onClick={uploadArchive}>Retry upload</button></div>}
      <button className={styles.textButton} disabled={uploadStatus === "uploading"} onClick={back}>Back to {isPractice ? "practice" : "applications"}</button><InterviewReportModal apiBase={apiBase} isOpen={showReport} onClose={() => setShowReport(false)} report={report} cvScore={report.cv_score} interviewScore={interviewScore(result)} />
    {leaveConfirm}</section></main>;
  }
  if (phase !== "active") return <main className={styles.shell}><div className={styles.setupLayout}>
    <aside className={styles.setupAside}><GenHireBrand label={isPractice ? "Practice interview" : "Interview"} /><span className={styles.eyebrow}>{isPractice ? "Practice interview" : "Your next opportunity"}</span><h1>Prepare for your interview</h1><p>Check your camera, microphone and speakers, register your face, then start your interview.</p>
      <ol className={styles.steps}>{["Laptop checks", "Face registration", ...(dualRequired ? ["Connect your phone"] : []), "Start interview"].map((label, index) => { const position = !dualRequired && index === 2 ? 3 : index; return <li key={label} className={position === step ? styles.currentStep : position < step ? styles.doneStep : ""}><span>{position < step ? <Check size={16} /> : index + 1}</span>{label}</li>; })}</ol>
      <div className={styles.privacyNote}><ShieldCheck size={20} /><p>Your camera remains visible. Monitoring warnings are recorded for review; a warning alone is not a decision about your performance.</p></div>
    </aside><section className={styles.setupCard}>
      <span className={styles.eyebrow}>{phase === "devices" ? "Step 1 · Your laptop" : phase === "face" ? "Step 2 · Face registration" : phase === "phone" ? "Step 3 · Second camera" : "Ready to begin"}</span>
      <h2>{phase === "devices" ? "Check your devices" : phase === "face" ? facePhoto ? "Review your photo" : "Center your face in the preview" : phase === "phone" ? "Connect your mobile camera" : "Start your interview"}</h2>
      <p>{phase === "devices" ? "Allow camera and microphone access, speak a short sentence, then check your speakers." : phase === "face" ? facePhoto ? "Make sure your face is clear. Retake the photo if needed, then continue." : "Sit in good light with only your face visible. Hold still for a moment and we'll capture your photo automatically." : phase === "phone" ? "Your recruiter requires a second view. Scan this private QR code on your phone, enable its camera, and leave the page open." : "The interviewer asks one question at a time. Take a moment to think, answer naturally, and use Send answer whenever you're finished."}</p>
      {phase === "devices" && <><div className={styles.devicePreview}>{renderVideo()}{!cameraReady && <span className={styles.cameraPlaceholder}><Camera size={32} />Camera preview</span>}</div>
        <div className={styles.deviceRow}><Camera size={20} /><span>Camera</span><strong className={cameraReady ? styles.good : ""}>{cameraReady ? "Ready" : "Waiting for permission"}</strong></div><div className={styles.deviceRow}><Mic size={20} /><span>Microphone <span className={styles.meter}><i style={{ width: `${micLevel}%` }} /></span></span><strong className={micReady ? styles.good : ""}>{micReady ? "Sound detected" : "Say a short sentence"}</strong>{cameraReady && !micReady && !busy && <button className={styles.secondary} onClick={() => contextRef.current?.resume().catch(() => setDeviceError("Retry your microphone check."))}>Check microphone</button>}</div>
        <div className={styles.deviceRow}><Headphones size={20} /><span>Speakers</span><button className={styles.secondary} onClick={testSpeaker}><Volume2 size={15} />Play test sound</button></div>{speakerTested === "played" && <button className={styles.secondary} onClick={() => setSpeakerTested(true)}>I heard the sound <Check size={16} /></button>}{speakerTested === true && <p className={styles.good}><Check size={16} /> Speakers confirmed</p>}
        {renderError(deviceError)}<p id="device-next-step" className={styles.note} role="status">{busy ? "Allow camera and microphone access in the permission window." : !cameraReady ? "Allow both devices in the permission window. If access was blocked, retry below." : !micReady ? "Speak a short sentence. If the meter stays still, select Check microphone." : speakerTested !== true ? "Camera and microphone are ready. Continue to confirm your speakers." : "All device checks passed. Continue to the next step."}</p>
        <div className={styles.actions}>{(deviceError || cameraReady) && <button className={styles.secondary} onClick={enableDevices} disabled={busy}>{busy ? "Checking devices…" : "Retry device checks"}</button>}<button className={styles.primary} aria-describedby="device-next-step" disabled={!cameraReady || !micReady || busy} onClick={continueDevices}>Continue <ChevronRight size={17} /></button></div>
        <Modal isOpen={showSpeakerCheck} onClose={() => setShowSpeakerCheck(false)} ariaLabelledBy="speaker-check-title" contentClassName={`${styles.centerCard} ${styles.speakerDialog}`}><Headphones size={28} className={styles.good}/><h2 id="speaker-check-title">Can you hear the test sound?</h2><p>Confirm your speakers before continuing. If you cannot hear it, check your volume or select another output device, then play it again.</p>{renderError(deviceError)}<div className={styles.actions}><button className={styles.secondary} onClick={testSpeaker}><Volume2 size={16}/>Play test sound</button><button className={styles.primary} disabled={!cameraReady || !micReady || busy || (speakerTested !== "played" && speakerTested !== true)} onClick={() => { setSpeakerTested(true); continueSetup(); }}>I heard the sound <Check size={16}/></button></div><button className={styles.textButton} onClick={() => setShowSpeakerCheck(false)}>Back to device checks</button></Modal></>}
      {phase === "face" && <><div className={styles.facePreview}>{facePhoto ? <img className={styles.preview} src={facePhoto} alt="Your captured face" /> : <>{renderVideo()}<span className={`${styles.faceGuide} ${faceProgress > 0 ? styles.faceAligned : ""}`} /><div className={styles.faceStatus} role="status">{faceHint}{faceProgress > 0 && <span className={styles.faceProgress}><i style={{ width: `${faceProgress * 100}%` }} /></span>}</div></>}</div><p className={styles.note}>{isPractice ? "This capture is used only for practice monitoring." : "Your capture is compared with your uploaded identity card in the background and included in the evaluation report."}</p>{renderError(error)}<div className={styles.actions}><button className={styles.secondary} disabled={busy} onClick={() => setPhase("devices")}>Back</button>{facePhoto ? <><button className={styles.secondary} onClick={retakeFace} disabled={busy}>Retake photo</button><button className={styles.primary} onClick={confirmFace} disabled={busy || !deviceReady}>{busy ? "Saving photo…" : "Use photo and continue"}<ChevronRight size={18} /></button></> : <button className={styles.secondary} onClick={captureFace} disabled={busy || !deviceReady}>Take photo manually <Camera size={18} /></button>}</div></>}
      {phase === "phone" && <><div className={styles.phonePairing}>{phoneUrl ? <div className={styles.qr}><QRCode value={phoneUrl} size={172} /></div> : <div className={styles.error}>The private phone link is unavailable. Reload this session to refresh it.</div>}<div><Smartphone size={30} /><h3>{phone.ready ? "Phone camera is ready" : "Waiting for your phone"}</h3><p>Use the front camera. Place it beside you, aimed at you, your laptop and desk. Keep it plugged in and turn off auto-lock.</p><span className={`${styles.badge} ${phone.ready ? styles.goodBadge : ""}`}>{phone.ready ? "Camera and microphone connected" : phone.status === "connected" ? "Phone connected · enable its camera" : "Scan the QR code"}</span></div></div><p className={styles.note}>This private link grants access only to this interview's companion camera.</p><button className={styles.primary} disabled={!phone.ready} onClick={() => setPhase("ready")}>Continue <ChevronRight size={18} /></button></>}
      {phase === "ready" && <><div className={styles.readySummary}><Check size={18} /> Camera, microphone and speakers checked<br /><Check size={18} /> Face captured{dualRequired && <><br /><Check size={18} /> Second camera {phone.ready ? "ready" : "disconnected"}</>}</div><label className={styles.consent}><input type="checkbox" checked={rulesAccepted} onChange={(event) => setRulesAccepted(event.target.checked)} /><span>I'm in a quiet, well-lit place and have time to finish. I'll keep my face visible, stay in this window and use no outside help{dualRequired ? ". My phone is positioned only as the required second camera" : ""}.</span></label><p className={styles.note}>Leaving this window, stopping a camera or microphone, switching phone apps, or locking your phone counts as an interruption. Interruptions are counted by type and included in your final proctoring score. Monitoring warnings do not automatically end this interview. Camera-analysis notices are retained for human review.</p><p className={styles.note}>{maxQuestions} questions · Usually 15–20 minutes · Your answer starts after the interviewer finishes speaking.</p>
        {!connected && renderError("Connecting to interview monitoring. Check your internet connection if this takes more than a few seconds.")}{dualRequired && !phone.ready && renderError("Your phone disconnected. Reopen its companion page before starting.")}{renderError(error)}<div className={styles.actions}><button className={styles.secondary} onClick={() => setPhase(dualRequired ? "phone" : "face")}>Back</button><button className={styles.primary} onClick={activate} disabled={busy || !deviceReady || !rulesAccepted || !connected || (dualRequired && !phone.ready)}>{busy ? "Starting…" : "Start interview"}<ChevronRight size={18} /></button></div></>}
    </section></div></main>;

  return <main className={styles.interviewShell}><header className={styles.interviewHeader}><GenHireBrand label={isPractice ? "Practice interview" : "Interview"} /><span>Question {questionCount} of {maxQuestions}</span><span className={styles.elapsed}>{formatTime(elapsed)}</span></header><div className={styles.progressTrack} role="progressbar" aria-label="Interview question progress" aria-valuemin={1} aria-valuemax={maxQuestions} aria-valuenow={Math.min(questionCount, maxQuestions)}><i style={{ width: `${Math.min(100, (questionCount / maxQuestions) * 100)}%` }} /></div>
    {warning && <div className={styles.warningToast} role="status"><CircleAlert size={19} /><div><strong>{warning.title}</strong><p>{warning.message}</p>{warning.recorded && <small>Monitoring events are saved for review. Your interview continues.</small>}</div></div>}
    {session?.screening_finish_by && <p className={styles.note}>Screening must finish by {new Date(session.screening_finish_by).toLocaleString()}. The hiring window continues during a disconnect.</p>}
    <section className={styles.interviewGrid}>
      <article className={styles.conversation}>
        <div className={styles.transcriptHeader}><div className={styles.interviewerBadge}><span>A</span><div><strong>Interview conversation</strong><small>Alex / Your AI interviewer</small></div></div><span className={styles.badge}>Voice interview</span></div>
        <div className={styles.transcriptFeed} role="log" aria-label="Interview conversation" aria-live="polite" aria-relevant="additions text">
          {turns.map((turn, index) => <div key={index} className={`${styles.transcriptTurn} ${turn.role === "user" || turn.role === "candidate" ? styles.candidateTurn : ""}`}><span>{turn.role === "user" || turn.role === "candidate" ? "You" : "Alex"}</span><p>{turn.text}</p></div>)}
          <div className={styles.transcriptTurn}><span>Alex <small>{speechState === "speaking" ? "Speaking" : `Question ${questionCount}`}</small></span><h1 className={styles.liveQuestion}>{aiCaption || (speechState === "speaking" ? "Alex is speaking..." : speechState === "thinking" ? "Preparing Alex's voice..." : question)}</h1></div>
          <div className={`${styles.transcriptTurn} ${styles.candidateTurn}`}><span>You <small>{speechState === "listening" ? "Draft captions" : speechState === "transcribing" ? "Finalizing transcript" : "Spoken answer"}</small></span><p>{draft || (speechState === "listening" ? "Your words will appear here as you speak…" : speechState === "speaking" ? "Listen to the question, then answer naturally." : "Your spoken answer will appear here.")}</p>{captionNote && ["listening", "transcribing"].includes(speechState) && <small className={styles.captionNote}>{captionNote}</small>}</div>
          <div ref={transcriptTailRef} />
        </div>
        <div className={styles.voiceControls} aria-busy={["thinking","transcribing"].includes(speechState)}>
          {speechError && <div className={styles.savedAnswer} role="alert"><p>{speechError}</p><button className={styles.primary} onClick={() => speak(question)}>Play question</button><button className={styles.secondary} onClick={() => { setSpeechError(""); setAiCaption(question); beginListening(); }}>Continue with question text</button></div>}
          <div className={styles.conversationStatus} aria-live="polite">{pauseReason ? "Reconnect your microphone to continue" : speechState === "speaking" ? "Alex is speaking…" : speechState === "transcribing" ? "Finalizing your spoken answer…" : speechState === "thinking" ? "Saving your answer and preparing the next question…" : speechState === "listening" ? hasSpoken ? answerCountdown <= 5 ? `Sending in ${answerCountdown}s unless you continue speaking` : "Listening to your answer" : `Start speaking within ${answerCountdown}s` : "Ready when you are"}</div>
          {renderError(error)}
          {pendingAnswer !== null && <div className={styles.savedAnswer}><p>Your spoken answer is saved for retry.</p><button className={styles.primary} disabled={!!pauseReason || speechState === "thinking"} onClick={() => submitAnswer(pendingAnswer.answer)}>Send saved answer</button></div>}
          <div className={styles.voiceButtons}>
            <button className={styles.primary} disabled={!!pauseReason || speechState !== "listening" || !hasSpoken} onClick={() => submitRecording(false)}><Mic size={17} />Send answer</button>
            {audioRetryAvailable && <button className={styles.secondary} disabled={!!pauseReason || ["thinking", "transcribing"].includes(speechState)} onClick={() => submitRecording(false, true)}>Retry recording</button>}
            {speechState === "idle" && !pendingAnswer && !speechError && <button className={styles.secondary} disabled={!!pauseReason} onClick={beginListening}>Record answer again</button>}
            <button className={styles.secondary} disabled={!!pauseReason || hasSpoken || ["thinking", "transcribing"].includes(speechState)} onClick={async () => { await stopAnswer(); speak(question); }}>Repeat question</button>
          </div>
          <p className={styles.note}>After Alex finishes speaking, you have {timing.initial_wait_seconds} seconds to begin. Once you speak, {timing.silence_seconds} seconds of silence sends your answer automatically. You can also choose Send answer.</p>
          {questionRemaining !== null && <p className={styles.questionClock}>Question time remaining <strong>{formatTime(questionRemaining)}</strong></p>}
        </div>
      </article>
      <aside className={styles.monitorPanel}>
        <div className={styles.candidatePreview}>{!pauseReason && renderVideo()}<span>You / Laptop camera</span></div>
        <VoiceSphere state={pauseReason ? "interrupted" : speechState === "speaking" ? "speaking" : speechState === "listening" ? "listening" : ["thinking", "transcribing"].includes(speechState) ? "processing" : "idle"} audioRef={voiceAudioRef} caption={pauseReason ? "Your recording is preserved while you reconnect." : undefined} />
        <h3><ShieldCheck size={18} /> Interview monitoring</h3>
        <div className={styles.monitorRow}><span>Recorded interruptions</span><strong>{integrity.count}</strong></div>
        {!!Object.keys(integrity.counts_by_type || {}).length && <details className={styles.interruptionDetails}><summary>View interruption types</summary>{Object.entries(integrity.counts_by_type).map(([type, count]) => <div key={type}><span>{type.replaceAll("_", " ")}</span><strong>{count}</strong></div>)}</details>}
        <div className={styles.monitorRow}><span>Laptop camera</span><strong className={cameraReady ? styles.good : ""}>{cameraReady ? "Connected" : "Reconnect"}</strong></div>
        <div className={styles.monitorRow}><span>Microphone</span><span className={styles.meter}><i style={{ width: `${micLevel}%` }} /></span></div>
        {dualRequired && <div className={styles.monitorRow}><span>Phone camera</span><strong className={phone.ready ? styles.good : ""}>{phone.ready ? "Connected" : "Reconnect"}</strong></div>}
        <div className={styles.monitorRow}><span>Monitoring connection</span><strong>{connected ? "Connected" : "Reconnecting"}</strong></div>
        <p className={styles.note}>Warnings and coverage gaps contribute to the final monitoring report. They do not automatically end the interview or establish cheating.</p>
        {dualRequired && !phone.ready && phoneUrl && <details className={styles.interruptionDetails}><summary>Reconnect phone camera</summary><p className={styles.note}>Reopen the companion page and keep the screen unlocked.</p><div className={styles.qr}><QRCode value={phoneUrl} size={128} /></div><button className={styles.textButton} onClick={refreshPhoneLink} disabled={busy}>Refresh pairing link</button></details>}
        {proctoring?.capabilities?.object_detection === false && <p className={styles.note}>Object detection is unavailable. Available camera checks and recording continue.</p>}
        <button className={styles.endButton} disabled={["transcribing", "thinking"].includes(speechState)} onClick={() => setShowEndConfirm(true)}>End interview</button>
      </aside>
    </section>
    <Modal isOpen={!!pauseReason} closeOnEsc={false} closeOnOverlayClick={false}
      overlayClassName={styles.pauseOverlay} contentClassName={`${styles.centerCard} ${styles.reconnectCard}`} ariaLabelledBy="reconnect-title">
      <CircleAlert size={30} /><h2 id="reconnect-title">Reconnect your devices</h2><p>{pauseReason}</p>
      <p className={styles.note}>Submitted answers are saved. Your interrupted recording stays on this device. Monitoring gaps are counted by type and included in the final proctoring report; they do not automatically end this interview. The question time limit continues during reconnection.</p>
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
      <button className={styles.primary} onClick={resume} disabled={!connected || !deviceReady || busy}>{busy ? "Checking devices..." : "Resume interview"}</button>
      <button className={styles.textButton} onClick={() => setShowEndConfirm(true)}>End with saved answers</button>
    </Modal>
    <ConfirmDialog isOpen={showEndConfirm} onClose={() => setShowEndConfirm(false)} onConfirm={finish} title="Finish this interview?"
      message="Your submitted spoken answers will be evaluated. Use Send answer first to include the current recording. Finishing does not submit an unsent recording." confirmText="Finish interview" />

  </main>;
}

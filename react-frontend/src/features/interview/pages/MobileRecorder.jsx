import React, { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import io from "socket.io-client";
import { Check, CircleAlert, ShieldCheck, Smartphone } from "lucide-react";
import { API_BASE } from "shared/api/client";
import { interviewRequest, mediaMimeType, recordingPartId } from "../utils/session";
import styles from "./InterviewExperience.module.css";

export default function MobileRecorder() {
  const { sessionId } = useParams(); const location = useLocation();
  const pairingToken = new URLSearchParams(location.search).get("pairing_token") || "";
  const [status, setStatus] = useState("connecting"); const [error, setError] = useState(""); const [cameraReady, setCameraReady] = useState(false);
  const [joined, setJoined] = useState(false); const [busy, setBusy] = useState(false);
  const videoRef = useRef(null); const streamRef = useRef(null); const socketRef = useRef(null); const recorderRef = useRef(null);
  const partsRef = useRef([]); const uploadingRef = useRef(false); const joinedRef = useRef(false); const wakeLockRef = useRef(null); const aliveRef = useRef(true);
  const uploadRef = useRef(null); const statusRef = useRef(status); statusRef.current = status;
  const cameraRequestRef = useRef(false); const permissionAttemptedRef = useRef(false);
  const fullscreenWantedRef = useRef(false);
  const activeInterviewRef = useRef(false);
  const [awakeNotice, setAwakeNotice] = useState("");
  const [integrity, setIntegrity] = useState(null);

  const sendStatus = useCallback((override) => {
    if (!joinedRef.current) return;
    const stream = streamRef.current;
    const live = (kind) => !!stream?.getTracks().some((track) => track.kind === kind && track.readyState === "live" && !track.muted);
    const viewReady = !document.hidden && (!fullscreenWantedRef.current || !!document.fullscreenElement);
    socketRef.current?.emit("mobile_status_update", { session_id: sessionId, status: override || (!viewReady ? "camera_error" : recorderRef.current?.state === "recording" ? "recording" : stream ? "ready" : "connected"), camera_ready: viewReady && live("video"), microphone_ready: viewReady && live("audio"), page_visible: !document.hidden,
      facing_mode: stream?.getVideoTracks()[0]?.getSettings().facingMode || (stream ? "user" : null) });
  }, [sessionId]);
  const upload = async () => {
    if (uploadingRef.current || !partsRef.current.some((part) => !part.uploaded)) return; uploadingRef.current = true;
    setStatus("uploading"); setError("");
    try {
      for (const part of partsRef.current) {
      if (part.uploaded) continue; const blob = part.blob; const form = new FormData();
      form.append("recording", blob, `mobile-recording.${blob.type.includes("mp4") ? "mp4" : "webm"}`); form.append("pairing_token", pairingToken); form.append("recording_part", part.id);
      await interviewRequest(API_BASE, `/interviews/${sessionId}/upload-mobile-recording`, null, { method: "POST", headers: { "X-Mobile-Pairing-Token": pairingToken }, body: form }, 120000);
      part.uploaded = true; part.blob = null;
      } setStatus("uploaded"); sendStatus("uploaded");
    } catch (failure) { setStatus("upload_failed"); setError(failure.message); }
    finally { uploadingRef.current = false; }
  };
  uploadRef.current = upload;
  const startRecording = useCallback(() => {
    if (!streamRef.current || recorderRef.current?.state === "recording" || document.hidden
      || !streamRef.current.getTracks().every(track => track.readyState === "live" && !track.muted)) return;
    try {
      const mimeType = mediaMimeType("video"); const recorder = new MediaRecorder(streamRef.current, { ...(mimeType ? { mimeType } : {}), videoBitsPerSecond: 450000, audioBitsPerSecond: 24000 });
      const chunks = []; recorderRef.current = recorder;
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onerror = () => { setError("Phone recording stopped. Reconnect your camera immediately."); sendStatus("camera_error"); };
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: recorder.mimeType }); chunks.length = 0;
        if (blob.size) partsRef.current.push({ id: recordingPartId(), blob, uploaded: false });
        if (aliveRef.current && statusRef.current === "uploading") uploadRef.current();
      };
      recorder.start(2000); setStatus("recording"); sendStatus("recording");
    } catch (failure) { setError(`Recording could not start: ${failure.message}. Reconnect your camera.`); setCameraReady(false); setStatus("camera_error"); sendStatus("camera_error"); }
  }, [sendStatus]);

  useEffect(() => {
    aliveRef.current = true;
    if (!pairingToken) { setStatus("invalid"); setError("This link has no private pairing token. Scan the QR code shown on your laptop."); return; }
    const socket = io(process.env.REACT_APP_API_URL || window.location.origin, { transports: ["websocket", "polling"], tryAllTransports: true, timeout: 8000, reconnection: true }); socketRef.current = socket;
    socket.on("connect", () => {
      socket.emit("join_mobile_session", { session_id: sessionId, pairing_token: pairingToken }, (response) => {
        if (!aliveRef.current) return;
        if (!response?.ok) { setStatus("invalid"); setError(response?.error || "This pairing link is invalid or expired. Refresh the QR code on your laptop."); return; }
        joinedRef.current = true; setJoined(true); setError("");
        activeInterviewRef.current = response.session_status === "active";
        if (response.terminal || ["completed", "abandoned", "discarded"].includes(response.session_status)) {
          if (recorderRef.current?.state === "recording") { statusRef.current = "uploading"; setStatus("uploading"); recorderRef.current.stop(); }
          else if (partsRef.current.some((part) => !part.uploaded)) uploadRef.current(); else setStatus("complete");
          streamRef.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); }); setCameraReady(false); wakeLockRef.current?.release().catch(() => {}); return;
        }
        if (recorderRef.current?.state === "recording") setStatus("recording"); else setStatus(streamRef.current ? "ready" : "camera_needed");
        if (activeInterviewRef.current && streamRef.current) startRecording();
        sendStatus();
      });
    });
    socket.on("disconnect", () => { joinedRef.current = false; setJoined(false); if (!["uploaded", "complete", "uploading"].includes(statusRef.current)) setStatus("reconnecting"); });
    socket.on("connect_error", () => setStatus("reconnecting"));
    socket.on("interview_integrity", (data) => { setIntegrity(data); if (data.losses?.mobile) setError(data.losses.mobile.message); else setError(""); });
    socket.on("mobile_recording_action", (data) => {
      if (data.action === "start") { activeInterviewRef.current = true; startRecording(); }
      else if (data.action === "stop") {
        activeInterviewRef.current = false;
        if (recorderRef.current?.state === "recording") { statusRef.current = "uploading"; setStatus("uploading"); recorderRef.current.stop(); }
        else if (partsRef.current.some((part) => !part.uploaded)) uploadRef.current(); else setStatus("complete");
        streamRef.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); }); setCameraReady(false); wakeLockRef.current?.release().catch(() => {});
      }
    });
    const heartbeat = setInterval(() => { if (streamRef.current && !["uploaded", "complete", "uploading", "upload_failed"].includes(statusRef.current)) sendStatus(); }, 5000);
    const canvas = document.createElement("canvas"); canvas.width = 480; canvas.height = 360;
    // A preview frame during setup proves the camera is actually capturing.
    // The server records coverage/scoring only after interview activation.
    const frames = setInterval(() => {
      if (document.hidden || !joinedRef.current || !streamRef.current?.getVideoTracks().some((track) => track.readyState === "live" && !track.muted) || !videoRef.current || videoRef.current.readyState < 2) return;
      canvas.getContext("2d").drawImage(videoRef.current, 0, 0, 480, 360);
      socket.emit("mobile_proctoring_frame", { session_id: sessionId, image: canvas.toDataURL("image/jpeg", 0.5) });
    }, 1000);
    const visibility = async () => {
      if (document.hidden) sendStatus("camera_error");
      else if (streamRef.current) { if (activeInterviewRef.current) startRecording(); sendStatus(); try { wakeLockRef.current = await navigator.wakeLock?.request("screen"); } catch { /* power saving may block wake lock */ } }
    };
    const leaving = () => sendStatus("camera_error");
    const fullscreen = () => sendStatus();
    const preventLeave = (event) => { if (recorderRef.current?.state === "recording" || partsRef.current.some(part => !part.uploaded)) { event.preventDefault(); event.returnValue = ""; } };
    document.addEventListener("visibilitychange", visibility);
    document.addEventListener("fullscreenchange", fullscreen);
    window.addEventListener("pagehide", leaving); window.addEventListener("offline", leaving); window.addEventListener("beforeunload", preventLeave);
    return () => {
      aliveRef.current = false; clearInterval(heartbeat); clearInterval(frames); document.removeEventListener("visibilitychange", visibility);
      document.removeEventListener("fullscreenchange", fullscreen);
      window.removeEventListener("pagehide", leaving); window.removeEventListener("offline", leaving); window.removeEventListener("beforeunload", preventLeave);
      sendStatus("disconnected"); socket.disconnect(); joinedRef.current = false;
      if (recorderRef.current?.state === "recording") { recorderRef.current.onstop = null; recorderRef.current.stop(); }
      streamRef.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); }); wakeLockRef.current?.release().catch(() => {});
    };
    // Session/token scope owns the socket; UI state must not interrupt recording.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, pairingToken]);

  const enableCamera = useCallback(async () => {
    if (cameraRequestRef.current) return; cameraRequestRef.current = true; setBusy(true); setError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("Open this private link in a current Safari or Chrome browser. Camera access requires HTTPS.");
      // Finish and retain the old part before swapping tracks. Otherwise its
      // asynchronous stop can leave the replacement camera without a recorder.
      const previous = recorderRef.current;
      if (previous && previous.state !== "inactive") await new Promise((resolve, reject) => {
        const finished = () => { clearTimeout(timer); resolve(); };
        const timer = setTimeout(() => { previous.removeEventListener("stop", finished); reject(new Error("Your previous recording is still saving. Retry camera access.")); }, 3000);
        previous.addEventListener("stop", finished, { once: true });
        try { previous.stop(); } catch (failure) { clearTimeout(timer); previous.removeEventListener("stop", finished); reject(failure); }
      });
      streamRef.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { exact: "user" }, width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15 } }, audio: { echoCancellation: true, noiseSuppression: true } });
      if (!aliveRef.current) { stream.getTracks().forEach((track) => track.stop()); return; }
      streamRef.current = stream; videoRef.current.srcObject = stream; await videoRef.current.play();
      stream.getTracks().forEach((track) => { track.onended = track.onmute = () => { setCameraReady(false); setStatus("camera_error"); setError("Your camera or microphone stopped. Enable it again to continue."); sendStatus("camera_error"); }; track.onunmute = () => { setCameraReady(true); setError(""); setStatus(recorderRef.current?.state === "recording" ? "recording" : "ready"); if (activeInterviewRef.current) startRecording(); sendStatus(); }; });
      setCameraReady(true); setStatus("ready"); sendStatus("ready");
      if (activeInterviewRef.current) startRecording();
      try { wakeLockRef.current = await navigator.wakeLock?.request("screen"); if (!wakeLockRef.current) setAwakeNotice("Automatic screen wake is unavailable. Disable auto-lock in your phone settings and keep this page visible."); }
      catch { setAwakeNotice("Your phone declined automatic screen wake. Disable auto-lock and keep it connected to power."); }
    } catch (failure) { setError(failure.name === "NotAllowedError" ? "Allow camera and microphone access in your browser settings, then retry." : failure.message); }
    finally { cameraRequestRef.current = false; if (aliveRef.current) setBusy(false); }
  }, [sendStatus, startRecording]);
  useEffect(() => {
    if (!joined || status !== "camera_needed" || permissionAttemptedRef.current) return;
    permissionAttemptedRef.current = true; enableCamera();
  }, [joined, status, enableCamera]);
  const title = { connecting: "Connecting your phone", reconnecting: "Reconnecting…", camera_needed: "Enable your second camera", camera_error: "Reconnect your second camera", ready: "Your second camera is ready", recording: "Interview monitoring is active", uploading: "Saving your recording", uploaded: "Recording saved", upload_failed: "Let's save your recording", complete: "Your interview has finished", invalid: "Scan a new private QR code" }[status];
  return <main className={styles.shell}><section className={styles.centerCard} style={{ margin: "10px auto", maxWidth: 540 }}><span className={styles.brand}><ShieldCheck size={22} /> GenHire companion</span>
    <span className={styles.eyebrow}>Phone · Second camera</span><h1>{title}</h1><p>Place your phone to show you, your laptop and your desk from the side. Keep this page open, your screen unlocked and your phone connected to power.</p>
    <div className={styles.devicePreview}><video ref={videoRef} autoPlay muted playsInline className={styles.preview} aria-label="Phone front camera preview" />{!cameraReady && <span className={styles.cameraPlaceholder}><Smartphone size={30} />Front camera preview</span>}</div>
    <p className={styles.note}>Use the front camera and position the phone beside you. Leaving this page, locking the screen or losing camera access is recorded as a coverage gap in the final report. Interruptions do not automatically end the interview. Your phone browser cannot prevent app switching or manual screen lock.</p>
    {integrity && <p role="status">Recorded interruptions: {integrity.count}</p>}
    {error && <div className={styles.error} role="alert"><CircleAlert size={18} /><span>{error}</span></div>}
    {awakeNotice && <p className={styles.note}>{awakeNotice}</p>}
    {cameraReady && typeof document.documentElement.requestFullscreen === "function" && <button className={styles.secondary} onClick={async () => {
      try { await document.documentElement.requestFullscreen(); fullscreenWantedRef.current = true; sendStatus(); }
      catch { setError("Fullscreen was declined. Keep the monitoring page visible and the screen unlocked."); }
    }}>Keep monitoring fullscreen</button>}
    {busy && <p className={styles.note} role="status">Allow camera and microphone access in your browser's permission prompt.</p>}
    {!cameraReady && joined && error && !["uploaded", "complete", "uploading", "upload_failed", "invalid"].includes(status) && <button className={styles.primary} style={{ marginTop: 22 }} onClick={enableCamera} disabled={busy}>{busy ? "Opening camera…" : "Retry camera and microphone"}</button>}
    {cameraReady && <p className={styles.good} style={{ marginTop: 20 }}><Check size={18} /> Camera connected · {joined ? "Laptop connected" : "Reconnecting to laptop"}</p>}
    {status === "ready" && <p className={styles.note}>Continue on your laptop. Recording begins when your interview starts.</p>}{status === "recording" && <p className={styles.note}>Do not switch apps or lock your phone. Your laptop controls recording automatically.</p>}
    {status === "upload_failed" && <button className={styles.primary} onClick={upload}>Retry recording upload</button>}
    {["uploaded", "complete"].includes(status) && <p className={styles.note}>You can close this page now.</p>}{status === "uploading" && <p className={styles.note}>Keep this page open until your recording is saved.</p>}
  </section></main>;
}

import React, { useEffect, useState, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Styles from "./Chat.module.css";
import { FFmpeg } from "@ffmpeg/ffmpeg";
import { toBlobURL } from "@ffmpeg/util";
import io from "socket.io-client";
import Avatar from "shared/components/layout/Avatar";
import QRCode from "react-qr-code";
import { proctoringConfig } from "features/interview/config/proctoring";
import { getToken, getUser, clearSession, isLoggedIn } from "shared/utils/session";
import { API_BASE } from "shared/api/client";
import LoadingScreen, { LOADING_STEPS } from "features/interview/components/LoadingScreen";
import InterviewHeader from "features/interview/components/InterviewHeader";
import PhaseIndicator from "features/interview/components/PhaseIndicator";
import PreInterviewChecklist from "features/interview/components/PreInterviewChecklist";
import Toast from "shared/components/ui/Toast";
import ConfirmDialog from "shared/components/ui/ConfirmDialog";

// Listening pace: after the AI finishes a question the candidate has
// NO_ANSWER_TIMEOUT_SECONDS to START speaking (with a visible countdown);
// once they have spoken, POST_SPEECH_SILENCE_SECONDS of sustained silence
// auto-submits the answer. A manual "Stop & Send" is always available.
const NO_ANSWER_TIMEOUT_SECONDS = 30;
const POST_SPEECH_SILENCE_SECONDS = 10;
// Mic volume (0-255 byte-frequency average) above which we count as speech.
const SPEECH_VOLUME_THRESHOLD = 10;
// If the GazeRecorder CDN never fires a calibration callback, unstick the
// candidate after this long instead of leaving them on the calibration
// screen forever.
const CALIBRATION_WATCHDOG_MS = 45000;
// Short spoken acknowledgements between an answer and the next question so
// the hand-off doesn't feel like an abrupt topic jump.
const ACKNOWLEDGEMENTS = [
  "Alright, thank you.",
  "Got it.",
  "Okay, thanks for sharing that.",
  "Thanks.",
];

export default function Chat({ interviewId }) {
  // --- STATE MANAGEMENT ---

  const currentAudioRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const isSubmittingAnswerRef = useRef(false);
  const [chatContent, setChatContent] = useState({});
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [interviewStatus, setInterviewStatus] = useState("starting");
  const [startErrorMessage, setStartErrorMessage] = useState("");
  const [evaluation, setEvaluation] = useState(null);
  // Real proctoring score from the /end response (data.proctoring_score) —
  // null until /end resolves; "incomplete" status means neither the live
  // frame-analysis nor the GazeRecorder signal was available, so there's
  // deliberately no fabricated fallback number to show.
  const [proctoringScore, setProctoringScore] = useState(null);
  const [proctoringStatus, setProctoringStatus] = useState(null);
  const [usageDeduction, setUsageDeduction] = useState(null);
  const [similarityScore, setSimilarityScore] = useState(null);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [gazeDirection, setGazeDirection] = useState(null);
  const [gazeTimes, setGazeTimes] = useState(null);
  const [isRecordingVideo, setIsRecordingVideo] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("idle");
  const [gazeRecorderStatus, setGazeRecorderStatus] = useState("idle"); // idle | calibrating | tracking | submitted | failed
  const [calibrationProgress, setCalibrationProgress] = useState(0);
  const [proctoringAlert, setProctoringAlert] = useState({
    active: false,
    message: "",
  });
  const [warningCount, setWarningCount] = useState(0);
  const [toast, setToast] = useState(null);
  const showToast = useCallback((message, type = "error") => {
    setToast({ message, type, id: Date.now() });
  }, []);
  const [showEndInterviewConfirm, setShowEndInterviewConfirm] = useState(false);
  // Account-level identity check result from /register-face:
  // "registered_new" (first real interview — photo enrolled as the account's
  // identity) | "verified" | "unverified_system_unavailable" | others.
  const [identityStatus, setIdentityStatus] = useState(null);
  const [identityBlockMessage, setIdentityBlockMessage] = useState("");

  const [isTimerRunning, setIsTimerRunning] = useState(false);
  const [questionCount, setQuestionCount] = useState(1);
  // Question cap comes from the backend session config (single source of
  // truth); 10 is only the fallback until /start responds.
  const [maxQuestions, setMaxQuestions] = useState(10);
  // Epoch-seconds deadline (from the backend's question_timeout_seconds) after
  // which we auto-submit an empty answer so a stalled candidate doesn't hang
  // the interview forever. Absent/undefined => no server-provided deadline
  // => no server-side backstop timer runs (the 30s no-answer timer still does).
  const [questionDeadline, setQuestionDeadline] = useState(null);
  const [timeoutWarning, setTimeoutWarning] = useState(false);
  const [silenceTimer, setSilenceTimer] = useState(0); // Silence AFTER the candidate spoke
  // Countdown until the question is skipped because the candidate never
  // started answering; null when not listening or once they've spoken.
  const [noAnswerRemaining, setNoAnswerRemaining] = useState(null);
  // Whether the candidate has said anything for the current question (UI copy
  // switches from "waiting to hear you" to "recording your answer").
  const [hasSpokenThisQuestion, setHasSpokenThisQuestion] = useState(false);
  const hasSpokenRef = useRef(false);
  const listeningStartedAtRef = useRef(null);
  // If /end fails we park on an "end_failed" screen with a retry button
  // instead of silently flipping back to "active".
  const [endError, setEndError] = useState("");
  // Set when /end reports the interview was discarded (zero answers) and the
  // start-of-interview credits were refunded.
  const [discardInfo, setDiscardInfo] = useState(null);
  const silenceTimerRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const volumeDetectionIntervalRef = useRef(null);
  const lastSpeechTimeRef = useRef(Date.now());
  const [interviewElapsedTime, setInterviewElapsedTime] = useState(0); // Track total interview time
  const interviewStartTimeRef = useRef(null);
  const initialGreetingSpoken = useRef(false);
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false);
  const [loadingStepIndex, setLoadingStepIndex] = useState(0);
  const [checklistDone, setChecklistDone] = useState(false);

  // Add state for progressive text display
  const [displayedText, setDisplayedText] = useState("");
  const [fullQuestionText, setFullQuestionText] = useState("");
  const typingIntervalRef = useRef(null); // --- REFS ---

  const videoRef = useRef(null);
  const ffmpegRef = useRef(new FFmpeg());
  const stopPromiseResolver = useRef(null);
  const recordedChunksRef = useRef([]);
  // Ref mirror of warningCount so long-lived callbacks (startLiveProctoring) always
  // read the latest value without being recreated on every count change.
  const warningCountRef = useRef(0);
  const socketRef = useRef(null);
  const proctoringIntervalRef = useRef(null);
  const sessionIdRef = useRef(null);
  const proctoringCanvasRef = useRef(null);
  const interviewStartInitiated = useRef(false);
  const gazeRecorderScriptsLoadedRef = useRef(false);
  const gazeRecorderTrackingRef = useRef(false);
  const gazePointsRef = useRef([]);
  const gazeStartedAtMsRef = useRef(null);
  const gazeEndedAtMsRef = useRef(null);
  const gazeStartTimeRef = useRef(null);
  const gazeRecordingDataRef = useRef(null);
  const gazeMessageGuardHandlerRef = useRef(null);
  // Holds { text, audioSrc } when TTS is pre-fetched during registering phase
  const prefetchedTTSRef = useRef(null);

  const transcriptRef = useRef("");
  // Track the currently active MediaStream explicitly to guarantee full shutdown
  const cameraStreamRef = useRef(null);
  const pendingSubmissionRef = useRef(false);

  // --- HOOKS ---
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // GazeRecorderAPI expects event.data to be a string in message handlers.
    // Block non-string payloads once GazeRecorder scripts are loaded.
    const handleWindowMessageGuard = (event) => {
      if (!gazeRecorderScriptsLoadedRef.current) return;
      if (typeof event?.data === "string") return;
      event.stopImmediatePropagation();
    };

    gazeMessageGuardHandlerRef.current = handleWindowMessageGuard;
    window.addEventListener("message", handleWindowMessageGuard, true);

    return () => {
      if (gazeMessageGuardHandlerRef.current) {
        window.removeEventListener(
          "message",
          gazeMessageGuardHandlerRef.current,
          true,
        );
      }
    };
  }, []);

  // Keep the ref in sync so long-lived callbacks always see the current count.
  useEffect(() => {
    warningCountRef.current = warningCount;
  }, [warningCount]);

  // Ref mirrors read by long-lived callbacks (MediaRecorder.onstop, TTS audio
  // events, GazeRecorder callbacks) that would otherwise capture stale state.
  const interviewStatusRef = useRef(interviewStatus);
  useEffect(() => {
    interviewStatusRef.current = interviewStatus;
  }, [interviewStatus]);
  // onSend is recreated whenever currentQuestion changes; the MediaRecorder's
  // onstop handler is wired once per status change and previously kept the
  // FIRST onSend it saw — every later answer was submitted against question 1.
  const onSendRef = useRef(null);
  const beginListeningRef = useRef(null);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden && interviewStatus === "active") {
        const newWarningCount = warningCount + 1;
        setWarningCount(newWarningCount);
        setProctoringAlert({
          active: true,
          message: `You have switched to another tab. This is warning #${newWarningCount}. This action has been recorded.`,
        });
        if (socketRef.current) {
          socketRef.current.emit("proctoring_violation", {
            session_id: sessionIdRef.current,
            type: "visibility_change",
          });
        }
      }
    };

    const handleBlur = () => {
      if (
        interviewStatus === "active" &&
        document.hasFocus() === false &&
        !proctoringAlert.active
      ) {
        const newWarningCount = warningCount + 1;
        setWarningCount(newWarningCount);
        setProctoringAlert({
          active: true,
          message: `You have switched to another window. This is warning #${newWarningCount}. This action has been recorded.`,
        });
        if (socketRef.current) {
          socketRef.current.emit("proctoring_violation", {
            session_id: sessionIdRef.current,
            type: "window_blur",
          });
        }
      }
    };

    if (interviewStatus === "active") {
      document.addEventListener("visibilitychange", handleVisibilityChange);
      window.addEventListener("blur", handleBlur);
    }

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleBlur);
    };
  }, [interviewStatus, proctoringAlert.active, warningCount]);

  const loadScript = useCallback((src) => {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[src="${src}"]`);
      if (existing) {
        if (existing.dataset.loaded === "true") {
          resolve();
          return;
        }
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener(
          "error",
          () => reject(new Error(`Failed to load ${src}`)),
          { once: true },
        );
        return;
      }
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.onload = () => {
        script.dataset.loaded = "true";
        resolve();
      };
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.body.appendChild(script);
    });
  }, []);

  // Pre-load all GazeRecorder CDN scripts as soon as the component mounts so
  // they are already in the DOM by the time the user clicks "Register Face".
  // Previously these were loaded inside the button handler, adding ~1-2s of
  // CDN latency right before calibration started.
  useEffect(() => {
    const preloadGazeScripts = async () => {
      try {
        await loadScript("https://app.gazerecorder.com/GazeCloudAPI.js");
        await loadScript("https://app.gazerecorder.com/GazeRecorderAPI.js");
        await loadScript("https://app.gazerecorder.com/GazePlayer.js");
        gazeRecorderScriptsLoadedRef.current = true;
      } catch (e) {
        // Non-fatal — startInlineGazeRecorder will fall back gracefully
        console.warn("GazeRecorder script preload failed:", e.message);
      }
    };
    preloadGazeScripts();
  }, [loadScript]);

  // Cycle the loading-step messages every 800 ms while the interview session
  // is being created on the backend.  Gives users a sense of forward progress
  // instead of a static spinner.
  useEffect(() => {
    if (interviewStatus !== "starting") return;
    const id = setInterval(() => {
      setLoadingStepIndex((i) => Math.min(i + 1, LOADING_STEPS.length - 1));
    }, 800);
    return () => {
      clearInterval(id);
      setLoadingStepIndex(0); // reset for next time
    };
  }, [interviewStatus]);

  const calibrationWatchdogRef = useRef(null);

  const startInlineGazeRecorder = useCallback(async () => {
    if (gazeRecorderTrackingRef.current) return;
    try {
      setGazeRecorderStatus("calibrating");
      if (!window.__gazeRecorderMessageGuardInstalled) {
        const messageGuard = (event) => {
          if (typeof event.data !== "string") {
            event.stopImmediatePropagation();
          }
        };

        window.addEventListener("message", messageGuard, true);
        window.__gazeRecorderMessageGuardInstalled = true;
      }

      if (!gazeRecorderScriptsLoadedRef.current) {
        await loadScript("https://app.gazerecorder.com/GazeCloudAPI.js");
        await loadScript("https://app.gazerecorder.com/GazeRecorderAPI.js");
        await loadScript("https://app.gazerecorder.com/GazePlayer.js");
        gazeRecorderScriptsLoadedRef.current = true;
      }

      if (!window.GazeCloudAPI || !window.GazeRecorderAPI) {
        throw new Error("GazeRecorder scripts not available.");
      }

      gazePointsRef.current = [];
      gazeRecordingDataRef.current = null;
      gazeStartedAtMsRef.current = Date.now();
      gazeEndedAtMsRef.current = null;
      gazeStartTimeRef.current = Date.now();

      // Disable click-based recalibration to prevent demo-timeout recalibration overlays
      window.GazeCloudAPI.UseClickRecalibration = false;

      window.GazeCloudAPI.OnResult = function (gazeData) {
        if (!gazeRecorderTrackingRef.current) return;
        gazePointsRef.current.push({
          timestamp: (Date.now() - gazeStartTimeRef.current) / 1000,
          x: gazeData?.docX || 0,
          y: gazeData?.docY || 0,
        });
      };

      window.GazeCloudAPI.OnCalibrationComplete = function () {
        if (calibrationWatchdogRef.current) {
          clearTimeout(calibrationWatchdogRef.current);
          calibrationWatchdogRef.current = null;
        }
        // If interview is already active, this is a demo-timeout recalibration — ignore it
        // and gracefully degrade (interview continues without gaze tracking)
        if (gazeRecorderTrackingRef.current) {
          console.warn(
            "⚠️ GazeCloudAPI recalibration triggered (likely demo timeout). Stopping gaze tracking gracefully.",
          );
          try {
            window.GazeRecorderAPI.StopRec();
            window.GazeCloudAPI.StopEyeTracking();
          } catch (e) {
            /* already stopped */
          }
          gazeRecorderTrackingRef.current = false;
          setGazeRecorderStatus("failed");
          return;
        }

        window.GazeRecorderAPI.Rec();
        gazeRecorderTrackingRef.current = true;
        gazeStartTimeRef.current = Date.now();
        setGazeRecorderStatus("tracking");

        // Progress to ready once tracking starts. Functional update — this
        // callback is created once inside a stable useCallback, so reading
        // `interviewStatus` directly here would see the value from the first
        // render ("starting"), never match "calibrating", and leave the
        // candidate stuck on the calibration screen forever.
        setInterviewStatus((prev) =>
          prev === "calibrating" ? "ready_to_start" : prev,
        );
      };

      // Handle camera denial / errors from GazeCloudAPI
      window.GazeCloudAPI.OnCamDenied = function () {
        console.warn("⚠️ GazeCloudAPI camera access denied.");
        if (calibrationWatchdogRef.current) {
          clearTimeout(calibrationWatchdogRef.current);
          calibrationWatchdogRef.current = null;
        }
        gazeRecorderTrackingRef.current = false;
        setGazeRecorderStatus("failed");
        setInterviewStatus((prev) =>
          prev === "calibrating" ? "ready_to_start" : prev,
        ); // degrade gracefully
      };

      window.GazeCloudAPI.StartEyeTracking();

      // Watchdog: if the third-party calibration never completes (CDN down,
      // ad-blocker, service hiccup), fail gaze tracking gracefully and let
      // the interview proceed rather than stranding the candidate.
      calibrationWatchdogRef.current = setTimeout(() => {
        calibrationWatchdogRef.current = null;
        if (gazeRecorderTrackingRef.current) return;
        console.warn("⚠️ Gaze calibration timed out — continuing without eye tracking.");
        try {
          window.GazeCloudAPI.StopEyeTracking();
        } catch (e) {
          /* not started */
        }
        setGazeRecorderStatus("failed");
        setInterviewStatus((prev) =>
          prev === "calibrating" ? "ready_to_start" : prev,
        );
      }, CALIBRATION_WATCHDOG_MS);

      // Simulate calibration progress
      let p = 0;
      const progressInterval = setInterval(() => {
        p += 5;
        if (p <= 95) setCalibrationProgress(p);
        if (gazeRecorderTrackingRef.current || p >= 100) clearInterval(progressInterval);
      }, 500);

    } catch (error) {
      console.error("Failed to start inline GazeRecorder:", error);
      setGazeRecorderStatus("failed");
      setInterviewStatus((prev) =>
        prev === "calibrating" ? "ready_to_start" : prev,
      );
    }
  }, [loadScript]);

  const finalizeInlineGazeRecorder = useCallback(async () => {
    const currentSessionId = sessionIdRef.current;
    if (!currentSessionId || !gazeRecorderScriptsLoadedRef.current) return;

    try {
      if (gazeRecorderTrackingRef.current) {
        window.GazeRecorderAPI.StopRec();
        window.GazeCloudAPI.StopEyeTracking();
        gazeRecordingDataRef.current = window.GazeRecorderAPI.GetRecData();
        gazeRecorderTrackingRef.current = false;
        gazeEndedAtMsRef.current = Date.now();
      }

      if (!gazePointsRef.current.length) {
        console.warn("No GazeRecorder points captured.");
        return;
      }

      const token = getToken();
      const apiBase = (process.env.REACT_APP_API_URL || "").replace(/\/$/, "");
      const response = await fetch(
        `${apiBase}/api/interviews/${currentSessionId}/gaze-recorder-results`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            session_id: currentSessionId,
            recordingData: gazeRecordingDataRef.current,
            gazePoints: gazePointsRef.current,
            startedAtMs: gazeStartedAtMsRef.current,
            endedAtMs: gazeEndedAtMsRef.current,
            viewport: { width: window.innerWidth, height: window.innerHeight },
          }),
        },
      );

      if (!response.ok) {
        throw new Error(
          (await response.json()).error || "Failed to submit GazeRecorder data",
        );
      }

      setGazeRecorderStatus("submitted");
    } catch (error) {
      console.error("Failed to finalize inline GazeRecorder:", error);
      setGazeRecorderStatus("failed");
    }
  }, []);

  // --- LIVE PROCTORING & WEBSOCKETS ---

  const startLiveProctoring = useCallback(() => {
    const currentSessionId = sessionIdRef.current;
    if (!currentSessionId || (socketRef.current && socketRef.current.connected))
      return;

    // Authenticate the socket — the backend joins us to our user room and
    // (crucially) accepts the proctoring frame stream on this connection.
    const socket = io(process.env.REACT_APP_API_URL, {
      auth: { token: getToken() },
    });
    socketRef.current = socket;

    // Register ALL event handlers at the socket level (not inside "connect") so
    // they are not duplicated when the socket auto-reconnects.

    socket.on("gaze_data", (data) => {
      setGazeDirection(data.gaze_direction);
      setGazeTimes(data.gaze_times);
      if (data.is_cheating_alert) {
        const newCount = warningCountRef.current + 1;
        warningCountRef.current = newCount;
        setWarningCount(newCount);
        setProctoringAlert({
          active: true,
          message: `Suspicious gaze detected! This is warning #${newCount}.`,
        });
        socket.emit("proctoring_violation", {
          session_id: sessionIdRef.current,
          type: "gaze_violation",
        });
      }
    });

    // proctoring_alert comes from the backend's frame analysis (face/head-pose check)
    socket.on("proctoring_alert", (data) => {
      if (data.status && data.status !== "Status: OK") {
        const newCount = warningCountRef.current + 1;
        warningCountRef.current = newCount;
        setWarningCount(newCount);
        setProctoringAlert({
          active: true,
          message: `${data.status} — Warning #${newCount}. This has been recorded.`,
        });
      }
    });

    socket.on("connect", () => {
      console.log("✅ WebSocket connected.");
      socket.emit("start_proctoring", { session_id: currentSessionId });
      socket.emit("control_mobile_recording", {
        session_id: currentSessionId,
        action: "start",
      });

      // Send 1 frame per second — enough for face verification without flooding backend.
      proctoringIntervalRef.current = setInterval(() => {
        if (
          videoRef.current &&
          videoRef.current.srcObject &&
          videoRef.current.readyState === 4 &&
          videoRef.current.videoWidth > 0 &&
          videoRef.current.videoHeight > 0
        ) {
          if (!proctoringCanvasRef.current) {
            proctoringCanvasRef.current = document.createElement("canvas");
          }
          const canvas = proctoringCanvasRef.current;
          if (canvas.width !== videoRef.current.videoWidth) canvas.width = videoRef.current.videoWidth;
          if (canvas.height !== videoRef.current.videoHeight) canvas.height = videoRef.current.videoHeight;
          const ctx = canvas.getContext("2d", { willReadFrequently: true });
          ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
          socket.emit("proctoring_frame", {
            session_id: currentSessionId,
            image: canvas.toDataURL("image/jpeg", 0.5),
          });
        }
      }, 1000);
    });

    socket.on("disconnect", () => {
      console.log("❌ WebSocket disconnected.");
      if (proctoringIntervalRef.current) {
        clearInterval(proctoringIntervalRef.current);
        proctoringIntervalRef.current = null;
      }
    });
  }, []);

  const stopLiveProctoring = useCallback(() => {
    if (proctoringIntervalRef.current) {
      clearInterval(proctoringIntervalRef.current);
      proctoringIntervalRef.current = null;
    }
  }, []);

  // Centralized camera shutdown to ensure hardware and browser indicator turn off.
  // Defined before handleFaceRegistration, which references it.
  const stopCamera = useCallback(() => {
    try {
      // Stop via <video> element stream if present
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject;
        try {
          stream.getTracks().forEach((t) => t.stop());
        } catch (e) {
          // ignore
        }
        videoRef.current.srcObject = null;
      }

      // Stop any tracked stream not attached to the element
      if (cameraStreamRef.current) {
        try {
          cameraStreamRef.current.getTracks().forEach((t) => t.stop());
        } catch (e) {
          // ignore
        }
        cameraStreamRef.current = null;
      }

      // Fully reset the video element
      if (videoRef.current) {
        try {
          videoRef.current.pause();
        } catch (e) {}
        videoRef.current.removeAttribute("src");
        try {
          videoRef.current.load();
        } catch (e) {}
      }
    } catch (e) {
      // no-op
    }
  }, []); // --- FACE REGISTRATION ---

  const handleFaceRegistration = useCallback(async () => {
    const elem = document.documentElement;
    try {
      if (elem.requestFullscreen) {
        await elem.requestFullscreen();
      } else if (elem.webkitRequestFullscreen) {
        await elem.webkitRequestFullscreen();
      } else if (elem.msRequestFullscreen) {
        await elem.msRequestFullscreen();
      }
    } catch (err) {
      console.warn(`Fullscreen request failed: ${err.message}`);
      showToast("Please enable fullscreen mode to continue the interview.");
      return;
    }

    const currentSessionId = sessionIdRef.current;
    if (
      !videoRef.current ||
      !currentSessionId ||
      videoRef.current.readyState < 3
    ) {
      showToast("Webcam not ready or session not started.");
      return;
    }
    if (videoRef.current.videoWidth === 0 || videoRef.current.videoHeight === 0) {
      showToast("Webcam is still initializing. Please wait a moment and try again.");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const context = canvas.getContext("2d");
    context.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    const imageData = canvas.toDataURL("image/jpeg");
    try {
      const token = getToken();
      const response = await fetch(
        `${API_BASE}/interviews/${currentSessionId}/register-face`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ image: imageData }),
        },
      );
      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        // Identity permanently blocked — the captured face repeatedly failed
        // to match this account's registered identity.
        if (result.error_code === "face_mismatch_blocked") {
          setIdentityBlockMessage(
            result.error ||
              "Face verification failed repeatedly — this interview attempt has been locked.",
          );
          setInterviewStatus("identity_blocked");
          if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
          }
          stopCamera();
          return;
        }
        // Mismatch with attempts left — keep the candidate on this screen.
        if (result.error_code === "face_mismatch") {
          const attemptsNote =
            typeof result.attempts_remaining === "number"
              ? ` Attempts remaining: ${result.attempts_remaining}.`
              : "";
          showToast(
            `${result.error || "The captured face does not match the identity registered on this account."}${attemptsNote}`,
          );
          return;
        }
        // Capture-quality problems (no face / multiple faces / bad image).
        if (
          result.error_code === "no_face_detected" ||
          result.error_code === "multiple_faces_detected" ||
          result.error_code === "invalid_image"
        ) {
          showToast(result.error || "Face capture failed. Please try again.", "warning");
          return;
        }
        throw new Error(result.error || result.message || "Face registration failed.");
      }

      const identityInfo = result.identity || {};
      setIdentityStatus(identityInfo.status || null);
      if (identityInfo.status === "registered_new") {
        showToast(
          "Face registered — this photo is now your account's verified identity for future interviews.",
          "success",
        );
      } else if (identityInfo.status === "verified") {
        showToast("Identity verified ✓", "success");
      }

      console.log(
        "✅ Face registered successfully, starting live proctoring...",
      );
      setInterviewStatus("calibrating");
      await startInlineGazeRecorder();
      // Start live proctoring after face registration so we have the registered face
      startLiveProctoring();

    } catch (error) {
      console.error("Face registration error:", error);
      showToast(`Could not register face: ${error.message}.`);
    }
  }, [startInlineGazeRecorder, startLiveProctoring, showToast, stopCamera]); // --- ARCHIVAL VIDEO RECORDING & UPLOADING (No changes needed) ---

  const uploadRecording = useCallback(
    async (blob) => {
      const currentSessionId = sessionIdRef.current;
      if (!currentSessionId) throw new Error("Session ID not available.");
      setUploadStatus("uploading");
      const ffmpeg = ffmpegRef.current;
      try {
        if (!ffmpeg.loaded) {
          const baseURL = "https://unpkg.com/@ffmpeg/core@0.12.6/dist/umd";
          await ffmpeg.load({
            coreURL: await toBlobURL(
              `${baseURL}/ffmpeg-core.js`,
              "text/javascript",
            ),
            wasmURL: await toBlobURL(
              `${baseURL}/ffmpeg-core.wasm`,
              "application/wasm",
            ),
          });
        }
        await ffmpeg.writeFile(
          "input.webm",
          new Uint8Array(await blob.arrayBuffer()),
        );
        await ffmpeg.exec(["-i", "input.webm", "-c", "copy", "output.mp4"]);
        const data = await ffmpeg.readFile("output.mp4");
        const formData = new FormData();
        formData.append(
          "recording",
          new Blob([data.buffer], { type: "video/mp4" }),
          `interview_${currentSessionId}.mp4`,
        );
        const token = getToken();
        const response = await fetch(
          `${API_BASE}/interviews/${currentSessionId}/upload-recording`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
            body: formData,
          },
        );
        if (!response.ok)
          throw new Error((await response.json()).error || "Upload failed");

        // Existing proctoring upload completed; also finalize inline GazeRecorder submission.
        await finalizeInlineGazeRecorder();
        setUploadStatus("success");
      } catch (error) {
        setUploadStatus("error");
        throw error;
      }
    },
    [finalizeInlineGazeRecorder],
  );

  const stopAndUploadRecording = useCallback(() => {
    return new Promise((resolve, reject) => {
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        stopPromiseResolver.current = { resolve, reject };
        mediaRecorder.stop();
      } else {
        resolve();
      }
    });
  }, [mediaRecorder]);

  const startWebcamAndArchivalRecording = useCallback(async () => {
    try {
      // Ensure any previous stream is fully stopped before acquiring a new one
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
      // Track the active stream and attach to the element
      cameraStreamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      startLiveProctoring();
      const recorder = new MediaRecorder(stream, { mimeType: "video/webm" });
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        setIsRecordingVideo(false);
        const blob = new Blob(recordedChunksRef.current, {
          type: "video/webm",
        });
        if (blob.size > 0 && stopPromiseResolver.current) {
          try {
            await uploadRecording(blob);
            stopPromiseResolver.current.resolve();
          } catch (err) {
            stopPromiseResolver.current.reject(err);
          }
        } else if (stopPromiseResolver.current) {
          stopPromiseResolver.current.resolve();
        }
        recordedChunksRef.current = [];
      };
      recorder.start(1000);
      setMediaRecorder(recorder);
      setIsRecordingVideo(true);
    } catch (error) {
      console.error("Error accessing webcam:", error);
    }
  }, [startLiveProctoring, uploadRecording]);

  // --- INTERVIEW LIFECYCLE MANAGEMENT ---
  useEffect(() => {
    if (interviewStartInitiated.current) return;
    interviewStartInitiated.current = true;

    // Check if this is a practice mode interview
    const isPracticeMode = location.state?.isPractice || false;

    // Check if coming from "Give Interview" button (URL will be /interview/start)
    const isDirectStart = interviewId === "start";

    if ((interviewId || isDirectStart) && interviewStatus === "starting") {
      // For practice mode, if session was already created, use it directly
      if (
        isPracticeMode &&
        location.state?.sessionId &&
        location.state?.initialQuestion
      ) {
        // Session already created by Practice page
        setSessionId(location.state.sessionId);
        sessionIdRef.current = location.state.sessionId;
        setSimilarityScore(location.state.similarityScore || 0);
        setCurrentQuestion(location.state.initialQuestion);
        // Same pacing config as real interviews (passed through by Practice)
        if (location.state.questionDeadline)
          setQuestionDeadline(location.state.questionDeadline);
        if (location.state.maxQuestions)
          setMaxQuestions(location.state.maxQuestions);
        setInterviewStatus("registering");
        return;
      }

      // Get application ID from navigation state (not needed for practice mode)
      const applicationId = location.state?.applicationId;

      const token = getToken();

      // For real interviews (not practice with pre-created session)
      const endpoint = `${API_BASE}/interviews/start`;

      fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ application_id: applicationId }),
      })
        .then(async (res) => {
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            const message =
              data?.error ||
              data?.message ||
              "Could not start interview session.";
            const error = new Error(message);
            error.status = res.status;
            throw error;
          }
          return data;
        })
        .then((data) => {
          setSessionId(data.session_id);
          sessionIdRef.current = data.session_id;
          setSimilarityScore(data.similarity_score);
          setCurrentQuestion(data.initial_questions[0]);
          if (data.question_deadline) setQuestionDeadline(data.question_deadline);
          if (data.max_questions) setMaxQuestions(data.max_questions);
          setInterviewStatus("registering");
        })
        .catch((err) => {
          console.error("Error starting interview:", err);
          const message =
            err?.message || "Could not start the interview session.";
          setStartErrorMessage(message);
          setChatContent({
            0: {
              response: `⚠️ Error: ${message}`,
            },
          });
          setInterviewStatus("start_failed");
        });
    }
  }, [interviewId, interviewStatus, navigate, location.state]);

  // Pre-fetch TTS audio for the very first question as soon as the session is
  // created (status = "registering").  By the time the user finishes face
  // registration + gaze calibration and clicks "Start Interview Now", the
  // audio blob is already cached in prefetchedTTSRef and speakResponse()
  // plays it instantly instead of waiting for another round-trip.
  useEffect(() => {
    if (interviewStatus !== "registering" || !currentQuestion || !sessionIdRef.current) return;

    const textToSpeak = `Your CV has a ${Math.round((similarityScore || 0) * 100)}% match. ${currentQuestion}`;

    const prefetch = async () => {
      try {
        const apiUrl = process.env.REACT_APP_API_URL || "http://localhost:5000";
        const response = await fetch(`${apiUrl}/api/speech/synthesize`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken()}`,
          },
          body: JSON.stringify({ text: textToSpeak, session_id: sessionIdRef.current }),
        });
        if (!response.ok) return;
        const data = await response.json();
        if (data.audio_base64) {
          prefetchedTTSRef.current = {
            text: textToSpeak,
            audioSrc: `data:audio/mp3;base64,${data.audio_base64}`,
          };
          console.log("✅ TTS pre-fetched and cached for instant playback.");
        }
      } catch (e) {
        // Ignore — speakResponse will fall back to a live fetch
        console.warn("TTS pre-fetch failed (non-fatal):", e.message);
      }
    };

    prefetch();
  }, [currentQuestion, interviewStatus, similarityScore]);

  useEffect(() => {
    const setupWebcam = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: true,
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        cameraStreamRef.current = stream;
      } catch (err) {
        console.error("Webcam access error:", err);
        // Toast is non-blocking, unlike the native alert() this replaces, so
        // the redirect is deliberately delayed to give the candidate time to
        // actually read the message before being navigated away.
        showToast(
          "Could not access the camera. Please check your browser permissions and ensure your camera is not in use by another application. Redirecting to the dashboard.",
        );
        setTimeout(() => navigate("/profile#applications"), 3000);
      }
    };

    if (
      interviewStatus === "registering" &&
      (!videoRef.current || !videoRef.current.srcObject)
    ) {
      setupWebcam();
    }

    if (interviewStatus === "active" && !isRecordingVideo) {
      // Stop any previous preview stream from registration phase
      stopCamera();
      startWebcamAndArchivalRecording();
      // Initialize question count to 1 for the first question
      setQuestionCount(1);
      // Start interview timer
      interviewStartTimeRef.current = Date.now();
      setInterviewElapsedTime(0);
      setChatContent({
        0: {
          response: `Your CV has a ${Math.round(
            similarityScore * 100,
          )}% match.`,
        },
        1: { response: currentQuestion },
      });
    }
  }, [
    interviewStatus,
    isRecordingVideo,
    startWebcamAndArchivalRecording,
    similarityScore,
    currentQuestion,
    navigate,
    showToast,
  ]);

  const endInterview = useCallback(async () => {
    if (socketRef.current) {
      console.log("📡 Signaling mobile to STOP...");
      socketRef.current.emit("control_mobile_recording", {
        session_id: sessionIdRef.current,
        action: "stop",
      });
    }
    const currentSessionId = sessionIdRef.current;
    if (
      !currentSessionId ||
      (interviewStatus !== "active" &&
        interviewStatus !== "ending" &&
        interviewStatus !== "end_failed") || // allow retry after a failed /end
      uploadStatus === "uploading"
    )
      return;

    setEndError("");
    setInterviewStatus("ending");

    // CRITICAL: Stop timer and speech recognition IMMEDIATELY
    setIsTimerRunning(false);
    clearInterval(silenceTimerRef.current);

    // Stop speech recording
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {
        // Speech recording already stopped
      }
    }
    setIsRecording(false);

    // Stop camera and all media tracks immediately
    stopCamera();

    stopLiveProctoring();

    try {
      await stopAndUploadRecording();

      const token = getToken();
      const isPracticeMode = location.state?.isPractice || false;

      // Use different endpoint for practice mode
      const endpoint = isPracticeMode
        ? `${API_BASE}/practice/${currentSessionId}/end`
        : `${API_BASE}/interviews/${currentSessionId}/end`;

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await response.json();
      if (!response.ok)
        throw new Error(data.error || "Failed to end interview");

      if (data.status === "interview_discarded") {
        // No answers were recorded — the backend refunded the start-of-
        // interview credits and discarded the session.
        setDiscardInfo({
          isPractice: !!isPracticeMode,
          refundSuccess: !!data?.refund?.success,
          creditsRefunded: Number(data?.refund?.credits_refunded || 0),
          message: data.message || "",
        });
        sessionStorage.setItem("credits-needs-refresh", "true");
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(() => {});
        }
        setInterviewStatus("discarded");
        return;
      }

      setInterviewStatus("completed");
      setEvaluation(data.evaluation);
      setProctoringScore(
        typeof data.proctoring_score === "number" ? data.proctoring_score : null,
      );
      setProctoringStatus(data.proctoring_status || null);
      setUsageDeduction(data?.usage_deduction || null);
      console.log("✅ Interview ended successfully:", data.evaluation);

      const deduction = data?.usage_deduction || null;
      if (deduction) {
        sessionStorage.setItem("credits-needs-refresh", "true");
        sessionStorage.setItem(
          "last-usage-deduction",
          JSON.stringify({
            ...deduction,
            session_id: currentSessionId,
            is_practice: !!isPracticeMode,
            captured_at: new Date().toISOString(),
          }),
        );
      }

      // For practice mode, don't update application scores
      if (isPracticeMode) {
        setChatContent((prev) => ({
          ...prev,
          [Object.keys(prev).length]: {
            response: "Practice interview ended. Generating your feedback...",
          },
        }));

        // No need to update application or store interview-just-completed flag
        return;
      }

      // Extract and update interview score from evaluation (only for real interviews)
      let extractedScore = null;

      // Handle different evaluation data structures
      if (data.evaluation?.quantitative?.average_relevance_score) {
        extractedScore = data.evaluation.quantitative.average_relevance_score;
      } else if (data.evaluation?.quantitative_scores) {
        if (typeof data.evaluation.quantitative_scores === "number") {
          extractedScore = data.evaluation.quantitative_scores;
        } else if (typeof data.evaluation.quantitative_scores === "object") {
          extractedScore =
            data.evaluation.quantitative_scores.average ||
            data.evaluation.quantitative_scores.overall ||
            Object.values(data.evaluation.quantitative_scores)[0];
        }
      }

      if (extractedScore !== null) {
        // Convert to percentage if score is decimal (0-1 range)
        const interviewScore =
          extractedScore <= 1
            ? Math.round(extractedScore * 100)
            : Math.round(extractedScore);

        try {
          // Update the application with the actual interview score
          await fetch(
            `${API_BASE}/applications/${location.state?.applicationId}/update-score`,
            {
              method: "PUT",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({
                interview_score: interviewScore,
              }),
            },
          );
          console.log(`✅ Interview score updated: ${interviewScore}%`);
        } catch (scoreError) {
          console.error("Failed to update interview score:", scoreError);
          // Don't throw error here as interview completion is more important
        }
      } else {
        console.warn("⚠️ No interview score found in evaluation data");
      }

      setChatContent((prev) => ({
        ...prev,
        [Object.keys(prev).length]: {
          response: "Interview ended. Finalizing your report...",
        },
      }));
    } catch (error) {
      console.error("Failed to end interview:", error);
      // Don't silently flip back to "active" — the candidate already stopped;
      // park on a retry screen instead. Answers are safe server-side.
      setEndError(error.message || "Could not finalize the interview.");
      setInterviewStatus("end_failed");
    } finally {
      if (socketRef.current && socketRef.current.connected) {
        socketRef.current.disconnect();
      }
    }
  }, [
    interviewStatus,
    uploadStatus,
    stopAndUploadRecording,
    stopLiveProctoring,
  ]);

  const onSend = useCallback(
    async (userAnswer) => {
      const currentSessionId = sessionIdRef.current;
      const answer = userAnswer.trim();
      const isPracticeMode = location.state?.isPractice || false;

      if (
        !currentQuestion ||
        !currentSessionId ||
        interviewStatus !== "active" ||
        isSubmittingAnswerRef.current
      ) {
        return;
      }

      setInput("");
      setIsSubmittingAnswer(true);
      isSubmittingAnswerRef.current = true;

      try {
        const token = getToken();

        // Use different endpoint for practice mode
        const endpoint = isPracticeMode
          ? `${API_BASE}/practice/${currentSessionId}/answer`
          : `${API_BASE}/interviews/${currentSessionId}/answer`;

        const response = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ question: currentQuestion, answer: answer }),
        });
        const data = await response.json();
        if (!response.ok)
          throw new Error(data.error || "Failed to submit answer");

        // Auto-end interview after configured max questions
        if (data.interview_complete || questionCount >= maxQuestions) {
          // Reset submitting state before ending
          setIsSubmittingAnswer(false);
          isSubmittingAnswerRef.current = false;
          await endInterview();
        } else {
          // Mirror the backend's own count instead of blindly incrementing —
          // on a repeated question (data.repeated_question) the backend
          // deliberately leaves progress.questions_asked unchanged, so the
          // visible progress here correctly stays put too. +1 because the
          // backend counter only tracks dynamically-generated questions
          // (starts at 0), while this display counter also counts the
          // hardcoded greeting as "question 1". Falls back to the old
          // increment-by-1 for responses without a progress field.
          setQuestionCount((prev) =>
            data.progress?.questions_asked != null
              ? data.progress.questions_asked + 1
              : prev + 1,
          );
          if (data.question_deadline) setQuestionDeadline(data.question_deadline);
          setTimeoutWarning(false);
          setCurrentQuestion(data.next_question);

          // Speak naturally: repeat requests get the question verbatim; a
          // skipped question moves on gently; a real answer earns a brief
          // acknowledgement before the next question.
          let spokenText = data.next_question;
          if (!data.repeated_question) {
            const ack = answer
              ? ACKNOWLEDGEMENTS[
                  Math.floor(Math.random() * ACKNOWLEDGEMENTS.length)
                ]
              : "No problem, let's move on.";
            spokenText = `${ack} ${data.next_question}`;
          }
          speakResponse(spokenText);
        }
      } catch (error) {
        console.error("Error in onSend:", error);
        speakResponse(
          "Sorry, something went wrong on our side. Please answer the question again.",
        );
      } finally {
        setIsSubmittingAnswer(false);
        isSubmittingAnswerRef.current = false;
      }
    },
    [
      currentQuestion,
      interviewStatus,
      endInterview,
      questionCount,
      maxQuestions,
      location.state,
    ],
  );

  // Fresh-closure mirror for the MediaRecorder onstop handler (see onSendRef
  // declaration for why this matters).
  useEffect(() => {
    onSendRef.current = onSend;
  }, [onSend]);

  // No-response timeout: if the candidate never answers at all (distinct from
  // the in-speech silence timer below, which only fires once they've started
  // talking), auto-submit an empty answer once the backend-provided deadline
  // passes so the interview can't hang indefinitely. No-op when the backend
  // hasn't supplied a deadline (e.g. practice mode).
  useEffect(() => {
    if (interviewStatus !== "active" || !questionDeadline) {
      setTimeoutWarning(false);
      return;
    }

    const checkDeadline = () => {
      const remaining = questionDeadline - Date.now() / 1000;
      if (remaining <= 0) {
        // Never cut a candidate off mid-answer: once they've spoken, the
        // post-speech silence logic owns submission. This backstop only
        // rescues questions nobody ever started answering.
        if (hasSpokenRef.current) return;
        if (!isSubmittingAnswerRef.current) {
          onSend("");
        }
        return;
      }
      setTimeoutWarning(remaining <= 30 && !hasSpokenRef.current);
    };

    checkDeadline();
    const id = setInterval(checkDeadline, 1000);
    return () => clearInterval(id);
  }, [questionDeadline, interviewStatus, onSend]);

  // Listening pace driver. Two distinct phases per question:
  //  1. Candidate hasn't spoken yet — count down NO_ANSWER_TIMEOUT_SECONDS
  //     (they get a full 30 seconds to think), then auto-skip with an empty answer.
  //  2. Candidate has spoken — POST_SPEECH_SILENCE_SECONDS of sustained
  //     silence submits what they said. (Replaces the old 3-second cutoff
  //     that submitted an empty answer before candidates could even think.)
  useEffect(() => {
    if (interviewStatus !== "active" || !isTimerRunning) {
      clearInterval(silenceTimerRef.current);
      if (interviewStatus !== "active") {
        setSilenceTimer(0);
        setNoAnswerRemaining(null);
      }
      return () => clearInterval(silenceTimerRef.current);
    }

    silenceTimerRef.current = setInterval(() => {
      if (!hasSpokenRef.current) {
        const waited =
          (Date.now() - (listeningStartedAtRef.current || Date.now())) / 1000;
        const remaining = Math.max(
          0,
          Math.ceil(NO_ANSWER_TIMEOUT_SECONDS - waited),
        );
        setNoAnswerRemaining(remaining);
        setSilenceTimer(0);

        if (remaining <= 0) {
          clearInterval(silenceTimerRef.current);
          setIsTimerRunning(false);
          setNoAnswerRemaining(null);
          pendingSubmissionRef.current = "no_answer";
          stopRecording();
        }
      } else {
        setNoAnswerRemaining(null);
        const silentFor = (Date.now() - lastSpeechTimeRef.current) / 1000;
        setSilenceTimer(Math.floor(silentFor));

        if (silentFor >= POST_SPEECH_SILENCE_SECONDS) {
          clearInterval(silenceTimerRef.current);
          setIsTimerRunning(false);
          setSilenceTimer(0);
          pendingSubmissionRef.current = "silence";
          stopRecording();
        }
      }
    }, 1000);

    return () => {
      clearInterval(silenceTimerRef.current);
    };
    // isRecording is a dep so the interval re-captures a fresh stopRecording
    // closure once recording actually starts (its internal guard reads the
    // isRecording value from its creation render).
  }, [isTimerRunning, isRecording, interviewStatus]);

  // Replace your entire SpeechRecognition useEffect with this final version

  useEffect(() => {
    // MediaRecorder version to replace browser STT API
    if (
      interviewStatus !== "active" &&
      interviewStatus !== "registering" &&
      interviewStatus !== "starting"
    ) {
      return;
    }

    const initMediaRecorder = async () => {
      try {
        console.log("🎤 Requesting audio permissions...");
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        console.log("✅ Audio permissions granted.");

        // Find supported mime type
        const mimeTypes = [
          "audio/webm;codecs=opus",
          "audio/webm",
          "audio/ogg;codecs=opus",
          "audio/wav",
          "audio/mp4",
        ];
        const supportedMimeType = mimeTypes.find((type) =>
          MediaRecorder.isTypeSupported(type),
        );
        console.log(`🎤 Supported MimeType: ${supportedMimeType}`);

        const mediaRecorder = new MediaRecorder(stream, {
          mimeType: supportedMimeType,
        });
        mediaRecorderRef.current = mediaRecorder;

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            console.log(`🎤 Audio data available: ${event.data.size} bytes`);
            audioChunksRef.current.push(event.data);
          }
        };

        mediaRecorder.onstart = () => {
          console.log("🎤 MediaRecorder started.");
        };

        mediaRecorder.onstop = async () => {
          console.log(
            `🎤 MediaRecorder stopped. Total chunks: ${audioChunksRef.current.length}`,
          );
          const audioBlob = new Blob(audioChunksRef.current, {
            type: supportedMimeType || "audio/webm",
          });
          audioChunksRef.current = [];
          console.log(
            `🎤 Audio blob created: ${audioBlob.size} bytes, type: ${audioBlob.type}`,
          );

          if (audioBlob.size < 100) {
            console.warn(
              "⚠️ Audio blob is too small, transcription might fail.",
            );
          }

          // Resolve a pending submission when transcription produced nothing
          // usable (STT failure, empty result). Previously these paths simply
          // returned, leaving "Alex is thinking..." on screen forever.
          const resolvePendingWithoutTranscript = () => {
            const reason = pendingSubmissionRef.current;
            if (!reason) {
              setIsSubmittingAnswer(false);
              return;
            }
            pendingSubmissionRef.current = null;

            const heardText = transcriptRef.current.trim();
            if (heardText) {
              setInput("");
              transcriptRef.current = "";
              if (onSendRef.current) onSendRef.current(heardText);
            } else if (reason === "no_answer") {
              // Candidate never spoke within the answer window — advance
              // with an empty answer (deliberate skip, scored as such).
              if (onSendRef.current) onSendRef.current("");
            } else {
              // Candidate DID speak but nothing was transcribed — never
              // convert their real answer into an empty submit. Let them
              // try again; the server question deadline still backstops.
              setIsSubmittingAnswer(false);
              showToast(
                "We couldn't hear that clearly — please answer again.",
                "warning",
              );
              if (beginListeningRef.current) beginListeningRef.current();
            }
          };

          // Send to backend for transcription
          const reader = new FileReader();
          reader.readAsDataURL(audioBlob);
          reader.onloadend = async () => {
            const base64Audio = reader.result.split(",")[1];
            console.log("🎤 Sending audio to backend for transcription...");
            try {
              const sampleRate =
                stream.getAudioTracks()[0].getSettings().sampleRate || 48000;
              const encoding = supportedMimeType.includes("opus")
                ? supportedMimeType.includes("webm")
                  ? "WEBM_OPUS"
                  : "OGG_OPUS"
                : "LINEAR16";
              const apiUrl =
                process.env.REACT_APP_API_URL || "http://localhost:5000";

              const response = await fetch(`${apiUrl}/api/speech/transcribe`, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${getToken()}`,
                },
                body: JSON.stringify({
                  audio_base64: base64Audio,
                  sample_rate_hertz: sampleRate,
                  encoding: encoding,
                  session_id: sessionIdRef.current,
                }),
              });

              if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error(
                  `❌ Transcription API error: ${response.status}`,
                  errorData,
                );
                resolvePendingWithoutTranscript();
                return;
              }

              const data = await response.json();
              console.log("✅ Transcription response:", data);
              if (data.transcript) {
                const finalTranscript = (
                  transcriptRef.current +
                  " " +
                  data.transcript
                ).trim();
                setInput(finalTranscript);
                transcriptRef.current = finalTranscript;

                // If auto-submit or manual send was triggered. Submit via the
                // ref — this handler is wired once per status change, and a
                // direct onSend reference would keep the closure from that
                // render, submitting every answer against question 1.
                if (pendingSubmissionRef.current) {
                  pendingSubmissionRef.current = null;
                  setInput("");
                  transcriptRef.current = "";
                  if (onSendRef.current) onSendRef.current(finalTranscript);
                }
              } else {
                console.warn("⚠️ No transcript received from backend.");
                resolvePendingWithoutTranscript();
              }
            } catch (error) {
              console.error("❌ Transcription network/fetch error:", error);
              resolvePendingWithoutTranscript();
            }
          };
        };
      } catch (err) {
        console.error("❌ Failed to initialize MediaRecorder:", err);
      }
    };

    initMediaRecorder();

    return () => {
      if (
        mediaRecorderRef.current &&
        mediaRecorderRef.current.state !== "inactive"
      ) {
        mediaRecorderRef.current.stop();
      }
    };
  }, [interviewStatus]);

  const startRecording = useCallback(() => {
    if (isSpeaking || isRecording || !mediaRecorderRef.current) return;

    setInput("");
    transcriptRef.current = "";
    lastSpeechTimeRef.current = Date.now();
    listeningStartedAtRef.current = Date.now();
    hasSpokenRef.current = false;
    setHasSpokenThisQuestion(false);
    setSilenceTimer(0);
    setNoAnswerRemaining(NO_ANSWER_TIMEOUT_SECONDS);

    try {
      audioChunksRef.current = [];
      mediaRecorderRef.current.start();
      setIsRecording(true);

      // Start volume-based silence detection
      const stream = mediaRecorderRef.current.stream;
      const audioContext = new (
        window.AudioContext || window.webkitAudioContext
      )();
      audioContextRef.current = audioContext;
      const analyser = audioContext.createAnalyser();
      analyserRef.current = analyser;
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      analyser.fftSize = 256;
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      volumeDetectionIntervalRef.current = setInterval(() => {
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const average = sum / bufferLength;

        if (average > SPEECH_VOLUME_THRESHOLD) {
          lastSpeechTimeRef.current = Date.now();
          if (!hasSpokenRef.current) {
            // First detected speech for this question: switch from the
            // "waiting for you to start" countdown to answer-silence tracking.
            hasSpokenRef.current = true;
            setHasSpokenThisQuestion(true);
            setNoAnswerRemaining(null);
          }
        }
      }, 100);
    } catch (e) {
      console.error("Error starting MediaRecorder or volume detection:", e);
    }
  }, [isSpeaking, isRecording]);

  const stopRecording = useCallback(() => {
    if (!isRecording || !mediaRecorderRef.current) return;

    try {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      // Show the "Alex is thinking..." indicator immediately — it covers both
      // the STT transcription phase and the backend answer-submission phase so
      // the user never stares at a silent, unresponsive screen.
      // NOTE: we deliberately do NOT set isSubmittingAnswerRef.current here
      // so that onSend() isn't blocked by its duplicate-submission guard.
      setIsSubmittingAnswer(true);

      // Clean up volume detection
      if (volumeDetectionIntervalRef.current) {
        clearInterval(volumeDetectionIntervalRef.current);
        volumeDetectionIntervalRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
    } catch (e) {
      console.error("Error stopping MediaRecorder:", e);
    }
  }, [isRecording]);

  // (Re)open the mic for the current question — used after the AI finishes
  // speaking, after a TTS failure (so the flow never dies with the audio),
  // and when transcription misses and the candidate needs another go.
  const beginListening = useCallback(() => {
    if (interviewStatusRef.current !== "active") return;
    setIsSubmittingAnswer(false);
    setSilenceTimer(0);
    lastSpeechTimeRef.current = Date.now();
    setIsTimerRunning(true);
    startRecording();
  }, [startRecording]);

  // Keep the long-lived handlers (MediaRecorder.onstop, TTS audio events)
  // pointed at the freshest closures.
  useEffect(() => {
    beginListeningRef.current = beginListening;
  }, [beginListening]);
  const speakResponse = async (text) => {
    if (!text) {
      console.warn("⚠️ speakResponse called with no text.");
      return;
    }
    console.log(`🔊 speakResponse: "${text.substring(0, 50)}..."`);

    if (isSpeaking) {
      console.log("🔊 Cancelling current speech...");
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
      }
      clearInterval(typingIntervalRef.current);
    }

    setFullQuestionText(text);
    setDisplayedText("");

    // Shared helper: wire up an <Audio> element and start word-sync animation.
    // Extracted so both the cache path and the live-fetch path reuse the same logic.
    const setupAndPlayAudio = (audioSrc) => {
      const audio = new Audio(audioSrc);

      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current.src = "";
      }
      currentAudioRef.current = audio;

      audio.onplay = () => {
        console.log("🔊 TTS audio playback started.");
        setIsSpeaking(true);

        const words = text.split(" ");
        // Show the first word immediately so the display is never blank
        // while the browser is loading the audio metadata/duration.
        setDisplayedText(words[0] || "");

        typingIntervalRef.current = setInterval(() => {
          const duration =
            isFinite(audio.duration) && audio.duration > 0
              ? audio.duration
              : words.length * 0.3;
          const progress = audio.currentTime / duration;
          const currentIndex = Math.min(
            words.length,
            Math.floor(progress * words.length) + 1,
          );
          setDisplayedText(words.slice(0, currentIndex).join(" "));
          if (currentIndex >= words.length || audio.ended) {
            clearInterval(typingIntervalRef.current);
            setDisplayedText(text);
          }
        }, 100);
      };

      audio.onended = () => {
        console.log("🔊 TTS audio playback ended.");
        setIsSpeaking(false);
        currentAudioRef.current = null;
        clearInterval(typingIntervalRef.current);
        setDisplayedText(text);
        if (interviewStatusRef.current === "active") {
          console.log("🎤 AI finished speaking. Opening the mic...");
          beginListening();
        }
      };

      audio.onerror = (e) => {
        console.error("❌ Audio playback error:", e);
        setIsSpeaking(false);
        currentAudioRef.current = null;
        clearInterval(typingIntervalRef.current);
        setDisplayedText(text);
        // Audio died mid-question — the text is on screen; keep the
        // interview moving by opening the mic anyway.
        if (interviewStatusRef.current === "active") beginListening();
      };

      audio.play().catch((e) => {
        console.error("❌ Audio play() failed:", e);
        setIsSpeaking(false);
        setDisplayedText(text);
        if (interviewStatusRef.current === "active") beginListening();
      });
    };

    // Fast path: use the pre-fetched audio blob if it matches this text.
    // This eliminates the TTS round-trip at the moment the interview starts.
    const cached = prefetchedTTSRef.current;
    if (cached && cached.text === text) {
      console.log("⚡ Using pre-fetched TTS audio (instant playback).");
      prefetchedTTSRef.current = null;
      setupAndPlayAudio(cached.audioSrc);
      return;
    }

    // TTS is unavailable: display the full question immediately and open the
    // mic so the interview continues silently instead of stalling. The
    // candidate reads the question rather than hearing it.
    const continueWithoutAudio = () => {
      setIsSpeaking(false);
      setDisplayedText(text);
      if (interviewStatusRef.current === "active") beginListening();
    };

    // Slow path: fetch TTS from the backend.
    try {
      const apiUrl = process.env.REACT_APP_API_URL || "http://localhost:5000";
      console.log(`🔊 Fetching TTS from: ${apiUrl}/api/speech/synthesize`);
      const response = await fetch(`${apiUrl}/api/speech/synthesize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ text, session_id: sessionIdRef.current }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error(`❌ TTS API error: ${response.status}`, errorData);
        continueWithoutAudio();
        return;
      }

      const data = await response.json();
      if (data.audio_base64) {
        console.log("✅ TTS audio received, base64 length:", data.audio_base64.length);
        setupAndPlayAudio(`data:audio/mp3;base64,${data.audio_base64}`);
      } else {
        console.error("❌ No audio_base64 in TTS response.");
        continueWithoutAudio();
      }
    } catch (error) {
      console.error("❌ Error in Google TTS fetch:", error);
      continueWithoutAudio();
    }
  }; // Automatically speak the first question
  useEffect(() => {
    if (
      interviewStatus === "active" &&
      (gazeRecorderStatus === "tracking" || gazeRecorderStatus === "failed") &&
      currentQuestion &&
      !isSpeaking &&
      !currentAudioRef.current &&
      !initialGreetingSpoken.current
    ) {
      initialGreetingSpoken.current = true;
      console.log(
        "🔊 Calibration complete — speaking initial greeting and first question...",
      );
      const initialMessage = `Your CV has a ${Math.round(
        similarityScore * 100,
      )}% match. ${currentQuestion}`;
      speakResponse(initialMessage);
    } // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interviewStatus, gazeRecorderStatus, currentQuestion, similarityScore]);

  // Interview elapsed time tracker
  useEffect(() => {
    if (interviewStatus === "active" && interviewStartTimeRef.current) {
      const timer = setInterval(() => {
        const elapsed = Math.floor(
          (Date.now() - interviewStartTimeRef.current) / 1000,
        );
        setInterviewElapsedTime(elapsed);
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [interviewStatus]);

  // --- Component Cleanup ---
  useEffect(() => {
    return () => {
      // Clear typing animation interval
      clearInterval(typingIntervalRef.current);
      stopLiveProctoring();
      stopCamera();
      if (
        gazeRecorderTrackingRef.current &&
        window.GazeCloudAPI &&
        window.GazeRecorderAPI
      ) {
        try {
          window.GazeRecorderAPI.StopRec();
          window.GazeCloudAPI.StopEyeTracking();
        } catch (error) {
          console.warn("Cleanup error for GazeRecorder:", error);
        }
      }
    };
  }, [stopLiveProctoring, stopCamera]);

  // --- Interview Completion Camera Cleanup ---
  useEffect(() => {
    if (
      interviewStatus === "completed" ||
      interviewStatus === "ending" ||
      interviewStatus === "discarded"
    ) {
      // Comprehensive camera and media cleanup
      const cleanup = () => {
        // Ensure camera shutdown via centralized function
        stopCamera();
        // Stop all camera and microphone tracks
        if (videoRef.current && videoRef.current.srcObject) {
          const stream = videoRef.current.srcObject;
          stream.getTracks().forEach((track) => {
            track.stop();
            console.log(`🔴 ${track.kind} track stopped - interview completed`);
          });
          videoRef.current.srcObject = null;
        }

        // Reset video element completely
        if (videoRef.current) {
          videoRef.current.pause();
          videoRef.current.removeAttribute("src");
          videoRef.current.load();
        }

        // Stop media recording
        if (mediaRecorder && mediaRecorder.state === "recording") {
          mediaRecorder.stop();
        }

        // Stop speech synthesis
        if (currentAudioRef.current) {
          currentAudioRef.current.pause();
          currentAudioRef.current = null;
        }

        // Stop speech recording
        if (
          mediaRecorderRef.current &&
          mediaRecorderRef.current.state !== "inactive"
        ) {
          try {
            mediaRecorderRef.current.stop();
          } catch (e) {
            // Already stopped
          }
        }

        if (
          gazeRecorderTrackingRef.current &&
          window.GazeCloudAPI &&
          window.GazeRecorderAPI
        ) {
          try {
            window.GazeRecorderAPI.StopRec();
            window.GazeCloudAPI.StopEyeTracking();
          } catch (error) {
            console.warn("Cleanup error for GazeRecorder:", error);
          }
        }

        // Clear all timers
        clearInterval(silenceTimerRef.current);

        // Stop proctoring
        stopLiveProctoring();

        // Clear states
        setIsRecording(false);
        setIsSpeaking(false);
        setIsTimerRunning(false);
        setIsRecordingVideo(false);
      };

      // Execute cleanup immediately and with a slight delay to ensure it's thorough
      cleanup();
      setTimeout(cleanup, 100);
      setTimeout(cleanup, 500); // Ensure complete cleanup
    }
  }, [interviewStatus, stopLiveProctoring, mediaRecorder, stopCamera]);

  // --- DERIVED VALUES (memoized so timers don't recompute them every second) ---

  const answerScorePct = React.useMemo(() => {
    if (!evaluation) return null;
    let score = null;
    if (evaluation?.quantitative_scores?.answer_score) {
      score = evaluation.quantitative_scores.answer_score;
    } else if (evaluation?.quantitative?.average_relevance_score) {
      score = evaluation.quantitative.average_relevance_score;
    } else if (evaluation?.quantitative_scores) {
      if (typeof evaluation.quantitative_scores === "number") {
        score = evaluation.quantitative_scores;
      } else if (typeof evaluation.quantitative_scores === "object") {
        score =
          evaluation.quantitative_scores.answer_score ||
          evaluation.quantitative_scores.average ||
          evaluation.quantitative_scores.overall ||
          Object.values(evaluation.quantitative_scores)[0];
      }
    }
    if (score === null) return null;
    return score <= 1 ? Math.round(score * 100) : Math.round(score);
  }, [evaluation]);

  const langScorePct = React.useMemo(() => {
    if (!evaluation) return null;
    let langScore = null;
    if (evaluation?.quantitative_scores?.language_score) {
      langScore = evaluation.quantitative_scores.language_score;
    } else if (evaluation?.quantitative_scores?.communication) {
      langScore = evaluation.quantitative_scores.communication;
    } else if (evaluation?.quantitative?.communication) {
      langScore = evaluation.quantitative.communication;
    }
    if (langScore === null) return null;
    return langScore <= 1 ? Math.round(langScore * 100) : Math.round(langScore);
  }, [evaluation]);

  // --- RENDER LOGIC ---
  if (interviewStatus === "starting") {
    return <LoadingScreen loadingStepIndex={loadingStepIndex} />;
  }

  if (interviewStatus === "registering") {
    // Construct URL using current hostname (handles localhost vs IP address)
    const mobileUrl = `${window.location.protocol}//${window.location.hostname}:3000/mobile-camera/${sessionId}`;

    return (
      <div className={Styles.registrationContainer}>
        <h2 className={Styles.registrationHeader}>
          {checklistDone ? "🔐 Camera Setup & Security Check" : "📋 Before You Begin"}
        </h2>
        <PhaseIndicator currentStep={checklistDone ? 1 : 0} />
        {!checklistDone ? (
          <PreInterviewChecklist onConfirm={() => setChecklistDone(true)} />
        ) : (
          <>
        <p style={{ color: "#64748b", fontSize: "1rem", marginBottom: "28px", textAlign: "center", maxWidth: "520px", lineHeight: "1.6" }}>
          Complete the steps below to verify your identity and begin your interview.
        </p>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: "32px",
            marginTop: "8px",
          }}
        >
          {/* LEFT: QR CODE SECTION */}
          <div
            style={{
              background: "white",
              padding: "28px 24px",
              borderRadius: "16px",
              border: "1px solid #e2e8f0",
              boxShadow: "0 8px 32px rgba(102, 126, 234, 0.1), 0 1px 3px rgba(0,0,0,0.06)",
              textAlign: "center",
              maxWidth: "300px",
              minWidth: "260px",
            }}
          >
            <div style={{ fontSize: "28px", marginBottom: "8px" }}>📱</div>
            <h4 style={{ color: "#1e293b", marginBottom: "8px", fontSize: "1.1rem", fontWeight: "600" }}>
              Step 1: Connect Phone
            </h4>
            <p
              style={{ color: "#64748b", fontSize: "0.85rem", marginBottom: "18px", lineHeight: "1.5" }}
            >
              Scan to enable 360° environment view. Place phone to show your
              side profile.
            </p>
            <div
              style={{
                background: "white",
                padding: "12px",
                display: "inline-block",
                borderRadius: "12px",
              }}
            >
              <QRCode value={mobileUrl} size={140} />
            </div>
          </div>

          {/* RIGHT: WEBCAM SECTION */}
          <div
            style={{
              background: "white",
              padding: "28px 24px",
              borderRadius: "16px",
              border: "1px solid #e2e8f0",
              boxShadow: "0 8px 32px rgba(102, 126, 234, 0.1), 0 1px 3px rgba(0,0,0,0.06)",
              textAlign: "center",
              minWidth: "260px",
            }}
          >
            <div style={{ fontSize: "28px", marginBottom: "8px" }}>💻</div>
            <h4 style={{ color: "#1e293b", marginBottom: "14px", fontSize: "1.1rem", fontWeight: "600" }}>
              Step 2: Face Registration
            </h4>
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className={Styles.registrationVideo}
              style={{
                width: "320px",
                height: "240px",
                borderRadius: "12px",
                border: "2px solid rgba(102, 126, 234, 0.5)",
              }}
            />
            <div style={{ marginTop: "20px" }}>
              <button
                onClick={handleFaceRegistration}
                className={Styles.registerButton}
              >
                Register Face & Calibrate
              </button>
            </div>
            <p
              style={{
                color: "#94a3b8",
                fontSize: "0.75rem",
                marginTop: "12px",
                lineHeight: "1.5",
                maxWidth: "320px",
              }}
            >
              Your photo is matched against your account's registered identity
              and shared with the recruiter to confirm who took the interview.
              Make sure only you are visible.
            </p>
          </div>
        </div>
          </>
        )}
        {toast && (
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
          />
        )}
      </div>
    );
  }

  if (interviewStatus === "calibrating") {
    return (
      <div className={Styles.registrationContainer}>
        <h2 className={Styles.registrationHeader}>
          👀 Eye Tracking Calibration
        </h2>
        <PhaseIndicator currentStep={2} />
        <p style={{ color: "#64748b", fontSize: "1rem", marginBottom: "28px", textAlign: "center", maxWidth: "520px", lineHeight: "1.6" }}>
          Please look at the red dots as they appear on your screen to calibrate eye tracking.
        </p>
        
        <div style={{
          width: "100%",
          maxWidth: "400px",
          background: "#e2e8f0",
          borderRadius: "8px",
          height: "12px",
          overflow: "hidden",
          margin: "0 auto 20px"
        }}>
          <div style={{
             width: `${calibrationProgress}%`,
             height: "100%",
             background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
             transition: "width 0.5s ease"
          }}></div>
        </div>
        
        <div style={{ marginTop: "15px", fontSize: "14px", color: "#94a3b8", textAlign: "center" }}>
          Calibrating... {calibrationProgress}%
        </div>
      </div>
    );
  }

  if (interviewStatus === "identity_blocked") {
    return (
      <div className={Styles.loadingContainer}>
        <h3 style={{ marginTop: "20px", color: "#dc2626", fontSize: "24px", fontWeight: "600" }}>
          Identity Verification Failed
        </h3>
        <p
          style={{
            color: "#991b1b",
            maxWidth: "560px",
            textAlign: "center",
            lineHeight: "1.6",
            marginTop: "12px",
            padding: "12px 14px",
            borderRadius: "10px",
            background: "#fef2f2",
            border: "1px solid #fecdd3",
          }}
        >
          {identityBlockMessage ||
            "The captured face repeatedly did not match the identity registered on this account."}
        </p>
        <p
          style={{
            color: "#64748b",
            maxWidth: "560px",
            textAlign: "center",
            lineHeight: "1.6",
            marginTop: "8px",
          }}
        >
          For fairness and security, interviews must be taken by the account
          owner whose face was registered during their first interview. This
          attempt has been recorded. If you believe this is an error, please
          contact support.
        </p>
        <div style={{ marginTop: "18px" }}>
          <button
            onClick={() =>
              navigate(location.state?.isPractice ? "/practice" : "/profile#applications")
            }
            className={Styles.registerButton}
          >
            {location.state?.isPractice ? "Back to Practice" : "Back to Applications"}
          </button>
        </div>
      </div>
    );
  }

  if (interviewStatus === "end_failed") {
    return (
      <div className={Styles.loadingContainer}>
        <h3 style={{ marginTop: "20px", color: "#dc2626", fontSize: "24px", fontWeight: "600" }}>
          Couldn't Finalize Your Interview
        </h3>
        <p
          style={{
            color: "#991b1b",
            maxWidth: "560px",
            textAlign: "center",
            lineHeight: "1.6",
            marginTop: "12px",
            padding: "12px 14px",
            borderRadius: "10px",
            background: "#fef2f2",
            border: "1px solid #fecdd3",
          }}
        >
          {endError || "A network problem interrupted the wrap-up."}
        </p>
        <p
          style={{
            color: "#64748b",
            maxWidth: "560px",
            textAlign: "center",
            lineHeight: "1.6",
            marginTop: "8px",
          }}
        >
          Your answers are already saved on our servers — nothing is lost.
          Click retry to finish generating your report.
        </p>
        <div style={{ marginTop: "18px" }}>
          <button onClick={() => endInterview()} className={Styles.registerButton}>
            Retry Finalizing
          </button>
        </div>
      </div>
    );
  }

  if (interviewStatus === "discarded") {
    const isPracticeDiscard = !!discardInfo?.isPractice;
    return (
      <div className={Styles.loadingContainer}>
        <h3 style={{ marginTop: "20px", color: "#b45309", fontSize: "24px", fontWeight: "600" }}>
          Interview Not Recorded
        </h3>
        <p
          style={{
            color: "#92400e",
            maxWidth: "560px",
            textAlign: "center",
            lineHeight: "1.6",
            marginTop: "12px",
            padding: "12px 14px",
            borderRadius: "10px",
            background: "#fffbeb",
            border: "1px solid #fde68a",
          }}
        >
          {discardInfo?.message ||
            "No answers were recorded, so this interview was discarded instead of being scored."}
        </p>
        <p
          style={{
            color: "#64748b",
            maxWidth: "560px",
            textAlign: "center",
            lineHeight: "1.6",
            marginTop: "8px",
          }}
        >
          {discardInfo?.refundSuccess
            ? isPracticeDiscard
              ? `The ${discardInfo?.creditsRefunded || ""} credits deducted for this practice session were refunded to your wallet. You can start a fresh practice interview any time.`
              : "The credits deducted for this interview were refunded to the recruiter, and your application is unaffected. You can retake the interview from your applications page."
            : "No report was generated for this session. You can retake the interview at any time."}
        </p>
        <div style={{ marginTop: "18px" }}>
          <button
            onClick={() =>
              navigate(isPracticeDiscard ? "/practice" : "/profile#applications")
            }
            className={Styles.registerButton}
          >
            {isPracticeDiscard ? "Back to Practice" : "Back to Applications"}
          </button>
        </div>
      </div>
    );
  }

  if (interviewStatus === "ready_to_start") {
    return (
      <div className={Styles.registrationContainer}>
        <h2 className={Styles.registrationHeader}>
          ✅ Ready to Begin
        </h2>
        <PhaseIndicator currentStep={3} />
        <p style={{ color: "#64748b", fontSize: "1rem", marginBottom: "28px", textAlign: "center", maxWidth: "520px", lineHeight: "1.6" }}>
          Your camera, microphone, and tracking systems are verified.
        </p>
        {(identityStatus === "verified" || identityStatus === "registered_new") && (
          <p
            style={{
              color: "#166534",
              background: "#f0fdf4",
              border: "1px solid #bbf7d0",
              borderRadius: "10px",
              padding: "10px 16px",
              fontSize: "0.95rem",
              textAlign: "center",
              marginBottom: "12px",
            }}
          >
            {identityStatus === "verified"
              ? "🪪 Identity verified — face matched your registered account identity."
              : "🪪 Face registered — this photo is now your account's verified identity."}
          </p>
        )}
        <div style={{ textAlign: "center", marginTop: "20px" }}>
          <button 
             className={Styles.registerButton}
             onClick={() => setInterviewStatus("active")}
             style={{ padding: "16px 40px", fontSize: "18px" }}
          >
             ▶ Start Interview Now
          </button>
        </div>
      </div>
    );
  }

  if (interviewStatus === "start_failed") {
    const normalizedError = (startErrorMessage || "").toLowerCase();
    const isPracticeMode = location.state?.isPractice || false;
    const isQuotaError =
      normalizedError.includes("credit") ||
      normalizedError.includes("limit") ||
      normalizedError.includes("unavailable");

    return (
      <div className={Styles.loadingContainer}>
        <h3 style={{ marginTop: "20px", color: "#dc2626", fontSize: "24px", fontWeight: "600" }}>
          Interview Could Not Start
        </h3>
        <p
          style={{
            color: "#991b1b",
            maxWidth: "560px",
            textAlign: "center",
            lineHeight: "1.6",
            marginTop: "12px",
            padding: "12px 14px",
            borderRadius: "10px",
            background: "#fef2f2",
            border: "1px solid #fecdd3",
          }}
        >
          {startErrorMessage || "Could not start the interview session."}
        </p>

        {isQuotaError && (
          <p
            style={{
              color: "#64748b",
              maxWidth: "560px",
              textAlign: "center",
              lineHeight: "1.6",
              marginTop: "8px",
            }}
          >
            {isPracticeMode
              ? "Your practice credits are exhausted. Upgrade your candidate plan to continue practice interviews."
              : "No action is required from you as a candidate. Please contact the recruiter to reopen interview availability for this role."}
          </p>
        )}

        <div style={{ marginTop: "18px", display: "flex", gap: "10px" }}>
          {isQuotaError && isPracticeMode && (
            <button
              onClick={() => navigate("/candidate/subscription")}
              className={Styles.registerButton}
            >
              Upgrade Plan
            </button>
          )}
          <button
            onClick={() =>
              navigate(isPracticeMode ? "/practice" : "/profile#applications")
            }
            className={Styles.registerButton}
          >
            {isPracticeMode ? "Back to Practice" : "Back to Applications"}
          </button>
        </div>
      </div>
    );
  }

  // Updated main interview render
  return (
    <div className={Styles["page-container-fullscreen"]}>
      {/* Interview progress header */}
      {interviewStatus === "active" && (
        <InterviewHeader
          questionCount={questionCount}
          maxQuestions={maxQuestions}
          interviewElapsedTime={interviewElapsedTime}
          silenceTimer={silenceTimer}
          isTimerRunning={isTimerRunning}
          hasSpoken={hasSpokenThisQuestion}
          noAnswerRemaining={noAnswerRemaining}
          autoSubmitAfter={POST_SPEECH_SILENCE_SECONDS}
        />
      )}
      {interviewStatus === "active" && timeoutWarning && (
        <div
          style={{
            textAlign: "center",
            padding: "6px 12px",
            background: "#fff3cd",
            color: "#856404",
            fontSize: 14,
          }}
        >
          Still there? This question will be skipped soon if there's no response.
        </div>
      )}
      {proctoringAlert.active && (
        <div className={Styles.modalOverlay}>
          {" "}
          <div className={Styles.modal}>
            <h2>Warning! ({warningCount})</h2>             {" "}
            <p>{proctoringAlert.message}</p>             {" "}
            <button
              onClick={() => setProctoringAlert({ active: false, message: "" })}
            >
              Acknowledge
            </button>{" "}
          </div>{" "}
        </div>
      )}
      {/* Candidate webcam — positioned top-left, always visible */}
      <div className={Styles["video-preview"]}>
        <video ref={videoRef} autoPlay muted playsInline />
        <div className={Styles["video-preview-label"]}>YOU</div>
      </div>
      <div className={Styles["avatar-container"]}>
        <Avatar />
      </div>
      <div className={Styles["controls-container"]}>
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div className={Styles["transcript-display"]}>
            {isSubmittingAnswer ? (
              /* Shown during STT processing + answer submission + question generation.
                 Covers the entire "silent gap" so the user always has feedback. */
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
                <div className={Styles["thinking-dots-container"]}>
                  <div className={Styles["thinking-dot"]}></div>
                  <div className={Styles["thinking-dot"]}></div>
                  <div className={Styles["thinking-dot"]}></div>
                </div>
                <span style={{ color: "rgba(148,163,184,0.9)", fontSize: "0.95rem", fontStyle: "italic" }}>
                  Alex is thinking...
                </span>
              </div>
            ) : isSpeaking ? (
              displayedText
            ) : (
              currentQuestion || "Waiting for next question..."
            )}
          </div>
          {input && input.trim().length > 0 && (
            <div
              style={{
                fontSize: "12px",
                color: "rgba(255, 255, 255, 0.7)",
                fontStyle: "italic",
              }}
            >
              {input.split(" ").length} words • {input.length} characters
            </div>
          )}
          {isRecording && !hasSpokenThisQuestion && !isSubmittingAnswer && (
            <div
              style={{
                fontSize: "12px",
                color: "rgba(255, 255, 255, 0.55)",
                fontStyle: "italic",
              }}
            >
              💡 Take a moment to think — or say "please repeat the question"
              to hear it again.
            </div>
          )}
        </div>

        <button
          className={`${Styles["mic-button"]} 
              ${isRecording ? Styles["mic-recording"] : ""} 
              ${isSpeaking || !isTimerRunning ? Styles["mic-disabled"] : ""}`}
          disabled={true}
        >
          {isRecording ? "Listening" : "Ready"}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path d="M12 14q.825 0 1.413-.588T14 12V6q0-.825-.588-1.413T12 4q-.825 0-1.413.588T10 6v6q0 .825.588 1.413T12 14Zm-1 7v-3.075q-2.6-.35-4.3-2.325T5 11H7q0 2.075 1.463 3.538T12 16q2.075 0 3.538-1.463T17 11h2q0 2.25-1.7 4.225T13 17.925V21h-2Z" />
          </svg>
        </button>

        {/* Manual Send Button */}
        <button
          className={Styles["send-button"]}
          onClick={() => {
            // If currently recording, stop it and signal for submission
            if (isRecording) {
              clearInterval(silenceTimerRef.current);
              setIsTimerRunning(false);
              pendingSubmissionRef.current = "manual";
              stopRecording();
              return;
            }

            // If not recording but we have input, send it
            if (input.trim().length > 0) {
              clearInterval(silenceTimerRef.current);
              setIsTimerRunning(false);
              onSend(input.trim());
              setInput("");
              transcriptRef.current = "";
            }
          }}
          disabled={
            (!isRecording && (!input || input.trim().length === 0)) ||
            isSpeaking ||
            !isTimerRunning ||
            isSubmittingAnswer
          }
        >
          {isSubmittingAnswer ? (
            <>
              <div
                className={Styles.spinner}
                style={{ width: "16px", height: "16px", borderWidth: "2px" }}
              ></div>
              Submitting...
            </>
          ) : isRecording ? (
            <>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M6 6h12v12H6z" />
              </svg>
              Stop & Send
            </>
          ) : (
            <>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
              Send Answer
            </>
          )}
        </button>

        {/* End Interview Early Button */}
        <button
          className={Styles["end-interview-btn"]}
          onClick={() => setShowEndInterviewConfirm(true)}
        >
          End Interview Early
        </button>

      </div>{" "}
      {interviewStatus === "completed" && evaluation && (
        <div className={Styles["evaluation-overlay"]}>
          {" "}
          <div className={Styles["evaluation-container"]}>
            <div style={{ textAlign: "center", marginBottom: "20px" }}>
              <h2
                style={{
                  color: "#27ae60",
                  fontSize: "28px",
                  marginBottom: "10px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "10px",
                }}
              >
                🎉 Interview Completed Successfully!
              </h2>
              <p style={{ color: "#666", fontSize: "16px" }}>
                Your performance has been evaluated and submitted.
              </p>
              <p style={{ color: "#999", fontSize: "14px", marginTop: "10px" }}>
                Review your results below
              </p>
            </div>
            {usageDeduction?.success && (
              <div
                style={{
                  background: "#eff6ff",
                  border: "1px solid #bfdbfe",
                  borderRadius: "12px",
                  padding: "14px 16px",
                  marginBottom: "18px",
                  color: "#1e3a8a",
                }}
              >
                <strong>Usage billing summary:</strong> $
                {Number(usageDeduction.usage_cost_usd || 0).toFixed(4)} used,{" "}
                {Number(usageDeduction.credits_deducted || 0)} credits deducted,{" "}
                {Number(usageDeduction.credits_remaining || 0)} credits
                remaining.
              </div>
            )}
            {usageDeduction && !usageDeduction.success && (
              <div
                style={{
                  background: "#fff7ed",
                  border: "1px solid #fed7aa",
                  borderRadius: "12px",
                  padding: "14px 16px",
                  marginBottom: "18px",
                  color: "#9a3412",
                }}
              >
                <strong>Billing update:</strong>{" "}
                {usageDeduction.error ||
                  "Usage deduction was not completed for this session."}
              </div>
            )}
            <div
              className={Styles["quantitative-metrics"]}
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "20px",
                marginBottom: "25px",
              }}
            >
              <div
                className={Styles["metric"]}
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
                  Answer Evaluation
                </div>
                <div style={{ fontSize: "32px", fontWeight: "bold" }}>
                  {answerScorePct != null ? `${answerScorePct}%` : "N/A"}
                </div>
              </div>
              <div
                className={Styles["metric"]}
                style={{
                  background:
                    "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
                  padding: "20px",
                  borderRadius: "12px",
                  color: "white",
                  textAlign: "center",
                  boxShadow: "0 4px 15px rgba(67, 233, 123, 0.4)",
                }}
              >
                <div
                  style={{
                    fontSize: "14px",
                    opacity: 0.9,
                    marginBottom: "8px",
                  }}
                >
                  Language Evaluation
                </div>
                <div style={{ fontSize: "32px", fontWeight: "bold" }}>
                  {langScorePct != null ? `${langScorePct}%` : "N/A"}
                </div>
              </div>
              <div
                className={Styles["metric"]}
                style={{
                  background:
                    "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
                  padding: "20px",
                  borderRadius: "12px",
                  color: "white",
                  textAlign: "center",
                  boxShadow: "0 4px 15px rgba(245, 87, 108, 0.4)",
                }}
              >
                <div
                  style={{
                    fontSize: "14px",
                    opacity: 0.9,
                    marginBottom: "8px",
                  }}
                >
                  Proctoring Score
                </div>
                <div style={{ fontSize: "32px", fontWeight: "bold" }}>
                  {proctoringStatus === "incomplete"
                    ? "N/A"
                    : typeof proctoringScore === "number"
                      ? `${Math.round(proctoringScore)}%`
                      : "Calculating..."}
                </div>
              </div>
              {evaluation.quantitative &&
                evaluation.quantitative.number_of_questions && (
                  <div
                    className={Styles["metric"]}
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
                      {evaluation.quantitative.number_of_questions}{" "}
                    </div>{" "}
                  </div>
                )}
            </div>
            {evaluation.qualitative_assessment && (
              <div
                style={{
                  background: "#f8f9fa",
                  padding: "20px",
                  borderRadius: "12px",
                  marginBottom: "20px",
                  border: "1px solid #e9ecef",
                }}
              >
                <h4
                  style={{
                    color: "#2c3e50",
                    marginBottom: "15px",
                    fontSize: "18px",
                    fontWeight: "600",
                  }}
                >
                  📋 Evaluation Summary
                </h4>
                <div
                  className={Styles["qualitative-assessment"]}
                  style={{
                    color: "#495057",
                    lineHeight: "1.6",
                  }}
                >
                  {" "}
                  {(evaluation.qualitative_assessment || "")
                    .split("\n")
                    .map((line, index) => (
                      <p key={index} style={{ marginBottom: "8px" }}>
                        {line}
                      </p>
                    ))}{" "}
                </div>
              </div>
            )}
            <div style={{ textAlign: "center" }}>
              <button
                className={Styles["back-to-dashboard"]}
                onClick={() => {
                  const isPracticeMode = location.state?.isPractice || false;
                  const redirectPath = isPracticeMode
                    ? "/practice"
                    : "/profile#applications";
                  navigate(redirectPath);
                }}
                style={{
                  background:
                    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                  color: "white",
                  border: "none",
                  padding: "15px 40px",
                  borderRadius: "8px",
                  fontSize: "16px",
                  fontWeight: "600",
                  cursor: "pointer",
                  boxShadow: "0 4px 15px rgba(102, 126, 234, 0.4)",
                  transition: "transform 0.2s, box-shadow 0.2s",
                }}
                onMouseOver={(e) => {
                  e.target.style.transform = "translateY(-2px)";
                  e.target.style.boxShadow =
                    "0 6px 20px rgba(102, 126, 234, 0.5)";
                }}
                onMouseOut={(e) => {
                  e.target.style.transform = "translateY(0)";
                  e.target.style.boxShadow =
                    "0 4px 15px rgba(102, 126, 234, 0.4)";
                }}
              >
                {location.state?.isPractice
                  ? "Back to Practice"
                  : "Go to Dashboard"}
              </button>
            </div>{" "}
          </div>{" "}
        </div>
      )}{" "}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
      <ConfirmDialog
        isOpen={showEndInterviewConfirm}
        onClose={() => setShowEndInterviewConfirm(false)}
        onConfirm={() => {
          setShowEndInterviewConfirm(false);
          endInterview();
        }}
        title="End interview early?"
        message="Are you sure you want to end the interview early? Your answers so far will be submitted for evaluation."
        confirmText="End Interview"
        confirmVariant="danger"
      />
    </div>
  );
}

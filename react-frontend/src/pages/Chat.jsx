import React, { useEffect, useState, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Styles from "./Chat.module.css";
import { FFmpeg } from "@ffmpeg/ffmpeg";
import { toBlobURL } from "@ffmpeg/util";
import io from "socket.io-client";
import Avatar from "../components/Avatar"; // Import the new Avatar component
import QRCode from "react-qr-code";
import { proctoringConfig } from "../config/proctoring";

// Removed formatTime function - no longer needed since we removed the 30-second timer

export default function Chat({ interviewId }) {
  const MAX_QUESTIONS = 10;
  // --- STATE MANAGEMENT ---
  // Add this with your other refs
  const isTimerRunningRef = useRef(false);
  const currentAudioRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const [chatContent, setChatContent] = useState({});
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [interviewStatus, setInterviewStatus] = useState("starting");
  const [startErrorMessage, setStartErrorMessage] = useState("");
  const [evaluation, setEvaluation] = useState(null);
  const [similarityScore, setSimilarityScore] = useState(null);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [gazeDirection, setGazeDirection] = useState(null);
  const [gazeTimes, setGazeTimes] = useState(null);
  const [isRecordingVideo, setIsRecordingVideo] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("idle");
  const [gazeRecorderStatus, setGazeRecorderStatus] = useState("idle"); // idle | calibrating | tracking | submitted | failed
  const [proctoringAlert, setProctoringAlert] = useState({
    active: false,
    message: "",
  });
  const [warningCount, setWarningCount] = useState(0);

  // Removed timeLeft state - using only silence detection now
  const [isTimerRunning, setIsTimerRunning] = useState(false);
  const [questionCount, setQuestionCount] = useState(0);
  const [silenceTimer, setSilenceTimer] = useState(0); // Track silence duration
  const silenceTimerRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const volumeDetectionIntervalRef = useRef(null);
  const lastSpeechTimeRef = useRef(Date.now());
  const [interviewElapsedTime, setInterviewElapsedTime] = useState(0); // Track total interview time
  const interviewStartTimeRef = useRef(null);
  const initialGreetingSpoken = useRef(false);
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false); // Track answer submission

  // Add state for progressive text display
  const [displayedText, setDisplayedText] = useState("");
  const [fullQuestionText, setFullQuestionText] = useState("");
  const typingIntervalRef = useRef(null); // --- REFS ---

  const videoRef = useRef(null);
  const ffmpegRef = useRef(new FFmpeg());
  const stopPromiseResolver = useRef(null);
  const recordedChunksRef = useRef([]);
  const socketRef = useRef(null);
  const proctoringIntervalRef = useRef(null);
  const sessionIdRef = useRef(null);
  const interviewStartInitiated = useRef(false);
  const gazeRecorderScriptsLoadedRef = useRef(false);
  const gazeRecorderTrackingRef = useRef(false);
  const gazePointsRef = useRef([]);
  const gazeStartedAtMsRef = useRef(null);
  const gazeEndedAtMsRef = useRef(null);
  const gazeStartTimeRef = useRef(null);
  const gazeRecordingDataRef = useRef(null);
  const gazeRecorderStartRequestedRef = useRef(false);

  // --- MODIFICATION --- Add refs for the timer and the latest transcript
  const timerRef = useRef(null);
  const transcriptRef = useRef("");
  // Track the currently active MediaStream explicitly to guarantee full shutdown
  const cameraStreamRef = useRef(null);
  const pendingSubmissionRef = useRef(false);

  // --- HOOKS ---
  const navigate = useNavigate();
  const location = useLocation();

  // Helper function to format elapsed time (MM:SS)
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Add this hook to your component
  useEffect(() => {
    isTimerRunningRef.current = isTimerRunning;
  }, [isTimerRunning]); // --- PROCTORING FOR TAB/WINDOW SWITCHING (No changes needed) ---

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
        existing.addEventListener('load', () => resolve(), { once: true });
        existing.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)), { once: true });
        return;
      }
      const script = document.createElement('script');
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

  const startInlineGazeRecorder = useCallback(async () => {
    if (gazeRecorderTrackingRef.current || gazeRecorderStartRequestedRef.current) {
      return true;
    }
    try {
      gazeRecorderStartRequestedRef.current = true;
      setGazeRecorderStatus('calibrating');
      if (!gazeRecorderScriptsLoadedRef.current) {
        await loadScript("https://app.gazerecorder.com/GazeCloudAPI.js");
        await loadScript("https://app.gazerecorder.com/GazeRecorderAPI.js");
        await loadScript("https://app.gazerecorder.com/GazePlayer.js");
        gazeRecorderScriptsLoadedRef.current = true;
      }

      if (!window.GazeCloudAPI || !window.GazeRecorderAPI) {
        throw new Error('GazeRecorder scripts not available.');
      }

      gazePointsRef.current = [];
      gazeRecordingDataRef.current = null;
      gazeStartedAtMsRef.current = Date.now();
      gazeEndedAtMsRef.current = null;
      gazeStartTimeRef.current = Date.now();

      window.GazeCloudAPI.OnResult = function (gazeData) {
        if (!gazeRecorderTrackingRef.current) return;
        gazePointsRef.current.push({
          timestamp: (Date.now() - gazeStartTimeRef.current) / 1000,
          x: gazeData?.docX || 0,
          y: gazeData?.docY || 0
        });
      };

      window.GazeCloudAPI.OnCalibrationComplete = function () {
        window.GazeRecorderAPI.Rec();
        gazeRecorderTrackingRef.current = true;
        gazeStartTimeRef.current = Date.now();
        setGazeRecorderStatus('tracking');
      };

      window.GazeCloudAPI.StartEyeTracking();
      return true;
    } catch (error) {
      console.error('Failed to start inline GazeRecorder:', error);
      setGazeRecorderStatus('failed');
      gazeRecorderStartRequestedRef.current = false;
      return false;
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
        console.warn('No GazeRecorder points captured.');
        return;
      }

      const token = localStorage.getItem("companyxyz-token");
      const apiBase = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
      const response = await fetch(`${apiBase}/api/interviews/${currentSessionId}/gaze-recorder-results`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          session_id: currentSessionId,
          recordingData: gazeRecordingDataRef.current,
          gazePoints: gazePointsRef.current,
          startedAtMs: gazeStartedAtMsRef.current,
          endedAtMs: gazeEndedAtMsRef.current,
          viewport: { width: window.innerWidth, height: window.innerHeight }
        })
      });

      if (!response.ok) {
        throw new Error((await response.json()).error || 'Failed to submit GazeRecorder data');
      }

      setGazeRecorderStatus('submitted');
      gazeRecorderStartRequestedRef.current = false;
    } catch (error) {
      console.error('Failed to finalize inline GazeRecorder:', error);
      setGazeRecorderStatus('failed');
    }
  }, []);

  // --- LIVE PROCTORING & WEBSOCKETS (No changes needed) ---

  const startLiveProctoring = useCallback(() => {
    const currentSessionId = sessionIdRef.current;
    if (!currentSessionId || (socketRef.current && socketRef.current.connected))
      return;
    const socket = io(process.env.REACT_APP_API_URL);
    socketRef.current = socket;
    socket.on("connect", () => {
      console.log("✅ WebSocket connected.");
      socket.emit("start_proctoring", { session_id: currentSessionId });
      console.log("📡 Signaling mobile to START...");
      socket.emit("control_mobile_recording", {
        session_id: currentSessionId,
        action: "start"
      });
      socket.on("gaze_data", (data) => {
        setGazeDirection(data.gaze_direction);
        setGazeTimes(data.gaze_times);
        if (data.is_cheating_alert) {
          const newWarningCount = warningCount + 1;
          setWarningCount(newWarningCount);
          setProctoringAlert({
            active: true,
            message: `Suspicious gaze detected! This is warning #${newWarningCount}.`,
          });
          socket.emit("proctoring_violation", {
            session_id: sessionIdRef.current,
            type: "gaze_violation",
          });
        }
      });

      proctoringIntervalRef.current = setInterval(() => {
        if (
          videoRef.current &&
          videoRef.current.srcObject &&
          videoRef.current.readyState === 4
        ) {
          const canvas = document.createElement("canvas");
          canvas.width = videoRef.current.videoWidth;
          canvas.height = videoRef.current.videoHeight;
          const context = canvas.getContext("2d");
          context.drawImage(
            videoRef.current,
            0,
            0,
            canvas.width,
            canvas.height
          );
          const imageData = canvas.toDataURL("image/jpeg", 0.5);
          socket.emit("proctoring_frame", {
            session_id: currentSessionId,
            image: imageData,
          });
        }
      }, 100);
    });
    socket.on("disconnect", () => {
      console.log("❌ WebSocket disconnected.");
      if (proctoringIntervalRef.current)
        clearInterval(proctoringIntervalRef.current);
    });
  }, []);

  const stopLiveProctoring = useCallback(() => {
    if (proctoringIntervalRef.current) {
      clearInterval(proctoringIntervalRef.current);
      proctoringIntervalRef.current = null;
    }
  }, []); // --- FACE REGISTRATION (No changes needed) ---

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
      alert("Please enable fullscreen mode to continue the interview.");
      return;
    }

    const currentSessionId = sessionIdRef.current;
    if (
      !videoRef.current ||
      !currentSessionId ||
      videoRef.current.readyState < 3
    ) {
      alert("Webcam not ready or session not started.");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const context = canvas.getContext("2d");
    context.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    const imageData = canvas.toDataURL("image/jpeg");
    try {
      const token = localStorage.getItem("companyxyz-token");
      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/register-face`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ image: imageData }),
        }
      );
      if (!response.ok)
        throw new Error(
          (await response.json()).message || "Face registration failed."
        );

      console.log("✅ Face registered successfully, starting interview monitoring...");
      
      setInterviewStatus("active");
    } catch (error) {
      console.error("Face registration error:", error);
      alert(`Could not register face: ${error.message}.`);
    }
  }, []); // --- ARCHIVAL VIDEO RECORDING & UPLOADING (No changes needed) ---

  const uploadRecording = useCallback(async (blob) => {
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
            "text/javascript"
          ),
          wasmURL: await toBlobURL(
            `${baseURL}/ffmpeg-core.wasm`,
            "application/wasm"
          ),
        });
      }
      await ffmpeg.writeFile(
        "input.webm",
        new Uint8Array(await blob.arrayBuffer())
      );
      await ffmpeg.exec(["-i", "input.webm", "-c", "copy", "output.mp4"]);
      const data = await ffmpeg.readFile("output.mp4");
      const formData = new FormData();
      formData.append(
        "recording",
        new Blob([data.buffer], { type: "video/mp4" }),
        `interview_${currentSessionId}.mp4`
      );
      const token = localStorage.getItem("companyxyz-token");
      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/upload-recording`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        }
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
  }, [finalizeInlineGazeRecorder]);

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

  // Centralized camera shutdown to ensure hardware and browser indicator turn off
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
        try { videoRef.current.pause(); } catch (e) { }
        videoRef.current.removeAttribute("src");
        try { videoRef.current.load(); } catch (e) { }
      }
    } catch (e) {
      // no-op
    }
  }, []);

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
      // Start the inline GazeRecorder on the same interview page.
      // This triggers calibration exactly when interview monitoring starts.
      await startInlineGazeRecorder();
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
  }, [startInlineGazeRecorder, startLiveProctoring, uploadRecording]);

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
      if (isPracticeMode && location.state?.sessionId && location.state?.initialQuestion) {
        // Session already created by Practice page
        setSessionId(location.state.sessionId);
        sessionIdRef.current = location.state.sessionId;
        setSimilarityScore(location.state.similarityScore || 0);
        setCurrentQuestion(location.state.initialQuestion);
        setInterviewStatus("registering");
        return;
      }

      // Get application ID from navigation state (not needed for practice mode)
      const applicationId = location.state?.applicationId;

      const token = localStorage.getItem("companyxyz-token");

      // For real interviews (not practice with pre-created session)
      const endpoint = `${process.env.REACT_APP_API_URL}/api/interviews/start`;

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
              data?.error || data?.message || "Could not start interview session.";
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
        alert(
          "Could not access the camera. Please check your browser permissions and ensure your camera is not in use by another application. Redirecting to the dashboard."
        );
        navigate("/profile#applications");
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
            similarityScore * 100
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
  ]);

  const endInterview = useCallback(async () => {
    if (socketRef.current) {
      console.log("📡 Signaling mobile to STOP...");
      socketRef.current.emit("control_mobile_recording", {
        session_id: sessionIdRef.current,
        action: "stop"
      });
    }
    const currentSessionId = sessionIdRef.current;
    if (
      !currentSessionId ||
      (interviewStatus !== "active" && interviewStatus !== "ending") || // Allow ending from active state
      uploadStatus === "uploading"
    )
      return;

    setInterviewStatus("ending");

    // CRITICAL: Stop timer and speech recognition IMMEDIATELY
    setIsTimerRunning(false);
    isTimerRunningRef.current = false; // Stop recognition from restarting
    clearInterval(timerRef.current);
    clearInterval(silenceTimerRef.current);

    // Stop speech recording
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
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

      const token = localStorage.getItem("companyxyz-token");
      const isPracticeMode = location.state?.isPractice || false;

      // Use different endpoint for practice mode
      const endpoint = isPracticeMode
        ? `${process.env.REACT_APP_API_URL}/api/practice/${currentSessionId}/end`
        : `${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/end`;

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

      setInterviewStatus("completed");
      setEvaluation(data.evaluation);
      console.log("✅ Interview ended successfully:", data.evaluation);

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
            `${process.env.REACT_APP_API_URL}/api/applications/${location.state?.applicationId}/update-score`,
            {
              method: "PUT",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({
                interview_score: interviewScore,
              }),
            }
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

      // Store interview completion flag for Profile page to detect
      localStorage.setItem("interview-just-completed", "true");
    } catch (error) {
      console.error("Failed to end interview:", error);
      setInterviewStatus("active"); // Revert status on failure
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
        interviewStatus !== "active"
      ) {
        return;
      }

      setInput("");
      setIsSubmittingAnswer(true);

      try {
        const token = localStorage.getItem("companyxyz-token");

        // Use different endpoint for practice mode
        const endpoint = isPracticeMode
          ? `${process.env.REACT_APP_API_URL}/api/practice/${currentSessionId}/answer`
          : `${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/answer`;

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
        if (data.interview_complete || questionCount >= MAX_QUESTIONS) {
          // Reset submitting state before ending
          setIsSubmittingAnswer(false);
          await endInterview();
        } else {
          // Increment question count for the NEXT question
          setQuestionCount((prev) => prev + 1);
          setCurrentQuestion(data.next_question);
          speakResponse(data.next_question);
        }
      } catch (error) {
        console.error("Error in onSend:", error);
        speakResponse(`An error occurred: ${error.message}`);
      } finally {
        setIsSubmittingAnswer(false);
      }
    },
    [currentQuestion, interviewStatus, endInterview, questionCount, location.state]
  );

  // --- FIXED --- Only silence detection, no 30-second timer
  useEffect(() => {
    // Don't run timer if interview is not active
    if (interviewStatus !== "active") {
      clearInterval(silenceTimerRef.current);
      return;
    }

    if (isTimerRunning) {
      // Only silence detection timer - checks every second
      silenceTimerRef.current = setInterval(() => {
        const timeSinceLastSpeech =
          (Date.now() - lastSpeechTimeRef.current) / 1000;
        setSilenceTimer(Math.floor(timeSinceLastSpeech));

        // Auto-submit after 3 seconds of silence
        if (
          timeSinceLastSpeech >= 3
        ) {
          clearInterval(silenceTimerRef.current);
          setIsTimerRunning(false);

          pendingSubmissionRef.current = true;
          stopRecording();
          setSilenceTimer(0);
        }
      }, 1000);
    } else {
      clearInterval(silenceTimerRef.current);
    }

    return () => {
      clearInterval(silenceTimerRef.current);
    };
  }, [isTimerRunning, isRecording, onSend, interviewStatus]);

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
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        console.log("✅ Audio permissions granted.");

        // Find supported mime type
        const mimeTypes = [
          'audio/webm;codecs=opus',
          'audio/webm',
          'audio/ogg;codecs=opus',
          'audio/wav',
          'audio/mp4'
        ];
        const supportedMimeType = mimeTypes.find(type => MediaRecorder.isTypeSupported(type));
        console.log(`🎤 Supported MimeType: ${supportedMimeType}`);

        const mediaRecorder = new MediaRecorder(stream, { mimeType: supportedMimeType });
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
          console.log(`🎤 MediaRecorder stopped. Total chunks: ${audioChunksRef.current.length}`);
          const audioBlob = new Blob(audioChunksRef.current, { type: supportedMimeType || 'audio/webm' });
          audioChunksRef.current = [];
          console.log(`🎤 Audio blob created: ${audioBlob.size} bytes, type: ${audioBlob.type}`);

          if (audioBlob.size < 100) {
            console.warn("⚠️ Audio blob is too small, transcription might fail.");
          }

          // Send to backend for transcription
          const reader = new FileReader();
          reader.readAsDataURL(audioBlob);
          reader.onloadend = async () => {
            const base64Audio = reader.result.split(',')[1];
            console.log("🎤 Sending audio to backend for transcription...");
            try {
              const sampleRate = stream.getAudioTracks()[0].getSettings().sampleRate || 48000;
              const encoding = supportedMimeType.includes('opus') ? (supportedMimeType.includes('webm') ? 'WEBM_OPUS' : 'OGG_OPUS') : 'LINEAR16';
              const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:5000';

              const response = await fetch(`${apiUrl}/api/speech/transcribe`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  audio_base64: base64Audio,
                  sample_rate_hertz: sampleRate,
                  encoding: encoding
                }),
              });

              if (!response.ok) {
                const errorData = await response.json();
                console.error(`❌ Transcription API error: ${response.status}`, errorData);
                return;
              }

              const data = await response.json();
              console.log("✅ Transcription response:", data);
              if (data.transcript) {
                const finalTranscript = (transcriptRef.current + " " + data.transcript).trim();
                setInput(finalTranscript);
                transcriptRef.current = finalTranscript;

                // If auto-submit or manual send was triggered
                if (pendingSubmissionRef.current) {
                  pendingSubmissionRef.current = false;
                  onSend(finalTranscript);
                  setInput("");
                  transcriptRef.current = "";
                }
              } else {
                console.warn("⚠️ No transcript received from backend.");
                // Still handle pending submission even if no transcript
                if (pendingSubmissionRef.current) {
                  pendingSubmissionRef.current = false;
                  if (transcriptRef.current.trim()) {
                    onSend(transcriptRef.current.trim());
                    setInput("");
                    transcriptRef.current = "";
                  }
                }
              }
            } catch (error) {
              console.error("❌ Transcription network/fetch error:", error);
            }
          };
        };
      } catch (err) {
        console.error("❌ Failed to initialize MediaRecorder:", err);
      }
    };

    initMediaRecorder();

    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
    };
  }, [interviewStatus]);

  const startRecording = useCallback(() => {
    if (isSpeaking || isRecording || !mediaRecorderRef.current) return;

    setInput("");
    transcriptRef.current = "";
    lastSpeechTimeRef.current = Date.now();
    setSilenceTimer(0);

    try {
      audioChunksRef.current = [];
      mediaRecorderRef.current.start();
      setIsRecording(true);

      // Start volume-based silence detection
      const stream = mediaRecorderRef.current.stream;
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
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

        // Threshold for speech detection (adjust as needed)
        if (average > 10) {
          lastSpeechTimeRef.current = Date.now();
          if (silenceTimer > 0) {
            setSilenceTimer(0);
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
      // Clear any existing typing animation
      clearInterval(typingIntervalRef.current);
    }

    // Set full text and start progressive display
    setFullQuestionText(text);
    setDisplayedText(""); // Reset displayed text

    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:5000';
      console.log(`🔊 Fetching TTS from: ${apiUrl}/api/speech/synthesize`);
      const response = await fetch(`${apiUrl}/api/speech/synthesize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        console.error(`❌ TTS API error: ${response.status}`, errorData);
        setIsSpeaking(false);
        setDisplayedText(text);
        return;
      }

      const data = await response.json();
      if (data.audio_base64) {
        console.log("✅ TTS audio received, base64 length:", data.audio_base64.length);
        const audioSrc = `data:audio/mp3;base64,${data.audio_base64}`;
        const audio = new Audio(audioSrc);
        currentAudioRef.current = audio;

        audio.onplay = () => {
          console.log("🔊 TTS audio playback started.");
          setIsSpeaking(true);

          // Start progressive text animation
          let currentIndex = 0;
          const words = text.split(" ");

          // Estimate speech duration from audio length if possible
          // Otherwise use a default word-based timing
          const intervalDelay = audio.duration ? (audio.duration * 1000 / words.length) : 300;
          console.log(`🔊 Text animation interval: ${intervalDelay}ms`);

          typingIntervalRef.current = setInterval(() => {
            if (currentIndex < words.length) {
              const wordsToShow = words.slice(0, currentIndex + 1).join(" ");
              setDisplayedText(wordsToShow);
              currentIndex++;
            } else {
              clearInterval(typingIntervalRef.current);
              setDisplayedText(text);
            }
          }, Math.max(intervalDelay, 150));
        };

        audio.onended = () => {
          console.log("🔊 TTS audio playback ended.");
          setIsSpeaking(false);
          currentAudioRef.current = null;
          clearInterval(typingIntervalRef.current);
          setDisplayedText(text);

          if (interviewStatus === "active") {
            console.log("🎤 AI finished speaking. Starting silence detection & recording...");
            setSilenceTimer(0);
            lastSpeechTimeRef.current = Date.now();
            setIsTimerRunning(true);
            startRecording();
          }
        };

        audio.onerror = (e) => {
          console.error("❌ Audio playback error:", e);
          setIsSpeaking(false);
          currentAudioRef.current = null;
          clearInterval(typingIntervalRef.current);
          setDisplayedText(text);
        };

        audio.play().catch(e => {
          console.error("❌ Audio play() failed:", e);
          // Auto-resume if blocked by browser policy (common issue)
          setIsSpeaking(false);
          setDisplayedText(text);
        });
      } else {
        console.error("❌ No audio_base64 in TTS response.");
        setIsSpeaking(false);
        setDisplayedText(text);
      }
    } catch (error) {
      console.error("❌ Error in Google TTS fetch:", error);
      setIsSpeaking(false);
      setDisplayedText(text);
    }
  }; // Automatically speak the first question
  useEffect(() => {
    if (
      interviewStatus === "active" &&
      currentQuestion &&
      !isSpeaking &&
      !currentAudioRef.current &&
      !initialGreetingSpoken.current
    ) {
      initialGreetingSpoken.current = true;
      console.log("🔊 Speaking initial greeting and first question...");
      setTimeout(() => {
        const initialMessage = `Your CV has a ${Math.round(
          similarityScore * 100
        )}% match. ${currentQuestion}`;
        speakResponse(initialMessage);
      }, 1000);
    } // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interviewStatus, currentQuestion, similarityScore]);

  // Interview elapsed time tracker
  useEffect(() => {
    if (interviewStatus === "active" && interviewStartTimeRef.current) {
      const timer = setInterval(() => {
        const elapsed = Math.floor(
          (Date.now() - interviewStartTimeRef.current) / 1000
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
      if (gazeRecorderTrackingRef.current && window.GazeCloudAPI && window.GazeRecorderAPI) {
        try {
          window.GazeRecorderAPI.StopRec();
          window.GazeCloudAPI.StopEyeTracking();
        } catch (error) {
          console.warn('Cleanup error for GazeRecorder:', error);
        }
      }
      gazeRecorderStartRequestedRef.current = false;
    };
  }, [stopLiveProctoring, stopCamera]);

  // --- Interview Completion Camera Cleanup ---
  useEffect(() => {
    if (interviewStatus === "completed" || interviewStatus === "ending") {
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
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
          try {
            mediaRecorderRef.current.stop();
          } catch (e) {
            // Already stopped
          }
        }

        if (gazeRecorderTrackingRef.current && window.GazeCloudAPI && window.GazeRecorderAPI) {
          try {
            window.GazeRecorderAPI.StopRec();
            window.GazeCloudAPI.StopEyeTracking();
          } catch (error) {
            console.warn('Cleanup error for GazeRecorder:', error);
          }
        }
        gazeRecorderStartRequestedRef.current = false;

        // Clear all timers
        clearInterval(timerRef.current);
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

  // --- RENDER LOGIC ---
  if (interviewStatus === "starting") {
    return (
      <div className={Styles.loadingContainer}>
        <div className={Styles.spinner}></div>
        <h3 style={{ marginTop: "20px", color: "#667eea", fontSize: "24px" }}>
          Preparing Your Interview
        </h3>
        <p
          style={{
            color: "#666",
            maxWidth: "400px",
            textAlign: "center",
            lineHeight: "1.6",
          }}
        >
          We're analyzing your CV and the job description to generate
          personalized questions...
        </p>
        <div style={{ marginTop: "15px", fontSize: "14px", color: "#999" }}>
          This usually takes 3-5 seconds
        </div>
      </div>
    );
  }

  if (interviewStatus === "registering") {
    // Construct URL using current hostname (handles localhost vs IP address)
    const mobileUrl = `${window.location.protocol}//${window.location.hostname}:3000/mobile-cam/${sessionId}`;

    return (
      <div className={Styles.registrationContainer}>
        <h2 className={Styles.registrationHeader}>Camera Setup & Security Check</h2>

        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '40px', marginTop: '20px' }}>

          {/* LEFT: QR CODE SECTION */}
          <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 4px 15px rgba(0,0,0,0.1)', textAlign: 'center', maxWidth: '300px' }}>
            <h4 style={{ color: '#333', marginBottom: '10px' }}>📱 Step 1: Connect Phone</h4>
            <p style={{ color: '#666', fontSize: '13px', marginBottom: '15px' }}>
              Scan to enable 360° environment view. Place phone to show your side profile.
            </p>
            <div style={{ background: 'white', padding: '10px', display: 'inline-block' }}>
              <QRCode value={mobileUrl} size={140} />
            </div>
          </div>

          {/* RIGHT: WEBCAM SECTION */}
          <div style={{ textAlign: 'center' }}>
            <h4 style={{ color: '#fff', marginBottom: '10px' }}>💻 Step 2: Face Registration</h4>
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className={Styles.registrationVideo}
              style={{ width: '320px', height: '240px', borderRadius: '8px', border: '2px solid #667eea' }}
            />
            <button
              onClick={handleFaceRegistration}
              className={Styles.registerButton}
              style={{ marginTop: '20px' }}
            >
              Start Interview
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (interviewStatus === "start_failed") {
    const normalizedError = (startErrorMessage || "").toLowerCase();
    const isQuotaError =
      normalizedError.includes("credit") ||
      normalizedError.includes("limit") ||
      normalizedError.includes("unavailable");

    return (
      <div className={Styles.loadingContainer}>
        <h3 style={{ marginTop: "20px", color: "#dc2626", fontSize: "24px" }}>
          Interview Could Not Start
        </h3>
        <p
          style={{
            color: "#444",
            maxWidth: "560px",
            textAlign: "center",
            lineHeight: "1.6",
            marginTop: "12px",
            padding: "12px 14px",
            borderRadius: "10px",
            background: "#fff1f2",
            border: "1px solid #fecdd3",
          }}
        >
          {startErrorMessage || "Could not start the interview session."}
        </p>

        {isQuotaError && (
          <p
            style={{
              color: "#666",
              maxWidth: "560px",
              textAlign: "center",
              lineHeight: "1.6",
              marginTop: "8px",
            }}
          >
            No action is required from you as a candidate. Please contact the recruiter to reopen interview availability for this role.
          </p>
        )}

        <div style={{ marginTop: "18px", display: "flex", gap: "10px" }}>
          <button
            onClick={() => navigate("/profile#applications")}
            className={Styles.registerButton}
          >
            Back to Applications
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
        <div className={Styles["interview-header"]}>
          <div className={Styles["progress-info"]}>
            <span className={Styles["question-counter"]}>
              Question {questionCount} of {MAX_QUESTIONS}
            </span>
            <span className={Styles["time-elapsed"]}>
              ⏱️ {formatTime(interviewElapsedTime)}
            </span>
          </div>
          {isTimerRunning && transcriptRef.current.trim().length > 0 && (
            <div className={Styles["silence-indicator"]}>
              {silenceTimer < 5
                ? `Speaking... ${5 - silenceTimer}s until auto-submit`
                : "Auto-submitting..."}
            </div>
          )}
        </div>
      )}
      {" "}
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
            </button>
            {" "}
          </div>
          {" "}
        </div>
      )}
      {" "}
      <div className={Styles["video-preview"]}>
        <video ref={videoRef} autoPlay muted playsInline />       {" "}
      </div>
      {" "}
      <div className={Styles["avatar-container"]}>
        <Avatar />       {" "}
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
          <p className={Styles["transcript-display"]}>
            {isSubmittingAnswer
              ? "AI is thinking..."
              : isRecording
                ? input || "Listening..."
                : isTimerRunning
                  ? "Ready to speak..."
                  : isSpeaking
                    ? displayedText
                    : currentQuestion || "Waiting for next question..."}
          </p>
          <p className={Styles["transcript-display"]}>
            Proctoring Calibration: {gazeRecorderStatus}
          </p>
          {gazeRecorderStatus === "calibrating" && (
            <div
              style={{
                fontSize: "12px",
                color: "#ffe066",
                fontWeight: 600
              }}
            >
              Please complete eye calibration prompt on this page.
            </div>
          )}
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
              pendingSubmissionRef.current = true;
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
      </div>
      {" "}
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
                  Interview Score
                </div>
                <div style={{ fontSize: "32px", fontWeight: "bold" }}>
                  {(() => {
                    // Handle different evaluation data structures
                    let score = null;

                    // Try quantitative.average_relevance_score (from interview_system.py)
                    if (evaluation?.quantitative?.average_relevance_score) {
                      score = evaluation.quantitative.average_relevance_score;
                    }
                    // Try quantitative_scores (from session_manager.py)
                    else if (evaluation?.quantitative_scores) {
                      if (typeof evaluation.quantitative_scores === "number") {
                        score = evaluation.quantitative_scores;
                      } else if (
                        typeof evaluation.quantitative_scores === "object"
                      ) {
                        // If it's an object, try to get average or overall score
                        score =
                          evaluation.quantitative_scores.average ||
                          evaluation.quantitative_scores.overall ||
                          Object.values(evaluation.quantitative_scores)[0];
                      }
                    }

                    // Convert to percentage if score is decimal (0-1 range)
                    if (score !== null) {
                      if (score <= 1) {
                        return `${Math.round(score * 100)}%`;
                      } else {
                        return `${Math.round(score)}%`;
                      }
                    }

                    return "85%"; // Fallback
                  })()}
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
                  Communication Score
                </div>
                <div style={{ fontSize: "32px", fontWeight: "bold" }}>
                  {(() => {
                    // Extract communication score from evaluation
                    let commScore = null;

                    // Try to get communication score from quantitative_scores
                    if (evaluation?.quantitative_scores?.communication) {
                      commScore = evaluation.quantitative_scores.communication;
                    }
                    // Fallback: check if it's stored differently
                    else if (evaluation?.quantitative?.communication) {
                      commScore = evaluation.quantitative.communication;
                    }

                    // Convert to percentage if score is decimal (0-1 range)
                    if (commScore !== null) {
                      if (commScore <= 1) {
                        return `${Math.round(commScore * 100)}%`;
                      } else {
                        return `${Math.round(commScore)}%`;
                      }
                    }

                    return "80%"; // Fallback
                  })()}
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
                  {/* TODO: Replace with actual proctoring score when model is developed */}
                  90%
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
                      {evaluation.quantitative.number_of_questions}
                      {" "}
                    </div>
                    {" "}
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
                    ))}
                  {" "}
                </div>
              </div>
            )}
            <div style={{ textAlign: "center" }}>
              <button
                className={Styles["back-to-dashboard"]}
                onClick={() => {
                  const isPracticeMode = location.state?.isPractice || false;
                  const redirectPath = isPracticeMode ? "/practice" : "/profile#applications";
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
                {location.state?.isPractice ? "Back to Practice" : "Go to Dashboard"}
              </button>
            </div>
            {" "}
          </div>
          {" "}
        </div>
      )}
      {" "}
    </div>
  );
}

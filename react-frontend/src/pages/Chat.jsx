import React, { useEffect, useState, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Styles from "./Chat.module.css";
import { FFmpeg } from "@ffmpeg/ffmpeg";
import { toBlobURL } from "@ffmpeg/util";
import io from "socket.io-client";
import Avatar from "../components/Avatar"; // Import the new Avatar component

// Removed formatTime function - no longer needed since we removed the 30-second timer

export default function Chat({ interviewId }) {
  // --- STATE MANAGEMENT ---
// Add this with your other refs
  const isTimerRunningRef = useRef(false);
  const [chatContent, setChatContent] = useState({});
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [interviewStatus, setInterviewStatus] = useState("starting");
  const [evaluation, setEvaluation] = useState(null);
  const [similarityScore, setSimilarityScore] = useState(null);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [isRecordingVideo, setIsRecordingVideo] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("idle");
  const [proctoringAlert, setProctoringAlert] = useState({
    active: false,
    message: "",
  });
  const [warningCount, setWarningCount] = useState(0);
  const [gazeDirection, setGazeDirection] = useState("Face Not Detected");
  const [gazeTimes, setGazeTimes] = useState({ Left: 0, Center: 0, Right: 0 });

  // Removed timeLeft state - using only silence detection now
  const [isTimerRunning, setIsTimerRunning] = useState(false);
  const [questionCount, setQuestionCount] = useState(0);
  const [silenceTimer, setSilenceTimer] = useState(0); // Track silence duration
  const silenceTimerRef = useRef(null);
  const lastSpeechTimeRef = useRef(Date.now());
  const [interviewElapsedTime, setInterviewElapsedTime] = useState(0); // Track total interview time
  const interviewStartTimeRef = useRef(null);
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false); // Track answer submission
  
  // Add state for progressive text display
  const [displayedText, setDisplayedText] = useState("");
  const [fullQuestionText, setFullQuestionText] = useState("");
  const typingIntervalRef = useRef(null);


  // --- REFS ---
  const videoRef = useRef(null);
  const recognitionRef = useRef(null);
  const currentUtteranceRef = useRef(null);
  const ffmpegRef = useRef(new FFmpeg());
  const stopPromiseResolver = useRef(null);
  const recordedChunksRef = useRef([]);
  const socketRef = useRef(null);
  const proctoringIntervalRef = useRef(null);
  const sessionIdRef = useRef(null);
  const interviewStartInitiated = useRef(false);
  // --- MODIFICATION --- Add refs for the timer and the latest transcript
  const timerRef = useRef(null);
  const transcriptRef = useRef("");
 

  // --- HOOKS ---
  const navigate = useNavigate();
  const location = useLocation();
  
  // Helper function to format elapsed time (MM:SS)
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
   

  // Add this hook to your component
useEffect(() => {
    isTimerRunningRef.current = isTimerRunning;
}, [isTimerRunning]);



  // --- PROCTORING FOR TAB/WINDOW SWITCHING (No changes needed) ---
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
            if (interviewStatus === 'active' && document.hasFocus() === false && !proctoringAlert.active) {
                const newWarningCount = warningCount + 1;
                setWarningCount(newWarningCount);
                setProctoringAlert({ active: true, message: `You have switched to another window. This is warning #${newWarningCount}. This action has been recorded.` });
                if (socketRef.current) {
                    socketRef.current.emit('proctoring_violation', { session_id: sessionIdRef.current, type: 'window_blur' });
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

  // --- LIVE PROCTORING & WEBSOCKETS (No changes needed) ---
  const startLiveProctoring = useCallback(() => {
    const currentSessionId = sessionIdRef.current;
    if (!currentSessionId || (socketRef.current && socketRef.current.connected))
      return;
    const socket = io("http://localhost:5000");
    socketRef.current = socket;
    socket.on("connect", () => {
      console.log("✅ WebSocket connected.");
      socket.emit("start_proctoring", { session_id: currentSessionId });

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
  }, []);

  // --- FACE REGISTRATION (No changes needed) ---
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
      setInterviewStatus("active");
    } catch (error) {
      console.error("Face registration error:", error);
      alert(`Could not register face: ${error.message}.`);
    }
  }, []);

  // --- ARCHIVAL VIDEO RECORDING & UPLOADING (No changes needed) ---
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
      setUploadStatus("success");
    } catch (error) {
      setUploadStatus("error");
      throw error;
    }
  }, []);

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
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
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
    
    // Check if coming from "Give Interview" button (URL will be /interview/start)
    const isDirectStart = interviewId === "start";
    
    if ((interviewId || isDirectStart) && interviewStatus === "starting") {
      // Get application ID from navigation state
      const applicationId = location.state?.applicationId;
      
      const token = localStorage.getItem("companyxyz-token");
      fetch(`${process.env.REACT_APP_API_URL}/api/interviews/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          application_id: applicationId,  // Pass the application ID
          cv_path: "uploads/cv/software_engineering_cv.pdf",
          jd_path: "uploads/jd/software_engineering_job_description.pdf",
          reference_paths: [
            "uploads/reference/Artificial Intelligence, Machine Learning, and Deep Learning.pdf",
          ],
        }),
      })
        .then((res) => (res.ok ? res.json() : Promise.reject(res.json())))
        .then((data) => {
          setSessionId(data.session_id);
          sessionIdRef.current = data.session_id;
          setSimilarityScore(data.similarity_score);
          setCurrentQuestion(data.initial_questions[0]);
          setInterviewStatus("registering");
        })
        .catch((err) => {
          console.error("Error starting interview:", err);
          setChatContent({
            0: { response: "⚠️ Error: Could not start the interview session." },
          });
          // Redirect back to profile on error
          setTimeout(() => navigate("/profile#applications"), 3000);
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
      if (videoRef.current && videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach((track) => track.stop());
      }
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
          )}% match. Let's begin.`,
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
    
    // Stop speech recognition
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {
        // Speech recognition already stopped
      }
    }
    setIsRecording(false);
    
    // Stop camera and all video tracks
    if (videoRef.current && videoRef.current.srcObject) {
      videoRef.current.srcObject.getTracks().forEach((track) => {
        track.stop();
      });
      videoRef.current.srcObject = null;
    }
    
    stopLiveProctoring(); 

    try {
      await stopAndUploadRecording();

      const token = localStorage.getItem("companyxyz-token");
      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/end`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const data = await response.json();
      if (!response.ok)
        throw new Error(data.error || "Failed to end interview");

      setInterviewStatus("completed");
      setEvaluation(data.evaluation);
      
      // Extract and update interview score from evaluation
      let extractedScore = null;
      
      // Handle different evaluation data structures
      if (data.evaluation?.quantitative?.average_relevance_score) {
        extractedScore = data.evaluation.quantitative.average_relevance_score;
      } else if (data.evaluation?.quantitative_scores) {
        if (typeof data.evaluation.quantitative_scores === 'number') {
          extractedScore = data.evaluation.quantitative_scores;
        } else if (typeof data.evaluation.quantitative_scores === 'object') {
          extractedScore = data.evaluation.quantitative_scores.average || 
                          data.evaluation.quantitative_scores.overall ||
                          Object.values(data.evaluation.quantitative_scores)[0];
        }
      }
      
      if (extractedScore !== null) {
        // Convert to percentage if score is decimal (0-1 range)
        const interviewScore = extractedScore <= 1 
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
                interview_score: interviewScore
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
      localStorage.setItem('interview-just-completed', 'true');
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
        const response = await fetch(
          `${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/answer`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ question: currentQuestion, answer: answer }),
          }
        );
        const data = await response.json();
        if (!response.ok)
          throw new Error(data.error || "Failed to submit answer");

        // Auto-end interview after 10 questions
        if (data.interview_complete || questionCount >= 10) {
          // Reset submitting state before ending
          setIsSubmittingAnswer(false);
          await endInterview();
        } else {
          // Increment question count for the NEXT question
          setQuestionCount(prev => prev + 1);
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
    [currentQuestion, interviewStatus, endInterview, questionCount]
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
          const timeSinceLastSpeech = (Date.now() - lastSpeechTimeRef.current) / 1000;
          setSilenceTimer(Math.floor(timeSinceLastSpeech));
          
          // Auto-submit after 5 seconds of silence
          if (timeSinceLastSpeech >= 5 && transcriptRef.current.trim().length > 0) {
            clearInterval(silenceTimerRef.current);
            setIsTimerRunning(false);
              
            if (recognitionRef.current && isRecording) {
              recognitionRef.current.stop();
            }
            setIsRecording(false);
            onSend(transcriptRef.current.trim());
            transcriptRef.current = "";
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
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.error("Speech Recognition API is not supported in this browser.");
        return;
    }

    // Don't set up recognition if interview is not in an active state
    if (interviewStatus !== "active" && interviewStatus !== "registering" && interviewStatus !== "starting") {
        return;
    }

    recognitionRef.current = new SpeechRecognition();
    const recognition = recognitionRef.current;
    
    // This variable will live inside the hook's closure and hold the text from previous segments.
    let finalizedText = '';
    
    // Keep track of current interview status in closure
    let currentInterviewStatus = interviewStatus;

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    // When a new recording segment STARTS, we update our finalizedText with the full transcript so far.
    recognition.onstart = () => {
        setIsRecording(true);
        finalizedText = transcriptRef.current;
    };

    // The 'onresult' handler now only needs to worry about the CURRENT segment's text.
    recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscriptForSegment = '';

        for (let i = 0; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscriptForSegment = event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        
        // Reset silence timer when speech is detected
        if (finalTranscriptForSegment || interimTranscript) {
            lastSpeechTimeRef.current = Date.now();
            setSilenceTimer(0);
        }
        
        // Combine the text from previous segments with the live text from the current one.
        const fullLiveTranscript = finalizedText + (finalTranscriptForSegment || interimTranscript);
        setInput(fullLiveTranscript);
        transcriptRef.current = fullLiveTranscript;
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
    };

    recognition.onend = () => {
        setIsRecording(false);
        
        // Only restart if timer is active AND interview is still active
        if (isTimerRunningRef.current && currentInterviewStatus === "active") {
            try {
              recognition.start();
            } catch (e) {
              // Could not restart recognition
            }
        }
    };

    return () => {
        currentInterviewStatus = "completed";
        try {
          recognition.stop();
        } catch (e) {
          // Already stopped
        }
    };

}, [interviewStatus]);

const startRecording = useCallback(() => {
    if (isSpeaking || isRecording || !recognitionRef.current) return;

    setInput("");
    transcriptRef.current = "";
    lastSpeechTimeRef.current = Date.now();
    setSilenceTimer(0);
    recognitionRef.current.start();
    setIsRecording(true);
}, [isSpeaking, isRecording]);
    

  const speakResponse = (text) => {
        if (!window.speechSynthesis || !text) return;

        if (isSpeaking) {
            window.speechSynthesis.cancel();
            // Clear any existing typing animation
            clearInterval(typingIntervalRef.current);
        }
        
        // Set full text and start progressive display
        setFullQuestionText(text);
        setDisplayedText(""); // Reset displayed text
        
        const utterance = new SpeechSynthesisUtterance(text);
        currentUtteranceRef.current = utterance;
        
        utterance.onstart = () => {
            setIsSpeaking(true);
            
            // Start progressive text animation
            let currentIndex = 0;
            const words = text.split(' ');
            const totalWords = words.length;
            
            // Estimate speech duration (average speaking rate: ~120 words per minute for natural speech)
            const estimatedDuration = (totalWords / 120) * 60 * 1000; // Convert to milliseconds
            // Use words for better pacing rather than characters
            const intervalDelay = estimatedDuration / words.length; // Time per word
            
            typingIntervalRef.current = setInterval(() => {
                if (currentIndex < words.length) {
                    // Display words progressively instead of characters for more natural flow
                    const wordsToShow = words.slice(0, currentIndex + 1).join(' ');
                    setDisplayedText(wordsToShow);
                    currentIndex++;
                } else {
                    clearInterval(typingIntervalRef.current);
                    setDisplayedText(text); // Ensure complete text is shown
                }
            }, Math.max(intervalDelay, 300)); // Minimum 300ms per word for natural reading pace
        };
        
        utterance.onend = () => {
            setIsSpeaking(false);
            currentUtteranceRef.current = null;
            // Clear typing animation and show full text
            clearInterval(typingIntervalRef.current);
            setDisplayedText(text); // Ensure full text is shown
            
            // Start silence detection after AI finishes speaking
            if (interviewStatus === 'active') {
                setSilenceTimer(0);
                lastSpeechTimeRef.current = Date.now();
                setIsTimerRunning(true);
                startRecording();
            }
        };
        
        utterance.onerror = () => {
            setIsSpeaking(false);
            currentUtteranceRef.current = null;
            clearInterval(typingIntervalRef.current);
            setDisplayedText(text); // Show full text on error
        };
        
        window.speechSynthesis.speak(utterance);
    };  // Automatically speak the first question
  useEffect(() => {
    if (
      interviewStatus === "active" &&
      currentQuestion &&
      !isSpeaking &&
      !currentUtteranceRef.current
    ) {
      setTimeout(() => {
        const initialMessage = `Your CV has a ${Math.round(
          similarityScore * 100
        )}% match. Let's begin. ${currentQuestion}`;
        speakResponse(initialMessage);
      }, 1000);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interviewStatus]);

  // Interview elapsed time tracker
  useEffect(() => {
    if (interviewStatus === "active" && interviewStartTimeRef.current) {
      const timer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - interviewStartTimeRef.current) / 1000);
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
      if (videoRef.current && videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach((track) => track.stop());
      }
    };
  }, [stopLiveProctoring]);

  // --- Interview Completion Camera Cleanup ---
  useEffect(() => {
    if (interviewStatus === "completed" || interviewStatus === "ending") {
      // Comprehensive camera and media cleanup
      const cleanup = () => {
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
          videoRef.current.removeAttribute('src');
          videoRef.current.load();
        }
        
        // Stop media recording
        if (mediaRecorder && mediaRecorder.state === 'recording') {
          mediaRecorder.stop();
        }
        
        // Stop speech synthesis
        if (window.speechSynthesis && window.speechSynthesis.speaking) {
          window.speechSynthesis.cancel();
        }
        
        // Stop speech recognition
        if (recognitionRef.current) {
          try {
            recognitionRef.current.stop();
            recognitionRef.current.abort();
          } catch (e) {
            // Already stopped
          }
        }
        
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
  }, [interviewStatus, stopLiveProctoring, mediaRecorder]);

  // --- RENDER LOGIC ---
  if (interviewStatus === "starting") {
    return (
      <div className={Styles.loadingContainer}>
        <div className={Styles.spinner}></div>
        <h3 style={{ marginTop: '20px', color: '#667eea', fontSize: '24px' }}>
          Preparing Your Interview
        </h3>
        <p style={{ color: '#666', maxWidth: '400px', textAlign: 'center', lineHeight: '1.6' }}>
          We're analyzing your CV and the job description to generate personalized questions...
        </p>
        <div style={{ marginTop: '15px', fontSize: '14px', color: '#999' }}>
          This usually takes 3-5 seconds
        </div>
      </div>
    );
  }

  if (interviewStatus === "registering") {
    return (
      <div className={Styles.registrationContainer}>
        <h2 className={Styles.registrationHeader}>
          Camera Setup & Security Check
        </h2>
        <p className={Styles.registrationSubheader}>
          For a fair evaluation, please close all other applications and browser tabs.
          <br />
          The interview will be conducted in fullscreen mode.
        </p>
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className={Styles.registrationVideo}
        />
        <button
          onClick={handleFaceRegistration}
          className={Styles.registerButton}
        >
          Register Face & Start Interview
        </button>
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
                <span className={Styles["question-counter"]}>Question {questionCount} of 10</span>
                <span className={Styles["time-elapsed"]}>⏱️ {formatTime(interviewElapsedTime)}</span>
              </div>
              {isTimerRunning && transcriptRef.current.trim().length > 0 && (
                <div className={Styles["silence-indicator"]}>
                  {silenceTimer < 5 ? `Speaking... ${5 - silenceTimer}s until auto-submit` : 'Auto-submitting...'}
                </div>
              )}
            </div>
        )}

        {proctoringAlert.active && (
          <div className={Styles.modalOverlay}>
            <div className={Styles.modal}>
              <h2>Warning! ({warningCount})</h2>
              <p>{proctoringAlert.message}</p>
              <button onClick={() => setProctoringAlert({ active: false, message: '' })}>Acknowledge</button>
            </div>
          </div>
        )}

        <div className={Styles["video-preview"]}>
          <video ref={videoRef} autoPlay muted playsInline />
        </div>

        {(gazeDirection === 'Left' || gazeDirection === 'Right') && (
          <div className={Styles["gaze-warning"]}>
            Please look at the center of the screen
          </div>
        )}

        <div className={Styles["avatar-container"]}>
          <Avatar />
        </div>

        <div className={Styles["controls-container"]}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <p className={Styles["transcript-display"]}>
              {isSubmittingAnswer ? "AI is thinking..." : 
               isRecording ? input || "Listening..." : 
               isTimerRunning ? "Ready to speak..." : 
               isSpeaking ? displayedText : 
               currentQuestion || "Waiting for next question..."}
            </p>
            {input && input.trim().length > 0 && (
              <div style={{ 
                fontSize: '12px', 
                color: 'rgba(255, 255, 255, 0.7)',
                fontStyle: 'italic' 
              }}>
                {input.split(' ').length} words • {input.length} characters
              </div>
            )}
          </div>
          
          <button
            className={`${Styles["mic-button"]} 
              ${isRecording ? Styles["mic-recording"] : ''} 
              ${isSpeaking || !isTimerRunning ? Styles["mic-disabled"] : ''}`}
            disabled={true}
          >
            {isRecording ? "Listening" : "Ready"}
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 14q.825 0 1.413-.588T14 12V6q0-.825-.588-1.413T12 4q-.825 0-1.413.588T10 6v6q0 .825.588 1.413T12 14Zm-1 7v-3.075q-2.6-.35-4.3-2.325T5 11H7q0 2.075 1.463 3.538T12 16q2.075 0 3.538-1.463T17 11h2q0 2.25-1.7 4.225T13 17.925V21h-2Z"/>
            </svg>
          </button>
          
          {/* Manual Send Button */}
          <button
            className={Styles["send-button"]}
            onClick={() => {
              if (input.trim().length > 0) {
                clearInterval(silenceTimerRef.current);
                setIsTimerRunning(false);
                if (recognitionRef.current && isRecording) {
                  recognitionRef.current.stop();
                }
                setIsRecording(false);
                onSend(input.trim());
                setInput("");
                transcriptRef.current = "";
              }
            }}
            disabled={!input || input.trim().length === 0 || isSpeaking || !isTimerRunning || isSubmittingAnswer}
          >
            {isSubmittingAnswer ? (
              <>
                <div className={Styles.spinner} style={{ width: '16px', height: '16px', borderWidth: '2px' }}></div>
                Submitting...
              </>
            ) : (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
                Send Answer
              </>
            )}
          </button>
        </div>

        {interviewStatus === "completed" && evaluation && (
          <div className={Styles["evaluation-overlay"]}>
            <div className={Styles["evaluation-container"]}>
              <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                <h2 style={{ 
                  color: '#27ae60', 
                  fontSize: '28px', 
                  marginBottom: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '10px'
                }}>
                  🎉 Interview Completed Successfully!
                </h2>
                <p style={{ color: '#666', fontSize: '16px' }}>
                  Your performance has been evaluated and submitted.
                </p>
                <p style={{ color: '#999', fontSize: '14px', marginTop: '10px' }}>
                  Review your results below
                </p>
                  </div>
              
              <div className={Styles["quantitative-metrics"]} style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '20px',
                marginBottom: '25px'
              }}>
                <div className={Styles["metric"]} style={{
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  padding: '20px',
                  borderRadius: '12px',
                  color: 'white',
                  textAlign: 'center',
                  boxShadow: '0 4px 15px rgba(102, 126, 234, 0.4)'
                }}>
                  <div style={{ fontSize: '14px', opacity: 0.9, marginBottom: '8px' }}>Interview Score</div>
                  <div style={{ fontSize: '32px', fontWeight: 'bold' }}>
                    {(() => {
                      // Handle different evaluation data structures
                      let score = null;
                      
                      // Try quantitative.average_relevance_score (from interview_system.py)
                      if (evaluation?.quantitative?.average_relevance_score) {
                        score = evaluation.quantitative.average_relevance_score;
                      }
                      // Try quantitative_scores (from session_manager.py)
                      else if (evaluation?.quantitative_scores) {
                        if (typeof evaluation.quantitative_scores === 'number') {
                          score = evaluation.quantitative_scores;
                        } else if (typeof evaluation.quantitative_scores === 'object') {
                          // If it's an object, try to get average or overall score
                          score = evaluation.quantitative_scores.average || 
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
                      
                      return '85%'; // Fallback
                    })()}
                  </div>
                </div>
                <div className={Styles["metric"]} style={{
                  background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                  padding: '20px',
                  borderRadius: '12px',
                  color: 'white',
                  textAlign: 'center',
                  boxShadow: '0 4px 15px rgba(245, 87, 108, 0.4)'
                }}>
                  <div style={{ fontSize: '14px', opacity: 0.9, marginBottom: '8px' }}>Proctoring Score</div>
                  <div style={{ fontSize: '32px', fontWeight: 'bold' }}>
                    {/* TODO: Replace with actual proctoring score when model is developed */}
                    90%
                  </div>
                </div>
                {evaluation.quantitative && evaluation.quantitative.number_of_questions && (
                  <div className={Styles["metric"]} style={{
                    background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                    padding: '20px',
                    borderRadius: '12px',
                    color: 'white',
                    textAlign: 'center',
                    boxShadow: '0 4px 15px rgba(79, 172, 254, 0.4)'
                  }}>
                    <div style={{ fontSize: '14px', opacity: 0.9, marginBottom: '8px' }}>Questions Answered</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold' }}>
                      {evaluation.quantitative.number_of_questions}
                  </div>
                </div>
              )}
              </div>
              
              {evaluation.qualitative_assessment && (
                <div style={{
                  background: '#f8f9fa',
                  padding: '20px',
                  borderRadius: '12px',
                  marginBottom: '20px',
                  border: '1px solid #e9ecef'
                }}>
                  <h4 style={{ 
                    color: '#2c3e50', 
                    marginBottom: '15px',
                    fontSize: '18px',
                    fontWeight: '600'
                  }}>
                    📋 Evaluation Summary
                  </h4>
                  <div className={Styles["qualitative-assessment"]} style={{
                    color: '#495057',
                    lineHeight: '1.6'
                  }}>
                {(evaluation.qualitative_assessment || '').split("\n").map((line, index) => (
                      <p key={index} style={{ marginBottom: '8px' }}>{line}</p>
                ))}
              </div>
                </div>
              )}
              
              <div style={{ textAlign: 'center' }}>
                <button 
                  className={Styles["back-to-dashboard"]} 
                  onClick={() => navigate("/profile#applications")}
                  style={{
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    color: 'white',
                    border: 'none',
                    padding: '15px 40px',
                    borderRadius: '8px',
                    fontSize: '16px',
                    fontWeight: '600',
                    cursor: 'pointer',
                    boxShadow: '0 4px 15px rgba(102, 126, 234, 0.4)',
                    transition: 'transform 0.2s, box-shadow 0.2s'
                  }}
                  onMouseOver={(e) => {
                    e.target.style.transform = 'translateY(-2px)';
                    e.target.style.boxShadow = '0 6px 20px rgba(102, 126, 234, 0.5)';
                  }}
                  onMouseOut={(e) => {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = '0 4px 15px rgba(102, 126, 234, 0.4)';
                  }}
                >
                Go to Dashboard
              </button>
              </div>
            </div>
          </div>
        )}
      </div>
  );
}
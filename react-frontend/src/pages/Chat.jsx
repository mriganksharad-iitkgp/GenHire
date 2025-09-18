import React, { useEffect, useState, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Styles from "./Chat.module.css";
import { FFmpeg } from "@ffmpeg/ffmpeg";
import { toBlobURL } from "@ffmpeg/util";
import io from "socket.io-client";
import Avatar from "../components/Avatar"; // Import the new Avatar component

// --- MODIFICATION --- Helper function to format seconds into MM:SS format
const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds < 10 ? '0' : ''}${remainingSeconds}`;
};

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

  const [timeLeft, setTimeLeft] = useState(10); 
  const [isTimerRunning, setIsTimerRunning] = useState(false);
  const [questionCount, setQuestionCount] = useState(0);


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

  // --- INTERVIEW LIFECYCLE MANAGEMENT (No changes needed here) ---
  useEffect(() => {
    if (interviewStartInitiated.current) return;
    interviewStartInitiated.current = true;
    if (interviewId && interviewStatus === "starting") {
      const token = localStorage.getItem("companyxyz-token");
      fetch(`${process.env.REACT_APP_API_URL}/api/interviews/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
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
        });
    }
  }, [interviewId, interviewStatus, navigate]);

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
      // --- MODIFICATION --- Initialize question count to 1 for the first question
      setQuestionCount(1);
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
      setChatContent((prev) => ({
        ...prev,
        [Object.keys(prev).length]: {
          response: "Interview ended. Finalizing your report...",
        },
      }));
    } catch (error) {
      console.error("Failed to end interview:", error);
      setInterviewStatus("active"); // Revert status on failure
    } finally {
      if (socketRef.current && socketRef.current.connected) {
        console.log("All tasks complete. Disconnecting socket now.");
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

      // Even if the answer is empty, we send it to proceed to the next question.
      console.log(`%cSending Answer: "${answer}"`, "color: #007bff; font-weight: bold;");

      setInput(""); 
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

        // --- MODIFICATION --- Auto-end interview after 10 questions
        if (data.interview_complete || questionCount >= 10) {
          console.log("Interview complete signal received or 10 questions answered. Ending interview.");
          await endInterview();
        } else {
          // --- MODIFICATION --- Increment question count for the NEXT question
          setQuestionCount(prev => prev + 1);
          setCurrentQuestion(data.next_question);
          speakResponse(data.next_question); // Automatically speak the next question
        }
      } catch (error) {
        console.error("Error in onSend:", error);
        speakResponse(`An error occurred: ${error.message}`);
      }
    },
    [currentQuestion, interviewStatus, endInterview, questionCount] // --- MODIFICATION --- Add questionCount dependency
  );

    // --- MODIFICATION --- Timer logic
    useEffect(() => {
      if (isTimerRunning) {
        timerRef.current = setInterval(() => {
          setTimeLeft((prevTime) => {
            if (prevTime <= 1) {
              clearInterval(timerRef.current);
              setIsTimerRunning(false);
              
              console.log("Time's up! Automatically sending answer.");
              
              if (recognitionRef.current && isRecording) {
                recognitionRef.current.stop();
              }
              setIsRecording(false);
              onSend(transcriptRef.current.trim()); // Send final transcript from ref
              transcriptRef.current = ""; // Reset ref
              
              return 0;
            }
            return prevTime - 1;
          });
        }, 1000);
      } else {
        clearInterval(timerRef.current);
      }

      return () => clearInterval(timerRef.current);
    }, [isTimerRunning, isRecording, onSend]);


// Replace your entire SpeechRecognition useEffect with this final version

useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.error("Speech Recognition API is not supported in this browser.");
        return;
    }

    recognitionRef.current = new SpeechRecognition();
    const recognition = recognitionRef.current;
    
    // This variable will live inside the hook's closure and hold the text from previous segments.
    let finalizedText = '';

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
        
        // Combine the text from previous segments with the live text from the current one.
        const fullLiveTranscript = finalizedText + (finalTranscriptForSegment || interimTranscript);
        setInput(fullLiveTranscript);
        transcriptRef.current = fullLiveTranscript;
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
    };

    recognition.onend = () => {
        console.log("Speech recognition service ended.");
        setIsRecording(false);
        
        // If the timer is still active, restart the service.
        if (isTimerRunningRef.current) {
            console.log("Timer is still active. Restarting recognition service...");
            recognition.start();
        }
    };

    return () => {
        recognition.stop();
    };

}, []);

const startRecording = useCallback(() => {
    if (isSpeaking || isRecording || !recognitionRef.current) return;

    console.log("🎤 Starting automatic recording for new answer...");
    setInput("");
    transcriptRef.current = ""; // This correctly resets the full answer for the new question
    recognitionRef.current.start();
    setIsRecording(true);
}, [isSpeaking, isRecording]);
    

  const speakResponse = (text) => {
        if (!window.speechSynthesis || !text) return;
        console.log(`%cAI Question: ${text}`, 'color: #28a745; font-weight: bold;');

        if (isSpeaking) {
            window.speechSynthesis.cancel();
        }
        const utterance = new SpeechSynthesisUtterance(text);
        currentUtteranceRef.current = utterance;
        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => {
            setIsSpeaking(false);
            currentUtteranceRef.current = null;
            // --- MODIFICATION --- Start timer and recording after AI finishes speaking
            if (interviewStatus === 'active') {
                console.log("AI finished speaking. Starting user response timer.");
                setTimeLeft(10);
                setIsTimerRunning(true);
                startRecording();
            }
        };
        utterance.onerror = () => {
            setIsSpeaking(false);
            currentUtteranceRef.current = null;
        };
        window.speechSynthesis.speak(utterance);
    };

  // Automatically speak the first question
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

  // --- Component Cleanup ---
  useEffect(() => {
    return () => {
      stopLiveProctoring();
      if (videoRef.current && videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach((track) => track.stop());
      }
    };
  }, [stopLiveProctoring]);

  // --- RENDER LOGIC (Loading and Registration are unchanged) ---
  if (interviewStatus === "starting") {
    return (
      <div className={Styles.loadingContainer}>
        <div className={Styles.spinner}></div>
        <p>Initializing Interview Session...</p>
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

  // --- MODIFICATION --- Updated main interview render
  return (
      <div className={Styles["page-container-fullscreen"]}>
        {/* --- MODIFICATION --- Timer display */}
        {isTimerRunning && (
            <div className={Styles["timer-display"]}>
                {formatTime(timeLeft)}
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
          <p className={Styles["transcript-display"]}>
              {/* --- MODIFICATION --- More descriptive transcript status */}
              {isRecording ? input || "Listening..." : isTimerRunning ? "Get ready..." : isSpeaking ? "AI is speaking..." : "Waiting for next question..."}
          </p>
          <button
            className={`${Styles["mic-button"]} 
              ${isRecording ? Styles["mic-recording"] : ''} 
              {/* --- MODIFICATION --- Mic is visually disabled when not user's turn */}
              ${isSpeaking || !isTimerRunning ? Styles["mic-disabled"] : ''}`}
            // --- MODIFICATION --- Button is now a visual indicator and cannot be clicked
            disabled={true}
          >
            {isRecording ? "Listening" : "Ready"}
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 14q.825 0 1.413-.588T14 12V6q0-.825-.588-1.413T12 4q-.825 0-1.413.588T10 6v6q0 .825.588 1.413T12 14Zm-1 7v-3.075q-2.6-.35-4.3-2.325T5 11H7q0 2.075 1.463 3.538T12 16q2.075 0 3.538-1.463T17 11h2q0 2.25-1.7 4.225T13 17.925V21h-2Z"/>
            </svg>
          </button>
          {/* --- MODIFICATION --- End Interview button has been removed */}
        </div>

        {interviewStatus === "completed" && evaluation && (
          <div className={Styles["evaluation-overlay"]}>
            <div className={Styles["evaluation-container"]}>
              <h3>Interview Evaluation</h3>
              {evaluation.quantitative && (
                <div className={Styles["quantitative-metrics"]}>
                  <div className={Styles["metric"]}>
                    <span>Average Score:</span>
                    <span>{Math.round(evaluation.quantitative.average_relevance_score * 100)}%</span>
                  </div>
                  <div className={Styles["metric"]}>
                    <span>Questions Answered:</span>
                    <span>{evaluation.quantitative.number_of_questions}</span>
                  </div>
                </div>
              )}
              <div className={Styles["qualitative-assessment"]}>
                {(evaluation.qualitative_assessment || '').split("\n").map((line, index) => (
                  <p key={index}>{line}</p>
                ))}
              </div>
              <button className={Styles["back-to-dashboard"]} onClick={() => navigate("/profile#applications")}>
                Return to Dashboard
              </button>
            </div>
          </div>
        )}
      </div>
  );
}
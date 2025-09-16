import React, { useEffect, useState, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Styles from "./Chat.module.css";
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { toBlobURL } from '@ffmpeg/util';
import io from 'socket.io-client';
import Avatar from "../components/Avatar"; // Import the new Avatar component

export default function Chat({ interviewId }) {
    // --- STATE MANAGEMENT ---
    const [chatContent, setChatContent] = useState({});
    const [input, setInput] = useState("");
    const [isRecording, setIsRecording] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    // const [speakingIndex, setSpeakingIndex] = useState(null); // No longer needed
    const [sessionId, setSessionId] = useState(null);
    const [currentQuestion, setCurrentQuestion] = useState("");
    const [interviewStatus, setInterviewStatus] = useState("starting"); // starting, registering, active, ending, completed
    const [evaluation, setEvaluation] = useState(null);
    const [similarityScore, setSimilarityScore] = useState(null);
    const [mediaRecorder, setMediaRecorder] = useState(null);
    const [isRecordingVideo, setIsRecordingVideo] = useState(false);
    const [uploadStatus, setUploadStatus] = useState('idle');
    // New state for proctoring alerts
    const [proctoringAlert, setProctoringAlert] = useState({ active: false, message: '' });
    const [warningCount, setWarningCount] = useState(0);
    // Add these new states
    // const [gazeDirection, setGazeDirection] = useState('Face Not Detected');
    // const [gazeTimes, setGazeTimes] = useState({ Left: 0, Center: 0, Right: 0 });

    // --- REFS ---
    const videoRef = useRef(null);
    // const targetRef = useRef(); // No longer needed for auto-scrolling chat
    const recognitionRef = useRef(null);
    const currentUtteranceRef = useRef(null);
    const ffmpegRef = useRef(new FFmpeg());
    const stopPromiseResolver = useRef(null);
    const recordedChunksRef = useRef([]);
    const socketRef = useRef(null);
    // const proctoringIntervalRef = useRef(null);
    const sessionIdRef = useRef(null);
    const interviewStartInitiated = useRef(false);

    // --- HOOKS ---
    const navigate = useNavigate();
    const location = useLocation();

    // --- PROCTORING FOR TAB/WINDOW SWITCHING ---
    useEffect(() => {
        const handleVisibilityChange = () => {
            if (document.hidden && interviewStatus === 'active') {
                const newWarningCount = warningCount + 1;
                setWarningCount(newWarningCount);
                setProctoringAlert({ active: true, message: `You have switched to another tab. This is warning #${newWarningCount}. This action has been recorded.` });
                if (socketRef.current) {
                    socketRef.current.emit('proctoring_violation', { session_id: sessionIdRef.current, type: 'visibility_change' });
                }
            }
        };

        const handleBlur = () => {
            // Check if the focus is lost from the main window, but ignore if the alert modal is active
            if (interviewStatus === 'active' && document.hasFocus() === false && !proctoringAlert.active) {
                const newWarningCount = warningCount + 1;
                setWarningCount(newWarningCount);
                setProctoringAlert({ active: true, message: `You have switched to another window. This is warning #${newWarningCount}. This action has been recorded.` });
                if (socketRef.current) {
                    socketRef.current.emit('proctoring_violation', { session_id: sessionIdRef.current, type: 'window_blur' });
                }
            }
        };

    // Connect socket ONLY when interview is active for tab-switching alerts
    if (interviewStatus === 'active' && !socketRef.current) {
        const socket = io('http://localhost:5000');
        socketRef.current = socket;
        socket.on('connect', () => {
            console.log('✅ WebSocket connected for violation monitoring.');
        });
        document.addEventListener("visibilitychange", handleVisibilityChange);
        window.addEventListener("blur", handleBlur);
    }

    return () => {
        document.removeEventListener("visibilitychange", handleVisibilityChange);
        window.removeEventListener("blur", handleBlur);
    };
}, [interviewStatus, proctoringAlert.active, warningCount]);


    // --- LIVE PROCTORING & WEBSOCKETS (Modified) ---
// const startLiveProctoring = useCallback(() => {
//     const currentSessionId = sessionIdRef.current;
//     if (!currentSessionId || (socketRef.current && socketRef.current.connected)) return;
    
//     const socket = io('http://localhost:5000');
//     socketRef.current = socket;
    
//     socket.on('connect', () => {
//         console.log('✅ WebSocket connected.');
//         socket.emit('start_proctoring', { session_id: currentSessionId });
        
//         // Listen for real-time gaze data from backend
//         socket.on('gaze_data', (data) => {
//             console.log('👁️ Gaze data received:', data);
//             setGazeDirection(data.gaze_direction);
//             setGazeTimes(data.gaze_times);
            
//             if (data.is_cheating_alert) {
//                 const newWarningCount = warningCount + 1;
//                 setWarningCount(newWarningCount);
//                 setProctoringAlert({ 
//                     active: true, 
//                     message: `Suspicious gaze detected! This is warning #${newWarningCount}.` 
//                 });
//                 // Note: Don't emit proctoring_violation here as it's already handled by backend
//             }
//         });

//         // Optimized frame capture - less frequent and smaller images
//         proctoringIntervalRef.current = setInterval(() => {
//             if (videoRef.current && 
//                 videoRef.current.srcObject && 
//                 videoRef.current.readyState === 4) {
                
//                 try {
//                     const canvas = document.createElement('canvas');
//                     // Reduce resolution for better performance
//                     const width = 320; // Reduced from full video width
//                     const height = 240; // Reduced from full video height
                    
//                     canvas.width = width;
//                     canvas.height = height;
                    
//                     const context = canvas.getContext('2d');
//                     context.drawImage(videoRef.current, 0, 0, width, height);
                    
//                     // Lower quality for faster transmission
//                     const imageData = canvas.toDataURL('image/jpeg', 0.3); // Reduced quality
                    
//                     console.log('📤 Sending frame to backend');
//                     socket.emit('proctoring_frame', { 
//                         session_id: currentSessionId, 
//                         image: imageData 
//                     });
//                 } catch (error) {
//                     console.error('❌ Error capturing frame:', error);
//                 }
//             }
//         }, 1000); // Increased interval to 1 second (from 200ms)
//     });
    
//     socket.on('disconnect', () => {
//         console.log('❌ WebSocket disconnected.');
//         if (proctoringIntervalRef.current) {
//             clearInterval(proctoringIntervalRef.current);
//             proctoringIntervalRef.current = null;
//         }
//     });
    
//     socket.on('connect_error', (error) => {
//         console.error('❌ Socket connection error:', error);
//     });
// }, [warningCount]); // Add warningCount as dependency

// const stopLiveProctoring = useCallback(() => {
//     // Only stop sending frames. Don't disconnect yet.
//     if (proctoringIntervalRef.current) {
//         clearInterval(proctoringIntervalRef.current);
//         proctoringIntervalRef.current = null;
//     }
// }, []);

    // --- FACE REGISTRATION ---
const handleFaceRegistration = useCallback(async () => {
    // Request fullscreen before proceeding
    const elem = document.documentElement;
    try {
        if (elem.requestFullscreen) {
            await elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) { /* Safari */
            await elem.webkitRequestFullscreen();
        } else if (elem.msRequestFullscreen) { /* IE11 */
            await elem.msRequestFullscreen();
        }
    } catch (err) {
        console.warn(`Fullscreen request failed: ${err.message}`);
        alert("Please enable fullscreen mode to continue the interview.");
        return;
    }

    const currentSessionId = sessionIdRef.current;
    if (!videoRef.current || !currentSessionId || videoRef.current.readyState < 3) {
        alert("Webcam not ready or session not started.");
        return;
    }
    
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const context = canvas.getContext('2d');
    context.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    const imageData = canvas.toDataURL('image/jpeg');
    
    try {
        const token = localStorage.getItem("companyxyz-token");
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/register-face`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ image: imageData }),
        });
        
        if (!response.ok) throw new Error((await response.json()).message || 'Face registration failed.');
        
        console.log("✅ Face registered successfully, starting live proctoring...");
        
        // IMPORTANT: Start live proctoring AFTER successful face registration
        // startLiveProctoring();
        
        setInterviewStatus("active");
    } catch (error) {
        console.error("Face registration error:", error);
        alert(`Could not register face: ${error.message}.`);
    }
}, []); 

    // --- ARCHIVAL VIDEO RECORDING & UPLOADING (No changes needed here) ---
    const uploadRecording = useCallback(async (blob) => {
        const currentSessionId = sessionIdRef.current;
        if (!currentSessionId) throw new Error("Session ID not available.");
        setUploadStatus('uploading');
        const ffmpeg = ffmpegRef.current;
        try {
            if (!ffmpeg.loaded) {
                const baseURL = 'https://unpkg.com/@ffmpeg/core@0.12.6/dist/umd';
                await ffmpeg.load({
                    coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
                    wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
                });
            }
            await ffmpeg.writeFile('input.webm', new Uint8Array(await blob.arrayBuffer()));
            await ffmpeg.exec(['-i', 'input.webm', '-c', 'copy', 'output.mp4']);
            const data = await ffmpeg.readFile('output.mp4');
            const formData = new FormData();
            formData.append('recording', new Blob([data.buffer], { type: 'video/mp4' }), `interview_${currentSessionId}.mp4`);
            const token = localStorage.getItem("companyxyz-token");
            const response = await fetch(`${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/upload-recording`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData,
            });
            if (!response.ok) throw new Error((await response.json()).error || "Upload failed");
            setUploadStatus('success');
        } catch (error) {
            setUploadStatus('error');
            throw error;
        }
    }, []);

    const stopAndUploadRecording = useCallback(() => {
        return new Promise((resolve, reject) => {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                stopPromiseResolver.current = { resolve, reject };
                mediaRecorder.stop();
            } else {
                resolve();
            }
        });
    }, [mediaRecorder]);

    const startWebcamAndArchivalRecording = useCallback(async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        if (videoRef.current) videoRef.current.srcObject = stream;
        
        // DON'T start live proctoring here - it will be started after face registration
        // startLiveProctoring(); // REMOVE THIS LINE
        
        const recorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunksRef.current.push(e.data);
        };
        recorder.onstop = async () => {
            setIsRecordingVideo(false);
            const blob = new Blob(recordedChunksRef.current, { type: 'video/webm' });
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
}, [uploadRecording]);

    // --- INTERVIEW LIFECYCLE MANAGEMENT (No changes needed here) ---
    useEffect(() => {
        if (interviewStartInitiated.current) return;
        interviewStartInitiated.current = true;
        if (interviewId && interviewStatus === "starting") {
            const token = localStorage.getItem("companyxyz-token");
            fetch(`${process.env.REACT_APP_API_URL}/api/interviews/start`, {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify({
                    cv_path: "uploads/cv/Data Science_resume_juanjosecarin.pdf",
                    jd_path: "uploads/jd/Data_Scientist_Job_Description.pdf",
                    reference_paths: ["uploads/reference/Artificial Intelligence, Machine Learning, and Deep Learning.pdf"]
                }),
            })
            .then(res => res.ok ? res.json() : Promise.reject(res.json()))
            .then(data => {
                setSessionId(data.session_id);
                sessionIdRef.current = data.session_id;
                setSimilarityScore(data.similarity_score);
                setCurrentQuestion(data.initial_questions[0]);
                setInterviewStatus("registering");
            })
            .catch(err => {
                console.error("Error starting interview:", err);
                setChatContent({ 0: { response: "⚠️ Error: Could not start the interview session." } });
            });
        }
    }, [interviewId, interviewStatus, navigate]);

    useEffect(() => {
        const setupWebcam = async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                }
            } catch (err) {
                console.error("Webcam access error:", err);
                alert("Could not access the camera. Please check your browser permissions and ensure your camera is not in use by another application. Redirecting to the dashboard.");
                navigate("/profile#applications");
            }
        };

        if (interviewStatus === 'registering' && (!videoRef.current || !videoRef.current.srcObject)) {
            setupWebcam();
        }

        if (interviewStatus === "active" && !isRecordingVideo) {
            if (videoRef.current && videoRef.current.srcObject) {
                videoRef.current.srcObject.getTracks().forEach(track => track.stop());
            }
            startWebcamAndArchivalRecording();
            setChatContent({
                0: { response: `Your CV has a ${Math.round(similarityScore * 100)}% match. Let's begin.` },
                1: { response: currentQuestion }
            });
        }
    }, [interviewStatus, isRecordingVideo, startWebcamAndArchivalRecording, similarityScore, currentQuestion, navigate]);

    const endInterview = useCallback(async () => {
    const currentSessionId = sessionIdRef.current;
    if (!currentSessionId || interviewStatus !== "active" || uploadStatus === 'uploading') return;

    setInterviewStatus("ending");
    // stopLiveProctoring(); // Now this only stops sending frames

    try {
        // 1. First, complete all async operations
        await stopAndUploadRecording();

        // 2. Then, notify the backend that the interview is over
        const token = localStorage.getItem("companyxyz-token");
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/end`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to end interview');

        setInterviewStatus("completed");
        setEvaluation(data.evaluation);
        setChatContent(prev => ({ ...prev, [Object.keys(prev).length]: { response: "Interview ended. Finalizing your report..." } }));

    } catch (error) {
        console.error("Failed to end interview:", error);
        setInterviewStatus("active"); // Revert status on failure
    } finally {
        // 3. Finally, disconnect the socket as the very last step
        if (socketRef.current && socketRef.current.connected) {
            console.log("All tasks complete. Disconnecting socket now.");
            socketRef.current.disconnect();
        }
    }
}, [interviewStatus, uploadStatus, stopAndUploadRecording]);
    
    const onSend = useCallback(async (userAnswer) => { // Modified to accept answer directly
        const currentSessionId = sessionIdRef.current;
        const answer = userAnswer.trim();
        if (answer === "" || !currentQuestion || !currentSessionId || interviewStatus !== "active") {
            return;
        }
        
        console.log(`%cUser Answer: ${answer}`, 'color: #007bff; font-weight: bold;');

        // We don't need to display the user's query in the new UI
        // const newChatContent = { ...chatContent };
        // const newIndex = Object.keys(newChatContent).length;
        // newChatContent[newIndex] = { query: answer, response: "Analyzing..." };
        // setChatContent(newChatContent);
        setInput(""); // Clear the transcript
        try {
            const token = localStorage.getItem("companyxyz-token");
            const response = await fetch(`${process.env.REACT_APP_API_URL}/api/interviews/${currentSessionId}/answer`, {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({ question: currentQuestion, answer: answer }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Failed to submit answer");
            
            if (data.interview_complete) {
                await endInterview();
            } else {
                setCurrentQuestion(data.next_question);
                speakResponse(data.next_question); // Automatically speak the next question
            }
            // We don't need to update chatContent anymore
            // setChatContent(updatedChatContent);
        } catch (error) {
            console.error("Error in onSend:", error);
            speakResponse(`An error occurred: ${error.message}`); // Speak the error
        }
    }, [currentQuestion, interviewStatus, endInterview]);

    // --- SPEECH RECOGNITION & SYNTHESIS (Modified) ---
    // --- SPEECH RECOGNITION & SYNTHESIS (Modified) ---
    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false; // Important for auto-stop
            recognitionRef.current.interimResults = true; // Show live transcript
            recognitionRef.current.lang = "en-US";

            recognitionRef.current.onresult = (event) => {
                let finalTranscript = '';
                for (let i = 0; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        setInput(event.results[i][0].transcript); // Update live transcript
                    }
                }
                if (finalTranscript) {
                    setInput(finalTranscript);
                    onSend(finalTranscript); // Automatically send final transcript
}
        };

            recognitionRef.current.onerror = (event) => console.error("Speech recognition error", event);
            recognitionRef.current.onend = () => setIsRecording(false);
        }
    }, [onSend]);

    const handleVoiceInput = useCallback(() => {
        if (isSpeaking) return; // Prevent any action while AI is speaking

        const recognition = recognitionRef.current;
        if (!recognition) return;

        if (isRecording) {
            // --- STOP RECORDING ---
            recognition.stop();
            setIsRecording(false);
            // Send the final accumulated transcript after a short delay to ensure state updates
            setTimeout(() => {
                if (input.trim()) {
                    onSend(input);
                }
            }, 100);
        } else {
            // --- START RECORDING ---
            setInput(""); // Clear previous transcript
            recognition.start();
            setIsRecording(true);
        }
    }, [isRecording, isSpeaking, input, onSend]); // Add dependencies

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
        };
        utterance.onerror = () => {
            setIsSpeaking(false);
            currentUtteranceRef.current = null;
        };
        window.speechSynthesis.speak(utterance);
    };

    // Automatically speak the first question
    useEffect(() => {
        if (interviewStatus === "active" && currentQuestion && !isSpeaking && !currentUtteranceRef.current) {
             // A small delay to ensure the UI transition is smooth
            setTimeout(() => {
                const initialMessage = `Your CV has a ${Math.round(similarityScore * 100)}% match. Let's begin. ${currentQuestion}`;
                speakResponse(initialMessage);
            }, 1000);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [interviewStatus]);


    // --- Component Cleanup ---
    useEffect(() => {
        return () => {
            // stopLiveProctoring();
            if (videoRef.current && videoRef.current.srcObject) {
                videoRef.current.srcObject.getTracks().forEach(track => track.stop());
            }
        };
    }, []);


    // --- RENDER LOGIC (Modified) ---
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
                <h2 className={Styles.registrationHeader}>Camera Setup & Security Check</h2>
                <p className={Styles.registrationSubheader}>
                    For a fair evaluation, please close all other applications and browser tabs.
                    <br />
                    The interview will be conducted in fullscreen mode.
                </p>
                <video ref={videoRef} autoPlay muted playsInline className={Styles.registrationVideo} />
                <button onClick={handleFaceRegistration} className={Styles.registerButton}>
                    Register Face & Start Interview
                </button>
            </div>
        );
    }

    return (
        <div className={Styles["page-container-fullscreen"]}>
            {/* Proctoring Warning Modal */}
            {proctoringAlert.active && (
                <div className={Styles.modalOverlay}>
                    <div className={Styles.modal}>
                        <h2>Warning! ({warningCount})</h2>
                        <p>{proctoringAlert.message}</p>
                        <button onClick={() => setProctoringAlert({ active: false, message: '' })}>Acknowledge</button>
                    </div>
                </div>
            )}

            {/* The small video preview for the active interview state */}
            <div className={Styles["video-preview"]}>
                <video ref={videoRef} autoPlay muted playsInline />
            </div>

            {/* Gaze Direction Warning */}
            {/* {console.log(gazeDirection, gazeTimes)}
            {(gazeDirection === 'Left' || gazeDirection === 'Right') && (
                <div className={Styles["gaze-warning"]}>
                    Please look at the center of the screen
                </div>
            )} */}

            {/* Main Avatar View */}
            <div className={Styles["avatar-container"]}>
                <Avatar />
            </div>

            {/* Controls and Transcript */}
            <div className={Styles["controls-container"]}>
                <p className={Styles["transcript-display"]}>
                    {isRecording ? input || "Listening..." : isSpeaking ? "AI is speaking..." : "Press the button to speak"}
                </p>
                <button
                    className={`${Styles["mic-button"]} ${isRecording ? Styles["mic-recording"] : ''} ${isSpeaking ? Styles["mic-disabled"] : ''}`}
                    onClick={handleVoiceInput}
                    disabled={isSpeaking || isRecording}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 14q.825 0 1.413-.588T14 12V6q0-.825-.588-1.413T12 4q-.825 0-1.413.588T10 6v6q0 .825.588 1.413T12 14Zm-1 7v-3.075q-2.6-.35-4.3-2.325T5 11H7q0 2.075 1.463 3.538T12 16q2.075 0 3.538-1.463T17 11h2q0 2.25-1.7 4.225T13 17.925V21h-2Z"/></svg>
                </button>
                {interviewStatus === "active" && (
                    <button className={Styles["end-interview-btn-bottom"]} onClick={endInterview} disabled={uploadStatus === 'uploading'}>
                        {uploadStatus === 'uploading' ? 'Saving...' : 'End Interview'}
                    </button>
                )}
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
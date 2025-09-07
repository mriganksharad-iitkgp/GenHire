import React, { useEffect, useState, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Styles from "./Chat.module.css";
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { toBlobURL } from '@ffmpeg/util';
import io from 'socket.io-client';

export default function Chat({ interviewId }) {
    // --- STATE MANAGEMENT ---
    const [chatContent, setChatContent] = useState({});
    const [input, setInput] = useState("");
    const [isRecording, setIsRecording] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [speakingIndex, setSpeakingIndex] = useState(null);
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


    // --- REFS ---
    const videoRef = useRef(null);
    const targetRef = useRef();
    const recognitionRef = useRef(null);
    const currentUtteranceRef = useRef(null);
    const ffmpegRef = useRef(new FFmpeg());
    const stopPromiseResolver = useRef(null);
    const recordedChunksRef = useRef([]);
    const socketRef = useRef(null);
    const proctoringIntervalRef = useRef(null);
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

        if (interviewStatus === 'active') {
            document.addEventListener("visibilitychange", handleVisibilityChange);
            window.addEventListener("blur", handleBlur);
        }

        return () => {
            document.removeEventListener("visibilitychange", handleVisibilityChange);
            window.removeEventListener("blur", handleBlur);
        };
    }, [interviewStatus, proctoringAlert.active, warningCount]);


    // --- LIVE PROCTORING & WEBSOCKETS (No changes needed here) ---
    const startLiveProctoring = useCallback(() => {
        const currentSessionId = sessionIdRef.current;
        if (!currentSessionId || (socketRef.current && socketRef.current.connected)) return;

        console.log(`Attempting to connect to WebSocket for session: ${currentSessionId}`);
        const socket = io('http://localhost:5000');
        socketRef.current = socket;
        socket.on('connect', () => {
            console.log('✅ WebSocket connected.');
            socket.emit('start_proctoring', { session_id: currentSessionId });
            proctoringIntervalRef.current = setInterval(() => {
                if (videoRef.current && videoRef.current.srcObject && videoRef.current.readyState === 4) {
                    const canvas = document.createElement('canvas');
                    canvas.width = videoRef.current.videoWidth;
                    canvas.height = videoRef.current.videoHeight;
                    const context = canvas.getContext('2d');
                    context.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
                    const imageData = canvas.toDataURL('image/jpeg', 0.5);
                    socket.emit('proctoring_frame', { session_id: currentSessionId, image: imageData });
                }
            }, 2000);
        });
        socket.on('disconnect', () => {
            console.log('❌ WebSocket disconnected.');
            if (proctoringIntervalRef.current) clearInterval(proctoringIntervalRef.current);
        });
    }, []);

    const stopLiveProctoring = useCallback(() => {
        if (proctoringIntervalRef.current) {
            clearInterval(proctoringIntervalRef.current);
            proctoringIntervalRef.current = null;
        }
        if (socketRef.current && socketRef.current.connected) {
            socketRef.current.disconnect();
        }
    }, []);

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
            formData.append('video', new Blob([data.buffer], { type: 'video/mp4' }), `interview_${currentSessionId}.mp4`);
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
            startLiveProctoring();
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
    }, [startLiveProctoring, uploadRecording]);

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
                     cv_path: "uploads/cv/PeterConnollyResume-2.pdf",
                     jd_path: "uploads/jd/JD1.pdf",
                     reference_path: "Eric Ries - The Lean Startup.pdf",
                }),
            })
            .then(res => res.ok ? res.json() : Promise.reject(res.json()))
            .then(data => {
                setSessionId(data.session_id);
                sessionIdRef.current = data.session_id;
                setSimilarityScore(data.similarity_score);
                setCurrentQuestion(data.initial_questions[0]);
                setInterviewStatus("registering");
                setChatContent({ 0: { response: "Welcome! To begin, please position your face in the camera frame and click 'Register Face'." } });
            })
            .catch(err => {
                console.error("Error starting interview:", err);
                setChatContent({ 0: { response: "⚠️ Error: Could not start the interview session." } });
            });
        }
    }, [interviewId, interviewStatus, navigate]);

    useEffect(() => {
        if (interviewStatus === 'registering' && (!videoRef.current || !videoRef.current.srcObject)) {
            navigator.mediaDevices.getUserMedia({ video: true })
                .then(stream => { if (videoRef.current) videoRef.current.srcObject = stream; })
                .catch(err => console.error("Webcam error:", err));
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
    }, [interviewStatus, isRecordingVideo, startWebcamAndArchivalRecording, similarityScore, currentQuestion]);

    const endInterview = useCallback(async () => {
        const currentSessionId = sessionIdRef.current;
        if (!currentSessionId || interviewStatus !== "active" || uploadStatus === 'uploading') return;
        setInterviewStatus("ending");
        stopLiveProctoring();
        try {
            await stopAndUploadRecording();
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
            setInterviewStatus("active");
        }
    }, [interviewStatus, uploadStatus, stopAndUploadRecording, stopLiveProctoring]);
    
    const onSend = useCallback(async (e) => {
        e.preventDefault();
        const currentSessionId = sessionIdRef.current;
        const answer = input.trim();
        if (answer === "" || !currentQuestion || !currentSessionId || interviewStatus !== "active") {
            setInput("");
            return;
        }
        const newChatContent = { ...chatContent };
        const newIndex = Object.keys(newChatContent).length;
        newChatContent[newIndex] = { query: answer, response: "Analyzing..." };
        setChatContent(newChatContent);
        setInput("");
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
            const updatedChatContent = { ...newChatContent };
            if (data.evaluation && data.evaluation.feedback) {
                updatedChatContent[newIndex] = { query: answer, evaluation: data.evaluation };
            }
            if (data.interview_complete) {
                await endInterview();
            } else {
                setCurrentQuestion(data.next_question);
                updatedChatContent[newIndex + 1] = { response: data.next_question };
            }
            setChatContent(updatedChatContent);
        } catch (error) {
            console.error("Error in onSend:", error);
            setChatContent(prev => ({ ...prev, [Object.keys(prev).length]: { response: `⚠️ Error: ${error.message}` } }));
        }
    }, [chatContent, input, currentQuestion, interviewStatus, endInterview]);

    // --- SPEECH RECOGNITION & SYNTHESIS (No changes needed here) ---
    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false;
            recognitionRef.current.interimResults = false;
            recognitionRef.current.lang = "en-US";
            recognitionRef.current.onresult = (event) => setInput(event.results[0][0].transcript);
            recognitionRef.current.onerror = (event) => console.error("Speech recognition error", event);
            recognitionRef.current.onend = () => setIsRecording(false);
        }
    }, []);

    const handleVoiceInput = () => {
        if (isRecording) {
            recognitionRef.current.stop();
        } else {
            recognitionRef.current.start();
            setIsRecording(true);
        }
    };

    const toggleSpeech = (idx, text) => {
        if (!window.speechSynthesis) return;
        if (isSpeaking && speakingIndex === idx) {
            window.speechSynthesis.cancel();
            setIsSpeaking(false); setSpeakingIndex(null);
            return;
        }
        if (isSpeaking) {
            window.speechSynthesis.cancel();
        }
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.onstart = () => { setIsSpeaking(true); setSpeakingIndex(idx); };
        utterance.onend = () => { setIsSpeaking(false); setSpeakingIndex(null); };
        utterance.onerror = () => { setIsSpeaking(false); setSpeakingIndex(null); };
        window.speechSynthesis.speak(utterance);
    };

    // --- Component Cleanup ---
    useEffect(() => {
        return () => {
            stopLiveProctoring();
            if (videoRef.current && videoRef.current.srcObject) {
                videoRef.current.srcObject.getTracks().forEach(track => track.stop());
            }
        };
    }, [stopLiveProctoring]);


    // --- RENDER LOGIC ---
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
        <div className={Styles["page-container"]}>
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

            <div className={Styles["chat-box-container"]}>
                <div className={Styles["chat-header"]}>
                    <h2>AI Interview Session {sessionId ? `#${sessionId.substring(0, 8)}` : ""}</h2>
                    {isRecordingVideo && <div className={Styles.recordingIndicator}><div className={Styles.recordingDot}></div>Live Proctoring Active</div>}
                    {interviewStatus === "active" && (
                        <button className={Styles["end-interview-btn"]} onClick={endInterview} disabled={uploadStatus === 'uploading'}>
                            {uploadStatus === 'uploading' ? 'Saving...' : 'End Interview'}
                        </button>
                    )}
                </div>
                <div className={Styles["chat-content"]}>
                    <div className={Styles["messages-list"]} ref={targetRef}>
                        {Object.keys(chatContent).length > 0 ? (
                            Object.keys(chatContent).map((idx) => {
                                const pair = chatContent[idx];
                                return (
                                    <React.Fragment key={idx}>
                                        {pair.query && (
                                            <div className={`${Styles["message-box"]} ${Styles["user"]}`}>
                                                <img src={"/android-chrome-192x192.png"} alt="User Avatar" />
                                                <div className={Styles["message"]}>{pair.query}</div>
                                            </div>
                                        )}
                                        {pair.evaluation && (
                                            <div className={`${Styles["message-box"]} ${Styles["evaluation"]}`}>
                                                <div className={Styles["evaluation-content"]}>
                                                    <div className={Styles["score"]}>
                                                        Relevance: {Math.round(pair.evaluation.relevance_score * 100)}%
                                                    </div>
                                                    <div className={Styles["feedback"]}>{pair.evaluation.feedback}</div>
                                                </div>
                                            </div>
                                        )}
                                        {pair.response && (
                                            <div className={`${Styles["message-box"]} ${Styles["gpt"]}`}>
                                                <img src={"/android-chrome-512x512.png"} alt="AI Avatar" />
                                                <div className={Styles["message"]}>
                                                    {(pair.response || '').split("\n").map((line, index) => (
                                                        <React.Fragment key={index}>{line}<br /></React.Fragment>
                                                    ))}
                                                     <div className={Styles["message-actions"]}>
                                                        <button
                                                            className={isSpeaking && speakingIndex === idx ? Styles["btn-stop"] : Styles["btn-speak"]}
                                                            onClick={() => toggleSpeech(idx, pair.response)}
                                                        >
                                                            {isSpeaking && speakingIndex === idx ? "Stop" : "Speak"}
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </React.Fragment>
                                );
                            })
                        ) : (
                            <div className={Styles["loading-chat"]}>Waiting for first question...</div>
                        )}
                    </div>
                </div>
                <div className={Styles["input-area"]}>
                    <form onSubmit={onSend}>
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder={interviewStatus === "active" ? "Type your answer here..." : "Interview has ended."}
                            disabled={interviewStatus !== "active"}
                            className={Styles["chat-input"]}
                        />
                        <div className={Styles["input-actions"]}>
                            <button type="button" className={Styles["voice-input-button"]} onClick={handleVoiceInput} disabled={interviewStatus !== "active" || isRecording}>
                                {isRecording ? "Listening..." : "Voice"}
                            </button>
                            <button type="submit" className={Styles["send-button"]} disabled={interviewStatus !== "active" || !input.trim()}>
                                Send
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            {interviewStatus === "completed" && evaluation && (
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
                    <button className={Styles["back-to-dashboard"]} onClick={() => navigate("/dashboard")}>
                        Return to Dashboard
                    </button>
                </div>
            )}
        </div>
    );
}
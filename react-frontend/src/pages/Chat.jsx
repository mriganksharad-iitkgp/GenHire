import React, { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Styles from "./Chat.module.css";
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { toBlobURL } from '@ffmpeg/util';

export default function Chat({ interviewId }) {
    // --- STATE MANAGEMENT ---
    const [chatContent, setChatContent] = useState({});
    const [input, setInput] = useState("");
    const [isRecording, setIsRecording] = useState(false); // For voice input
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [speakingIndex, setSpeakingIndex] = useState(null);
    const [sessionId, setSessionId] = useState(null);
    const [currentQuestion, setCurrentQuestion] = useState("");
    const [interviewStatus, setInterviewStatus] = useState("starting"); // starting, active, ending, completed
    const [evaluation, setEvaluation] = useState(null);
    const [similarityScore, setSimilarityScore] = useState(null);
    const [mediaRecorder, setMediaRecorder] = useState(null);
    const [isRecordingVideo, setIsRecordingVideo] = useState(false); // For webcam
    const [uploadStatus, setUploadStatus] = useState('idle'); // idle, uploading, success, error

    // --- REFS ---
    const videoRef = useRef(null);
    const targetRef = useRef(); // For scrolling chat
    const recognitionRef = useRef(null); // For SpeechRecognition API
    const currentUtteranceRef = useRef(null); // For SpeechSynthesis API
    const ffmpegRef = useRef(new FFmpeg());
    const stopPromiseResolver = useRef(null); // To handle async stop/upload logic
    
    // **FIX**: Use a ref for recorded chunks to avoid stale state in the onstop event handler.
    const recordedChunksRef = useRef([]);

    // --- HOOKS ---
    const navigate = useNavigate();

    // --- CORE FUNCTIONS for VIDEO RECORDING & UPLOADING ---

    /**
     * Converts the recorded WEBM blob to MP4 using FFmpeg and uploads it to the server.
     * Wrapped in useCallback to ensure it has the latest `sessionId` and is stable.
     */
    const uploadRecording = useCallback(async (blob) => {
        if (!sessionId) {
            console.error("Upload cannot proceed without a session ID.");
            throw new Error("Session ID is not available.");
        }
        
        console.log("Starting video conversion and upload...");
        const ffmpeg = ffmpegRef.current;
        try {
            // Load FFmpeg if it's not already loaded
            if (!ffmpeg.loaded) {
                const baseURL = 'https://unpkg.com/@ffmpeg/core@0.12.6/dist/umd';
                await ffmpeg.load({
                    coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
                    wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
                });
            }

            // Perform the conversion from webm to mp4
            await ffmpeg.writeFile('input.webm', new Uint8Array(await blob.arrayBuffer()));
            await ffmpeg.exec(['-i', 'input.webm', '-vcodec', 'libx264', '-crf', '28', '-preset', 'ultrafast', 'output.mp4']);
            const data = await ffmpeg.readFile('output.mp4');
            
            // Prepare and send the form data
            const formData = new FormData();
            formData.append('video', new Blob([data.buffer], { type: 'video/mp4' }), `interview_${sessionId}.mp4`);
            
            const token = localStorage.getItem("companyxyz-token");
            const response = await fetch(`http://localhost:5000/api/interviews/${sessionId}/upload-recording`, {
                method: 'POST',
                headers: { 'Authorization': token },
                body: formData,
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || "Upload failed");
            }

            console.log("✅ Recording uploaded successfully!");

            // Clean up FFmpeg files
            await ffmpeg.deleteFile('input.webm');
            await ffmpeg.deleteFile('output.mp4');

        } catch (error) {
            console.error("Error during recording conversion or upload:", error);
            throw error; // Re-throw to be caught by the caller
        }
    }, [sessionId]); // Dependency on sessionId ensures it's not stale

    /**
     * Stops the MediaRecorder and returns a Promise that resolves when the upload is complete.
     */
    const stopAndUploadRecording = useCallback(() => {
        return new Promise((resolve, reject) => {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                // Store the promise's resolve/reject functions to be called in onstop
                stopPromiseResolver.current = { resolve, reject };
                mediaRecorder.stop();
                setIsRecordingVideo(false);
                // Stop webcam tracks
                if (videoRef.current && videoRef.current.srcObject) {
                    videoRef.current.srcObject.getTracks().forEach(track => track.stop());
                }
            } else {
                resolve(); // No recorder active, resolve immediately.
            }
        });
    }, [mediaRecorder]);

    /**
     * Initializes the webcam and sets up the MediaRecorder.
     * This is where the main fix is applied.
     */
    const startWebcamRecording = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            if (videoRef.current) videoRef.current.srcObject = stream;
    
            const recorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
    
            // **FIX**: Push data chunks to the ref's `.current` array.
            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    recordedChunksRef.current.push(e.data);
                }
            };
    
            // This `onstop` handler now correctly uses the ref to access all chunks.
            recorder.onstop = async () => {
                const blob = new Blob(recordedChunksRef.current, { type: 'video/webm' });
                
                if (blob.size > 0 && stopPromiseResolver.current) {
                    try {
                        await uploadRecording(blob);
                        stopPromiseResolver.current.resolve(); // Signal success
                    } catch (err) {
                        stopPromiseResolver.current.reject(err); // Signal error
                    }
                } else if (stopPromiseResolver.current) {
                    stopPromiseResolver.current.resolve(); // No data, but not an error
                }
                
                // **FIX**: Clear the ref for any subsequent recordings.
                recordedChunksRef.current = [];
            };
    
            recorder.start(1000); // Collect chunks every second
            setMediaRecorder(recorder);
            setIsRecordingVideo(true);
        } catch (error) {
            console.error("Error accessing webcam:", error);
        }
    }, [uploadRecording]); // Depends on the stable uploadRecording function

    /**
     * Effect to start the webcam recording once the interview becomes active.
     */
    useEffect(() => {
        if (interviewStatus === "active" && !isRecordingVideo) {
            startWebcamRecording();
        }
    }, [interviewStatus, isRecordingVideo, startWebcamRecording]);

    /**
     * Handles the logic for ending the interview.
     */
    const endInterview = useCallback(async () => {
        if (!sessionId || interviewStatus !== "active" || uploadStatus === 'uploading') return;
    
        setUploadStatus('uploading');
    
        try {
            // **CRITICAL**: This now correctly waits for the upload to finish.
            await stopAndUploadRecording();
            setUploadStatus('success');
            console.log("Recording saved. Now ending the interview on the server.");
    
            setInterviewStatus("ending");
            const token = localStorage.getItem("companyxyz-token");
            const response = await fetch(`http://localhost:5000/api/interviews/${sessionId}/end`, {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: token },
            });
            const data = await response.json();
    
            if (!response.ok) throw new Error(data.error || 'Failed to end interview');
    
            // Update UI with final evaluation
            setInterviewStatus("completed");
            setEvaluation(data.evaluation);
    
            setChatContent(prev => {
                const newChatContent = { ...prev };
                const newIndex = Object.keys(newChatContent).length;
                newChatContent[newIndex] = { response: "Thank you for completing the interview. Here's your evaluation:" };
                if (data.evaluation && data.evaluation.qualitative_assessment) {
                    newChatContent[newIndex + 1] = { response: data.evaluation.qualitative_assessment };
                }
                return newChatContent;
            });
    
        } catch (error) {
            console.error("Failed to save recording or end interview:", error);
            setUploadStatus('error');
            setChatContent(prev => {
                const newChatContent = { ...prev };
                const newIndex = Object.keys(newChatContent).length;
                newChatContent[newIndex] = { response: `⚠️ Error saving recording: ${error.message}. Please contact support.` };
                return newChatContent;
            });
            setInterviewStatus("active"); // Revert status to allow retry
        }
    }, [sessionId, interviewStatus, uploadStatus, stopAndUploadRecording]);

    /**
     * Handles sending a user's answer to the backend.
     */
    const onSend = useCallback(async (e) => {
        e.preventDefault();
        const answer = input.trim();
        if (answer === "" || !currentQuestion || !sessionId || interviewStatus !== "active") {
            setInput("");
            return;
        }

        const newChatContent = { ...chatContent };
        const newIndex = Object.keys(newChatContent).length;
        newChatContent[newIndex] = { query: answer, response: "Analyzing your response..." };
        setChatContent(newChatContent);
        setInput("");

        try {
            const response = await fetch(`http://localhost:5000/api/interviews/${sessionId}/answer`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: currentQuestion, answer: answer }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Failed to submit answer");

            const updatedChatContent = { ...newChatContent };
            if (data.evaluation && data.evaluation.feedback) {
                updatedChatContent[newIndex] = { query: answer, evaluation: data.evaluation };
            }

            if (data.interview_complete) {
                await endInterview(); // Call the robust endInterview function
            } else {
                setCurrentQuestion(data.next_question);
                updatedChatContent[newIndex + 1] = { response: data.next_question };
            }
            setChatContent(updatedChatContent);

        } catch (error) {
            console.error("Error in onSend:", error);
            const updatedChatContent = { ...chatContent };
            const errorIndex = Object.keys(updatedChatContent).length;
            updatedChatContent[errorIndex] = { response: `⚠️ An error occurred: ${error.message}` };
            setChatContent(updatedChatContent);
            if (uploadStatus === 'uploading') setUploadStatus('error');
        }
    }, [chatContent, input, currentQuestion, sessionId, interviewStatus, endInterview, uploadStatus]);


    // --- Other Effects and Handlers (No changes needed here) ---

    useEffect(() => {
        const isLoggedIn = localStorage.getItem("companyxyz-token") !== null;
        if (!isLoggedIn) {
            navigate("/login");
        }
    }, [navigate]);

    useEffect(() => {
        if (interviewId && !sessionId && interviewStatus === "starting") {
            const token = localStorage.getItem("companyxyz-token");
            fetch("http://localhost:5000/api/interviews/start", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: token,
                },
                body: JSON.stringify({
                    cv_path: "uploads/cv/PeterConnollyResume-2.pdf",
                    jd_path: "uploads/jd/JD1.pdf",
                    reference_path: "Eric Ries - The Lean Startup.pdf",
                }),
            })
            .then((response) => response.json())
            .then((data) => {
                setSessionId(data.session_id);
                setSimilarityScore(data.similarity_score);
                setInterviewStatus("active");

                const newChatContent = {};
                newChatContent[0] = {
                    response: `Welcome to your AI interview session. Your CV has a ${Math.round(data.similarity_score * 100)}% match with the job description. I'll be asking you several questions to assess your fit for this role.`,
                };

                if (data.initial_questions && data.initial_questions.length > 0) {
                    setCurrentQuestion(data.initial_questions[0]);
                    newChatContent[1] = {
                        response: data.initial_questions[0],
                    };
                }
                setChatContent(newChatContent);
            })
            .catch((error) => {
                console.error("Error starting interview:", error);
                setChatContent({ 0: { response: "⚠️ Error: Could not start the interview session. Please try again later." } });
            });
        }
    }, [interviewId, sessionId, interviewStatus, navigate]);
    
    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false;
            recognitionRef.current.interimResults = false;
            recognitionRef.current.lang = "en-US";

            recognitionRef.current.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                setInput(transcript);
                setIsRecording(false);
            };

            recognitionRef.current.onerror = (event) => {
                console.error("Speech recognition error", event);
                setIsRecording(false);
            };

            recognitionRef.current.onend = () => {
                setIsRecording(false);
            };
        } else {
            console.error("Speech Recognition API is not supported in this browser.");
        }
    }, []);

    const handleVoiceInput = () => {
        if (!recognitionRef.current) return;
        if (isRecording) {
            recognitionRef.current.stop();
        } else {
            recognitionRef.current.start();
            setIsRecording(true);
        }
    };

    const toggleSpeech = (idx, text) => {
        if (!window.speechSynthesis) {
            console.error("Speech Synthesis API is not supported in this browser.");
            return;
        }
        if (isSpeaking && speakingIndex === idx) {
            window.speechSynthesis.cancel();
            setIsSpeaking(false);
            setSpeakingIndex(null);
            return;
        }
        if (isSpeaking) {
            window.speechSynthesis.cancel();
        }
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "en-US";
        utterance.onstart = () => {
            setIsSpeaking(true);
            setSpeakingIndex(idx);
        };
        utterance.onend = () => {
            setIsSpeaking(false);
            setSpeakingIndex(null);
        };
        utterance.onerror = () => {
            setIsSpeaking(false);
            setSpeakingIndex(null);
        };
        currentUtteranceRef.current = utterance;
        window.speechSynthesis.speak(utterance);
    };

    const getEndButtonText = () => {
        switch (uploadStatus) {
            case 'uploading':
                return 'Saving Recording...';
            case 'error':
                return 'Upload Failed, Try Again';
            default:
                return 'End Interview';
        }
    };

    // --- RENDER ---
    return (
        <div className={Styles["page-container"]}>
            <div className={Styles["chat-box-container"]}>
                <div className={Styles["chat-header"]}>
                    <h2>AI Interview Session {sessionId ? `#${sessionId}` : ""}</h2>
                    {isRecordingVideo && (
                        <div className={Styles.recordingIndicator}>
                            <div className={Styles.recordingDot}></div>
                            Recording
                        </div>
                    )}
                    {similarityScore !== null && (
                        <div className={Styles["similarity-score"]}>
                            CV-JD Match: {Math.round(similarityScore * 100)}%
                        </div>
                    )}
                    {interviewStatus === "active" && (
                        <button
                            className={Styles["end-interview-btn"]}
                            onClick={endInterview}
                            disabled={uploadStatus === 'uploading'}
                        >
                            {getEndButtonText()}
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
                                                <img src={"../android-chrome-192x192.png"} alt="User Avatar" />
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
                                                <img src={"../android-chrome-512x512.png"} alt="AI Avatar" />
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
                            <div className={Styles["loading-chat"]}>Initializing interview session...</div>
                        )}
                    </div>
                    <div className={Styles["input-area"]}>
                        <form onSubmit={onSend}>
                            <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder={
                                    interviewStatus === "active" ? "Type your answer here..."
                                    : interviewStatus === "completed" ? "Interview completed"
                                    : "Starting interview..."
                                }
                                disabled={interviewStatus !== "active"}
                                className={Styles["chat-input"]}
                            />
                            <div className={Styles["input-actions"]}>
                                <button type="button" className={Styles["voice-input-button"]} onClick={handleVoiceInput} disabled={interviewStatus !== "active"}>
                                    {isRecording ? "Stop" : "Voice"}
                                </button>
                                <button type="submit" className={Styles["send-button"]} disabled={interviewStatus !== "active" || !input.trim()}>
                                    Send
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
            <div className={Styles["video-preview"]} style={{ display: 'none' }}>
                <video ref={videoRef} autoPlay muted playsInline />
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
                        {evaluation.qualitative_assessment.split("\n").map((line, index) => (
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

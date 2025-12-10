import React, { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import io from "socket.io-client";
import axios from "axios";

const MobileRecorder = () => {
    const { sessionId } = useParams();
    const videoRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const chunksRef = useRef([]);
    const [status, setStatus] = useState("Connecting...");
    const [socket, setSocket] = useState(null);

    useEffect(() => {
        // 1. Initialize Socket
        const newSocket = io("http://localhost:5000"); // Your backend URL
        setSocket(newSocket);

        newSocket.emit("join_mobile_session", { session_id: sessionId });
        setStatus("Waiting for interview to start...");

        // 2. Setup Camera (Rear Camera)
        const startCamera = async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: "environment" }, // Request back camera
                    audio: true 
                });
                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                }
                return stream;
            } catch (err) {
                console.error("Camera access denied:", err);
                setStatus("Error: Camera access denied");
            }
        };

        const streamPromise = startCamera();

        // 3. Listen for commands
        newSocket.on("mobile_recording_action", async (data) => {
            const stream = await streamPromise;

            if (data.action === "start") {
                setStatus("Recording...");
                mediaRecorderRef.current = new MediaRecorder(stream);
                chunksRef.current = [];

                mediaRecorderRef.current.ondataavailable = (e) => {
                    if (e.data.size > 0) chunksRef.current.push(e.data);
                };

                mediaRecorderRef.current.onstop = uploadRecording;
                mediaRecorderRef.current.start(1000); // Save chunks every second
            } 
            else if (data.action === "stop") {
                setStatus("Stopping & Uploading...");
                if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
                    mediaRecorderRef.current.stop();
                }
            }
        });

        return () => {
            newSocket.disconnect();
            // Cleanup stream
            if (videoRef.current && videoRef.current.srcObject) {
                videoRef.current.srcObject.getTracks().forEach(track => track.stop());
            }
        };
    }, [sessionId]);

    const uploadRecording = async () => {
        const blob = new Blob(chunksRef.current, { type: "video/webm" });
        const formData = new FormData();
        formData.append("recording", blob, "mobile_recording.webm");

        try {
            await axios.post(`http://localhost:5000/api/interviews/${sessionId}/upload-mobile-recording`, formData);
            setStatus("Upload Complete! You can close this tab.");
            socket.emit("mobile_status_update", { session_id: sessionId, status: "uploaded" });
        } catch (error) {
            setStatus("Upload Failed. Please try again.");
            console.error(error);
        }
    };

    return (
        <div style={{ backgroundColor: "#000", height: "100vh", color: "#fff", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
            <h3>Secondary Camera</h3>
            <p>{status}</p>
            {/* Show preview so user knows what they are capturing */}
            <video ref={videoRef} autoPlay muted playsInline style={{ width: "80%", border: "2px solid green" }} />
        </div>
    );
};

export default MobileRecorder;
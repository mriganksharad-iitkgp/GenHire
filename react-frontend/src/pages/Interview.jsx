import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import Chat from "./Chat";
import io from "socket.io-client";
import { proctoringConfig } from "../config/proctoring";

const Interview = () => {
	const { interviewId } = useParams();
	const [showWarning, setShowWarning] = useState(false);
	const [isInterviewEnding, setIsInterviewEnding] = useState(false);
	const socket = io(process.env.REACT_APP_API_URL); // Standard app socket for other things? Or was this ONLY for proctoring?
	// It seems this socket was ONLY for gaze_data.

	useEffect(() => {
		if (!proctoringConfig.enabled) return;

		const socket = io(proctoringConfig.serverUrl);
		socket.on("gaze_data", (data) => {
			if (data.session_id === interviewId) {
				if (data.gaze_direction !== "Center") {
					setShowWarning(true);
				} else {
					setShowWarning(false);
				}
			}
		});

		return () => {
			socket.disconnect();
		};
	}, [interviewId]);

	const handleEndInterview = () => {
		setIsInterviewEnding(true);
		// You can also add any cleanup logic here, like stopping the camera, etc.
	};

	if (isInterviewEnding) {
		return (
			<div
				style={{
					display: "flex",
					justifyContent: "center",
					alignItems: "center",
					height: "100vh",
					fontSize: "2rem",
				}}
			>
				<p>We are ending the interview...</p>
			</div>
		);
	}

	return (
		<div>
			{showWarning && (
				<div
					style={{
						backgroundColor: "orange",
						color: "white",
						textAlign: "center",
						padding: "10px",
						position: "fixed",
						top: 0,
						width: "100%",
						zIndex: 1000,
					}}
				>
					Please look at the center of the screen
				</div>
			)}
			<Chat interviewId={interviewId} onEndInterview={handleEndInterview} />
		</div>
	);
};

export default Interview;
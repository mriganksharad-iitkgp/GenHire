import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import Chat from "./Chat";
import io from "socket.io-client";
import { proctoringConfig } from "features/interview/config/proctoring";

// Thin wrapper around Chat. NOTE: the previous version also created an
// unmanaged `io(...)` socket on every render (never cleaned up) — Chat owns
// the proctoring socket, so only the optional gaze-warning listener remains.
const Interview = () => {
	const { interviewId } = useParams();
	const [showWarning, setShowWarning] = useState(false);

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
			<Chat interviewId={interviewId} />
		</div>
	);
};

export default Interview;

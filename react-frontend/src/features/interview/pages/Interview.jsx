import React, { useState, useEffect } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import Chat from "./Chat";
import io from "socket.io-client";
import { proctoringConfig } from "features/interview/config/proctoring";
import { getIdentityCardStatus } from "features/candidate/api/identityCardApi";
import styles from "./Interview.module.css";

// Thin wrapper around Chat. Gates real interviews behind the identity card:
// the capture at interview start is verified against the uploaded ID, so a
// candidate without one is sent to their profile to upload it first.
// Practice sessions never verify identity and are not gated.
const Interview = () => {
	const { interviewId } = useParams();
	const location = useLocation();
	const [showWarning, setShowWarning] = useState(false);
	// null = checking, true = ok to proceed, false = ID card missing
	const [identityReady, setIdentityReady] = useState(null);

	const isPractice =
		location.state?.isPractice ||
		new URLSearchParams(location.search).get("practice") === "true";

	useEffect(() => {
		if (isPractice) {
			setIdentityReady(true);
			return;
		}
		let cancelled = false;
		getIdentityCardStatus()
			.then((status) => {
				if (!cancelled) setIdentityReady(!!status.uploaded);
			})
			.catch(() => {
				// If the status check itself fails, let the backend gate decide
				// at interview start instead of blocking here.
				if (!cancelled) setIdentityReady(true);
			});
		return () => {
			cancelled = true;
		};
	}, [isPractice]);

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

	if (identityReady === null) {
		return (
			<div className={styles.gateContainer}>
				<p>Checking your identity card…</p>
			</div>
		);
	}

	if (identityReady === false) {
		return (
			<div className={styles.gateContainer}>
				<div className={styles.gateCard}>
					<h2>Identity card required</h2>
					<p>
						Before you can start an interview, you need to upload your
						identity card. Your face is verified against it when the
						interview begins.
					</p>
					<p className={styles.gateNote}>
						The card can be uploaded only once — make sure the photo is
						clear before submitting.
					</p>
					<Link to="/profile" className={styles.gateButton}>
						Upload identity card in your profile
					</Link>
				</div>
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
			<Chat interviewId={interviewId} />
		</div>
	);
};

export default Interview;

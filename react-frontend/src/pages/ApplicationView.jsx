import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import styles from "./ApplicationView.module.css";
import "./darkModeOverride.css";
import "./emergency-fixes.css";

const ApplicationView = () => {
	const { applicationId } = useParams();
	const navigate = useNavigate();
	const [isLoading, setIsLoading] = useState(true);
	const [application, setApplication] = useState(null);
	const [currentDate, setCurrentDate] = useState(new Date());


	// Update current time every minute to ensure time window logic works correctly
	useEffect(() => {
		const timer = setInterval(() => {
			setCurrentDate(new Date());
		}, 60000); // update every minute

		return () => clearInterval(timer); // cleanup on unmount
	}, []);

	useEffect(() => {
			// Check authentication
			const token = localStorage.getItem("companyxyz-token");
			if (!token) {
				navigate("/login");
				return;
			}

			const fetchApplication = async () => {
				try {
					setIsLoading(true);
					const res = await fetch(
						`${process.env.REACT_APP_API_URL}/api/applications/${applicationId}`,
						{
							headers: {
								Authorization: `Bearer ${token}`,
							},
						}
					);

					if (!res.ok) {
						// Unauthorized or not found -> back to profile
						navigate("/profile");
						return;
					}

					const app = await res.json();

					// Build a minimal timeline from real fields
					const appliedDateISO = app.applied_at || new Date().toISOString();
					const updatedDateISO = app.updated_at || appliedDateISO;

					const timeline = [
						{
							id: 1,
							date: appliedDateISO,
							type: "Application Submitted",
							status: "Completed",
							description: "Your application was successfully submitted.",
							icon: "fa-paper-plane",
						},
					];

					const status = String(app.status || "pending").toLowerCase();
					const pushEvent = (id, type, desc, icon, done = true) =>
						timeline.push({
							id,
							date: updatedDateISO,
							type,
							status: done ? "Completed" : "Pending",
							description: desc,
							icon,
						});

					if (["reviewed", "shortlisted", "interviewed", "selected", "rejected"].includes(status)) {
						if (status === "reviewed")
							pushEvent(2, "Application Reviewed", "Your application was reviewed by our hiring team.", "fa-check-circle");
						if (status === "shortlisted")
							pushEvent(3, "Shortlisted", "You've been shortlisted for the next round.", "fa-star");
						if (status === "interviewed")
							pushEvent(4, "Interview Completed", "Your interview has been completed.", "fa-video-camera");
						if (status === "selected")
							pushEvent(5, "Offer", "Congratulations! You've been selected.", "fa-trophy");
						if (status === "rejected")
							pushEvent(6, "Rejection", "We proceeded with other candidates.", "fa-times-circle");
					}

					setApplication({
						id: app._id,
						position: app.job_details?.title || app.job_title || "Applied Position",
						company: app.job_details?.company || "TechCorp Solutions",
						jobId: app.job_id,
						status: status.charAt(0).toUpperCase() + status.slice(1),
						appliedDate: appliedDateISO,
						timeline,
					});
				} catch (e) {
					navigate("/profile");
				} finally {
					setIsLoading(false);
				}
			};

			fetchApplication();
	}, [applicationId, navigate]);

	// Format date for display
	const formatDate = (dateString) => {
		const options = { year: "numeric", month: "long", day: "numeric" };
		return new Date(dateString).toLocaleDateString(undefined, options);
	};

	// Check if interview is upcoming or past
	const isInterviewUpcoming = (interviewDate) => {
		const interview = new Date(interviewDate);

		// Set interview to end of day for more accurate comparison
		interview.setHours(23, 59, 59, 999);

		return interview >= currentDate;
	};

	// Check if interview is today
	const isInterviewToday = (interviewDate) => {
		const interview = new Date(interviewDate);
		const today = new Date(currentDate);

		return (
			interview.getDate() === today.getDate() &&
			interview.getMonth() === today.getMonth() &&
			interview.getFullYear() === today.getFullYear()
		);
	};

	// Check if current time is within interview window (30 minutes before and after scheduled time)
	const isWithinInterviewWindow = (interviewDate, interviewTime) => {
		// Parse time properly handling both "10:00 AM" and "10:00" formats
		let hours = 0;
		let minutes = 0;

		if (interviewTime.includes("AM") || interviewTime.includes("PM")) {
			// Handle "10:00 AM" format
			const timeParts = interviewTime
				.replace(/\s/g, "")
				.match(/(\d+):(\d+)([APM]+)/i);
			if (timeParts) {
				hours = parseInt(timeParts[1]);
				minutes = parseInt(timeParts[2]);
				// Adjust hours for PM
				if (timeParts[3].toUpperCase() === "PM" && hours < 12) {
					hours += 12;
				}
				// Adjust for 12 AM
				if (timeParts[3].toUpperCase() === "AM" && hours === 12) {
					hours = 0;
				}
			}
		} else {
			// Handle "10:00" format
			const [hoursStr, minutesStr] = interviewTime.split(":");
			hours = parseInt(hoursStr);
			minutes = parseInt(minutesStr);
		}

		// Create interview date object
		const interview = new Date(interviewDate);
		interview.setHours(hours, minutes, 0, 0);

		const windowStart = new Date(interview.getTime() - 30 * 60000); // 30 minutes before
		const windowEnd = new Date(interview.getTime() + 30 * 60000); // 30 minutes after

		// For debugging
		console.log("Current time:", currentDate);
		console.log("Interview time:", interview);
		console.log("Window start:", windowStart);
		console.log("Window end:", windowEnd);
		console.log(
			"Is within window:",
			currentDate >= windowStart && currentDate <= windowEnd
		);

		return currentDate >= windowStart && currentDate <= windowEnd;
	};

	// Format interview time for display
	const getRelativeInterviewTime = (interviewDate, interviewTime) => {
		if (isInterviewToday(interviewDate)) {
			return `Today at ${interviewTime}`;
		} else {
			return `${formatDate(interviewDate)} at ${interviewTime}`;
		}
	};

	// Get interview status text
	const getInterviewStatus = (interviewDate, interviewTime) => {
		if (!isInterviewToday(interviewDate)) {
			return "Upcoming";
		}
		if (isWithinInterviewWindow(interviewDate, interviewTime)) {
			return "In Progress";
		}
		return "Scheduled";
	};

	if (isLoading) {
		return (
			<div className={styles.loadingContainer}>
				<div className={styles.loader}></div>
				<p>Loading application details...</p>
			</div>
		);
	}

	if (!application) {
		return (
			<div className={styles.loadingContainer}>
				<p>Application not found.</p>
				<button
					className={styles.backButton}
					onClick={() => navigate("/profile#applications")}
				>
					<i className="fa fa-arrow-left"></i> Back to Applications
				</button>
			</div>
		);
	}

	return (
		<div className={styles.applicationViewContainer}>
			<div className={styles.content}>
				<div className={styles.header}>
					<button
						className={styles.backButton}
						onClick={() => navigate("/profile#applications")}
					>
						<i className="fa fa-arrow-left"></i> Back to
						Applications
					</button>
				</div>

				<div className={styles.applicationHeader}>
					<div className={styles.applicationInfo}>
						<h1>{application.position}</h1>
						<div className={styles.applicationMeta}>
							<span className={styles.company}>
								{application.company}
							</span>
							<span className={styles.appliedDate}>
								<i className="fa fa-calendar"></i> Applied on{" "}
								{formatDate(application.appliedDate)}
							</span>
							<span
								className={`${styles.status} ${
									styles[
										application.status
											.toLowerCase()
											.replace(" ", "")
									]
								}`}
							>
								{application.status}
							</span>
						</div>
					</div>
					<div className={styles.applicationActions}>
						<Link
							to={`/job/${application.jobId}`}
							className={styles.viewJobButton}
						>
							<i className="fa fa-file-text-o"></i> View Job
							Description
						</Link>
					</div>
				</div>

				<div className={styles.applicationBody}>
					<div className={styles.timelineSection}>
						<h2>Application Timeline</h2>
						<div className={styles.timeline}>
							{application.timeline.map((event, index) => (
								<div
									key={event.id}
									className={`${styles.timelineEvent} ${
										event.status.toLowerCase() ===
										"completed"
											? styles.completed
											: event.status.toLowerCase() ===
											  "scheduled"
											? styles.scheduled
											: styles.pending
									}`}
								>
									<div className={styles.timelineIcon}>
										<i className={`fa ${event.icon}`}></i>
									</div>
									<div className={styles.timelineConnector}>
										{index <
											application.timeline.length - 1 && (
											<div
												className={styles.connector}
											></div>
										)}
									</div>
									<div className={styles.timelineContent}>
										<div className={styles.timelineHeader}>
											<h3>{event.type}</h3>
											<span
												className={styles.timelineDate}
											>
												{formatDate(event.date)}
											</span>
										</div>
										<p>{event.description}</p>

										{/* Interview Details Section */}
										{event.interviewDetails && (
											<div
												className={
													styles.interviewDetails
												}
											>
												<div
													className={
														styles.interviewHeader
													}
												>
													<h4>Interview Details</h4>
													{isInterviewUpcoming(
														event.interviewDetails
															.date
													) && (
														<div
															className={
																styles.interviewActions
															}
														>
															{event
																.interviewDetails
																.meetingLink && (
																<>
																	{isWithinInterviewWindow(
																		event
																			.interviewDetails
																			.date,
																		event
																			.interviewDetails
																			.time
																	) ? (
																		<a
																			href={
																				event
																					.interviewDetails
																					.meetingLink
																			}
																			target="_blank"
																			rel="noopener noreferrer"
																			className={
																				styles.joinButton
																			}
																		>
																			<i className="fa fa-video-camera"></i>{" "}
																			Join
																			Interview
																		</a>
																	) : (
																		<span
																			className={
																				styles.joinButtonDisabled
																			}
																		>
																			<i className="fa fa-clock-o"></i>{" "}
																			{getInterviewStatus(
																				event
																					.interviewDetails
																					.date,
																				event
																					.interviewDetails
																					.time
																			)}
																		</span>
																	)}
																</>
															)}
															<Link
																to={`/interview/${event.interviewDetails.id}?practice=true`}
																className={
																	styles.practiceButton
																}
															>
																<i className="fa fa-microphone"></i>{" "}
																Practice
															</Link>
														</div>
													)}
												</div>

												<div
													className={
														styles.interviewInfo
													}
												>
													<div
														className={
															styles.infoItem
														}
													>
														<i className="fa fa-clock-o"></i>
														<div>
															<strong>
																When:
															</strong>{" "}
															{getRelativeInterviewTime(
																event
																	.interviewDetails
																	.date,
																event
																	.interviewDetails
																	.time
															)}
															<div
																className={
																	styles.duration
																}
															>
																Duration:{" "}
																{
																	event
																		.interviewDetails
																		.duration
																}
															</div>
														</div>
													</div>

													<div
														className={
															styles.infoItem
														}
													>
														<i className="fa fa-users"></i>
														<div>
															<strong>
																Interviewers:
															</strong>
															<ul
																className={
																	styles.interviewersList
																}
															>
																{event.interviewDetails.interviewers.map(
																	(
																		interviewer,
																		i
																	) => (
																		<li
																			key={
																				i
																			}
																		>
																			{
																				interviewer
																			}
																		</li>
																	)
																)}
															</ul>
														</div>
													</div>

													<div
														className={
															styles.infoItem
														}
													>
														<i className="fa fa-map-marker"></i>
														<div>
															<strong>
																Location:
															</strong>{" "}
															{
																event
																	.interviewDetails
																	.location
															}
														</div>
													</div>

													<div
														className={
															styles.infoItem
														}
													>
														<i className="fa fa-list"></i>
														<div>
															<strong>
																Agenda:
															</strong>
															<ul
																className={
																	styles.agendaList
																}
															>
																{event.interviewDetails.agenda.map(
																	(
																		item,
																		i
																	) => (
																		<li
																			key={
																				i
																			}
																		>
																			{
																				item
																			}
																		</li>
																	)
																)}
															</ul>
														</div>
													</div>

													<div
														className={
															styles.infoItem
														}
													>
														<i className="fa fa-lightbulb-o"></i>
														<div>
															<strong>
																Preparation
																Tips:
															</strong>
															<ul
																className={
																	styles.prepList
																}
															>
																{event.interviewDetails.preparation.map(
																	(
																		item,
																		i
																	) => (
																		<li
																			key={
																				i
																			}
																		>
																			{
																				item
																			}
																		</li>
																	)
																)}
															</ul>
														</div>
													</div>
												</div>
											</div>
										)}
									</div>
								</div>
							))}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export default ApplicationView;

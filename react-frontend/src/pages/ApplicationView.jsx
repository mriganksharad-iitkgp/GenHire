import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import styles from "./ApplicationView.module.css";

const ApplicationView = () => {
	const { applicationId } = useParams();
	const navigate = useNavigate();
	const [isLoading, setIsLoading] = useState(true);
	const [application, setApplication] = useState(null);
	const [currentDate, setCurrentDate] = useState(new Date());

	// Sample application data with timeline and detailed interview information
	const sampleApplications = {
		1: {
			id: 1,
			position: "Senior Business Development Manager",
			company: "CompanyXYZ",
			jobId: 1001,
			status: "In Progress",
			appliedDate: "2023-08-15",
			timeline: [
				{
					id: 1,
					date: "2023-08-15",
					type: "Application Submitted",
					status: "Completed",
					description: "Your application was successfully submitted.",
					icon: "fa-paper-plane",
				},
				{
					id: 2,
					date: "2023-08-20",
					type: "Application Reviewed",
					status: "Completed",
					description:
						"Your application was reviewed by our hiring team.",
					icon: "fa-check-circle",
				},
				{
					id: 3,
					date: "2023-08-25",
					type: "Skills Assessment",
					status: "Completed",
					description:
						"Online business strategy assessment was completed successfully.",
					icon: "fa-chart-line",
				},
				{
					id: 4,
					date: new Date(new Date().getTime() + 5.5 * 60 * 60 * 1000)
						.toISOString()
						.split("T")[0], // Today's date
					type: "Live Demo Interview",
					status: "Scheduled",
					description:
						"Test interview scheduled for today to demonstrate the time window feature.",
					icon: "fa-video-camera",
					interviewDetails: {
						id: 999,
						date: new Date(
							new Date().getTime() + 5.5 * 60 * 60 * 1000
						)
							.toISOString()
							.split("T")[0],
						time:
							new Date().getHours() +
							":" +
							(new Date().getMinutes() < 10 ? "0" : "") +
							new Date().getMinutes(),
						duration: "1 hour",
						type: "Demo",
						interviewers: ["Test Interviewer (Demo Manager)"],
						location: "Remote (Platform Chat)",
						meetingLink: "/interview/999",
						agenda: [
							"Demonstration of interview time window feature",
							"Test of join button functionality",
						],
						preparation: [
							"No preparation needed - this is just a demo",
						],
					},
				},
				{
					id: 5,
					date: "2023-09-15",
					type: "Business Interview",
					status: "Scheduled",
					description:
						"Remote interview with the business development team.",
					icon: "fa-video-camera",
					interviewDetails: {
						id: 101,
						date: "2023-09-15",
						time: "10:00 AM",
						duration: "1 hour",
						type: "Business Strategy",
						interviewers: [
							"Sarah Johnson (Sales Director)",
							"Michael Chen (Senior Business Manager)",
						],
						location: "Remote (Platform Chat)",
						meetingLink: "/interview/101",
						agenda: [
							"Discussion of your previous business development experience",
							"Questions on sales strategies, client acquisition, and market analysis",
							"Business case scenario discussion",
							"Q&A session",
						],
						preparation: [
							"Review your experience with sales strategies and client relationship management",
							"Be prepared to discuss business growth examples from past roles",
							"Practice explaining your approach to business development",
						],
					},
				},
				{
					id: 6,
					date: "2023-09-25",
					type: "Final Interview",
					status: "Pending",
					description: "Interview with the CCO and team leads.",
					icon: "fa-users",
					interviewDetails: {
						id: 102,
						date: "2023-09-25",
						time: "2:00 PM",
						duration: "1 hour",
						type: "Leadership",
						interviewers: [
							"Alex Patterson (CCO)",
							"Emma Rodriguez (Sales Lead)",
						],
						location: "Remote (Platform Chat)",
						meetingLink: "/interview/102",
						agenda: [
							"Discussion about career goals and vision",
							"Cultural fit assessment",
							"Leadership and collaboration scenarios",
							"Q&A about the company and role",
						],
						preparation: [
							"Prepare questions about the company's business direction",
							"Review the company's values and culture",
							"Be ready to discuss a challenging business deal you closed",
						],
					},
				},
				{
					id: 7,
					date: "2023-10-01",
					type: "Decision",
					status: "Pending",
					description: "Final hiring decision will be made.",
					icon: "fa-flag-checkered",
				},
			],
		},
		2: {
			id: 2,
			position: "Business Development Representative",
			company: "CompanyXYZ",
			jobId: 1002,
			status: "Rejected",
			appliedDate: "2023-07-10",
			timeline: [
				{
					id: 1,
					date: "2023-07-10",
					type: "Application Submitted",
					status: "Completed",
					description: "Your application was successfully submitted.",
					icon: "fa-paper-plane",
				},
				{
					id: 2,
					date: "2023-07-15",
					type: "Application Reviewed",
					status: "Completed",
					description:
						"Your application was reviewed by our hiring team.",
					icon: "fa-check-circle",
				},
				{
					id: 3,
					date: "2023-07-30",
					type: "Rejection",
					status: "Completed",
					description:
						"We've decided to proceed with other candidates whose skills better match our current needs.",
					icon: "fa-times-circle",
				},
			],
		},
		3: {
			id: 3,
			position: "Strategic Partnerships Manager",
			company: "CompanyXYZ",
			jobId: 1003,
			status: "Shortlisted",
			appliedDate: "2023-09-01",
			timeline: [
				{
					id: 1,
					date: "2023-09-01",
					type: "Application Submitted",
					status: "Completed",
					description: "Your application was successfully submitted.",
					icon: "fa-paper-plane",
				},
				{
					id: 2,
					date: "2023-09-05",
					type: "Application Reviewed",
					status: "Completed",
					description:
						"Your application was reviewed by our hiring team.",
					icon: "fa-check-circle",
				},
				{
					id: 3,
					date: "2023-09-15",
					type: "HR Round",
					status: "Scheduled",
					description: "Initial discussion with the HR team.",
					icon: "fa-comments",
					interviewDetails: {
						id: 103,
						date: "2023-09-15",
						time: "3:00 PM",
						duration: "30 minutes",
						type: "HR",
						interviewers: ["Jessica Kim (HR Manager)"],
						location: "Platform Chat",
						meetingLink: "/interview/103",
						agenda: [
							"Overview of your background and experience",
							"Discussion about your interest in the company",
							"Explanation of the hiring process",
							"Questions about salary expectations and availability",
						],
						preparation: [
							"Research about company history and values",
							"Prepare a brief summary of your relevant experience",
							"Have questions ready about the team and work environment",
						],
					},
				},
				{
					id: 4,
					date: "2023-09-20",
					type: "Partnership Strategy Round",
					status: "Scheduled",
					description:
						"Interview focused on partnership strategy skills.",
					icon: "fa-handshake-o",
					interviewDetails: {
						id: 104,
						date: "2023-09-20",
						time: "11:00 AM",
						duration: "1 hour",
						type: "Business Strategy",
						interviewers: ["David Wilson (Partnerships Lead)"],
						location: "Remote (Platform Chat)",
						meetingLink: "/interview/104",
						agenda: [
							"Questions about partnership strategies, contract negotiation, and revenue models",
							"Discussion about your previous partnership projects",
							"Problem-solving scenarios for partnership challenges",
							"Partner acquisition strategy discussion",
						],
						preparation: [
							"Review partnership fundamentals and business development strategies",
							"Be prepared to explain partnership lifecycle management",
							"Practice explaining how you structure partnership agreements",
						],
					},
				},
			],
		},
	};

	// Update current time every minute to ensure time window logic works correctly
	useEffect(() => {
		const timer = setInterval(() => {
			setCurrentDate(new Date());
		}, 60000); // update every minute

		return () => clearInterval(timer); // cleanup on unmount
	}, []);

	useEffect(() => {
		// Check authentication
		const isLoggedIn = localStorage.getItem("companyxyz-token") !== null;
		if (!isLoggedIn) {
			navigate("/login");
			return;
		}

		// Simulate API call to fetch application data
		setIsLoading(true);
		setTimeout(() => {
			const app = sampleApplications[applicationId];
			if (app) {
				setApplication(app);
			} else {
				// If application not found, redirect to profile
				navigate("/profile");
			}
			setIsLoading(false);
		}, 800);
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

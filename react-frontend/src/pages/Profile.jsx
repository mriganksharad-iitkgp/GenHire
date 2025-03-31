import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import styles from "./Profile.module.css";

const Profile = () => {
	const navigate = useNavigate();
	const [activeTab, setActiveTab] = useState("bio"); // Add state for active tab
	const [cvFile, setCvFile] = useState(null);
	const [cvFilePath, setCvFilePath] = useState(null);
	const [isUploading, setIsUploading] = useState(false);
	const [bioData, setBioData] = useState({
		name: "John Doe",
		email: "john.doe@example.com",
		phone: "+1 (555) 123-4567",
		location: "New York, USA",
		title: "Senior Business Development Manager",
		about: "Experienced business development professional with 5+ years of experience in identifying opportunities, building relationships, and growing revenue for organizations.",
		skills: [
			"Sales Strategy",
			"Client Acquisition",
			"Market Research",
			"Negotiation",
			"CRM Systems",
		],
	});

	// Sample job applications data
	const [applications, setApplications] = useState([
		{
			id: 1,
			company: "CompanyXYZ",
			position: "Senior Business Development Manager",
			appliedDate: "2023-08-15",
			status: "In Progress",
			interviews: [
				{
					date: "2025-03-27",
					type: "Initial Screening",
					time: "02:30 PM",
					meetingLink: "/interview/201",
				},
				{
					date: new Date(new Date().getTime() + 5.5 * 60 * 60 * 1000)
						.toISOString()
						.split("T")[0], // Today's date
					type: "Demo Interview",
					time:
						new Date().getHours() +
						":" +
						(new Date().getMinutes() < 10 ? "0" : "") +
						new Date().getMinutes(),
					meetingLink: "/interview/202",
				},
			],
		},
		{
			id: 2,
			company: "CompanyXYZ",
			position: "Business Development Representative",
			appliedDate: "2023-07-10",
			status: "Rejected",
			interviews: [],
		},
		{
			id: 3,
			company: "CompanyXYZ",
			position: "Strategic Partnerships Manager",
			appliedDate: "2023-09-01",
			status: "Shortlisted",
			interviews: [
				{
					date: "2023-09-15",
					type: "HR Round",
					time: "2:30 PM",
					meetingLink: "/interview/203",
				},
				{
					date: "2023-09-20",
					type: "Sales Pitch Presentation",
					time: "11:00 AM",
					meetingLink: "/interview/204",
				},
			],
		},
	]);

	// Check authentication when component mounts
	useEffect(() => {
		const isLoggedIn = localStorage.getItem("companyxyz-token") !== null;
		if (!isLoggedIn) {
			navigate("/login");
		}

		// Check for hash in URL to set active tab
		const hash = window.location.hash;
		if (hash === "#applications") {
			setActiveTab("applications");
		} else if (hash === "#bio") {
			setActiveTab("bio");
		}
	}, [navigate]);

	// Handle tab change
	const handleTabChange = (tab) => {
		setActiveTab(tab);
		window.location.hash = `#${tab}`;
	};

	// Handle CV upload
	const handleCVUpload = async (e) => {
		e.preventDefault();
		if (!cvFile) {
			alert("Please select a CV file.");
			return;
		}
		setIsUploading(true);

		const formData = new FormData();
		formData.append("cv", cvFile);

		try {
			// This is a mock API call - implement with actual backend
			setTimeout(() => {
				setCvFilePath(`/uploads/${cvFile.name}`);
				setIsUploading(false);
				alert("CV uploaded successfully!");
			}, 1500);

			// Uncomment and adapt when backend is ready
			/*
      const response = await fetch("http://localhost:5000/api/upload-cv", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (response.ok) {
        setCvFilePath(data.cv_file_path);
        alert("CV uploaded successfully!");
      } else {
        alert(data.error);
      }
      */
		} catch (error) {
			alert("Error uploading CV. Please try again.");
		} finally {
			setIsUploading(false);
		}
	};

	// Handle profile data update
	const handleProfileUpdate = (e) => {
		e.preventDefault();
		alert("Profile updated successfully!");
	};

	// Add helper function to check if an interview is currently live
	const isInterviewLive = (interview) => {
		const interviewDate = new Date(interview.date);
		let hours = 0;
		let minutes = 0;

		// Parse time properly handling both "10:00 AM" and "10:00" formats
		if (interview.time.includes("AM") || interview.time.includes("PM")) {
			// Handle "10:00 AM" format
			const timeParts = interview.time
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
			const [hoursStr, minutesStr] = interview.time.split(":");
			hours = parseInt(hoursStr);
			minutes = parseInt(minutesStr);
		}

		interviewDate.setHours(hours, minutes, 0, 0);

		const now = new Date();
		const windowStart = new Date(interviewDate.getTime() - 30 * 60000); // 30 minutes before
		const windowEnd = new Date(interviewDate.getTime() + 30 * 60000); // 30 minutes after

		return now >= windowStart && now <= windowEnd;
	};

	// Add helper function to get live interviews for an application
	const getLiveInterviews = (application) => {
		return application.interviews.filter((interview) =>
			isInterviewLive(interview)
		);
	};

	// Sort applications to show those with live interviews first
	const sortedApplications = [...applications].sort((a, b) => {
		const aLiveInterviews = getLiveInterviews(a).length;
		const bLiveInterviews = getLiveInterviews(b).length;
		return bLiveInterviews - aLiveInterviews;
	});

	return (
		<div className={styles.profileContainer}>
			<div className={styles.content}>
				<div className={styles.sidebar}>
					<div className={styles.profilePicSection}>
						<div className={styles.profilePic}>
							<img
								src="../android-chrome-192x192.png"
								alt="Profile"
							/>
						</div>
						<button className={styles.changePhotoBtn}>
							Change Photo
						</button>
					</div>

					<div className={styles.fileUploadBox}>
						<h3>CV Upload</h3>
						<form onSubmit={handleCVUpload}>
							<div className={styles.fileCard}>
								<label className={styles.fileInputLabel}>
									<i
										className="fa fa-file-text"
										aria-hidden="true"
									></i>
									<span>Resume/CV</span>
									<input
										type="file"
										accept=".pdf,.docx"
										onChange={(e) =>
											setCvFile(e.target.files[0])
										}
										className={styles.hiddenInput}
									/>
									<div className={styles.fileInfo}>
										{cvFile
											? cvFile.name
											: "No file selected"}
									</div>
								</label>
								{cvFilePath && (
									<div className={styles.fileInfo}>
										<a
											href={cvFilePath}
											target="_blank"
											rel="noopener noreferrer"
										>
											View Uploaded CV
										</a>
									</div>
								)}
							</div>
							<button
								type="submit"
								className={styles.uploadButton}
								disabled={isUploading}
							>
								{isUploading ? (
									"Uploading..."
								) : (
									<>
										<i
											className="fa fa-upload"
											aria-hidden="true"
										></i>
										Upload CV
									</>
								)}
							</button>
						</form>
					</div>

					{/* Application Statistics Card */}
					<div className={styles.statsCard}>
						<h3>Application Status</h3>
						<div className={styles.statsContainer}>
							<div className={styles.statItem}>
								<span className={styles.statNumber}>
									{applications.length}
								</span>
								<span className={styles.statLabel}>
									Total Applications
								</span>
							</div>
							<div className={styles.statItem}>
								<span className={styles.statNumber}>
									{
										applications.filter(
											(app) =>
												app.status === "Shortlisted"
										).length
									}
								</span>
								<span className={styles.statLabel}>
									Shortlisted
								</span>
							</div>
							<div className={styles.statItem}>
								<span className={styles.statNumber}>
									{
										applications.filter(
											(app) =>
												app.status === "In Progress"
										).length
									}
								</span>
								<span className={styles.statLabel}>
									In Progress
								</span>
							</div>
							<div className={styles.statItem}>
								<span className={styles.statNumber}>
									{
										applications.filter(
											(app) => app.status === "Rejected"
										).length
									}
								</span>
								<span className={styles.statLabel}>
									Rejected
								</span>
							</div>
						</div>
					</div>
				</div>

				<div className={styles.mainContent}>
					{/* Tab Navigation */}
					<div className={styles.tabNavigation}>
						<button
							className={`${styles.tabButton} ${
								activeTab === "bio" ? styles.activeTab : ""
							}`}
							onClick={() => handleTabChange("bio")}
						>
							<i className="fa fa-user"></i> Bio Data
						</button>
						<button
							className={`${styles.tabButton} ${
								activeTab === "applications"
									? styles.activeTab
									: ""
							}`}
							onClick={() => handleTabChange("applications")}
						>
							<i className="fa fa-file-text"></i> Applications
						</button>
					</div>

					{/* Tab Content */}
					<div className={styles.tabContent}>
						{/* Bio Data Tab */}
						{activeTab === "bio" && (
							<section className={styles.bioSection}>
								<h2>Bio Data</h2>
								<form onSubmit={handleProfileUpdate}>
									<div className={styles.formRow}>
										<div className={styles.formGroup}>
											<label>Full Name</label>
											<input
												type="text"
												value={bioData.name}
												onChange={(e) =>
													setBioData({
														...bioData,
														name: e.target.value,
													})
												}
											/>
										</div>
										<div className={styles.formGroup}>
											<label>Email</label>
											<input
												type="email"
												value={bioData.email}
												onChange={(e) =>
													setBioData({
														...bioData,
														email: e.target.value,
													})
												}
											/>
										</div>
									</div>

									<div className={styles.formRow}>
										<div className={styles.formGroup}>
											<label>Phone</label>
											<input
												type="tel"
												value={bioData.phone}
												onChange={(e) =>
													setBioData({
														...bioData,
														phone: e.target.value,
													})
												}
											/>
										</div>
										<div className={styles.formGroup}>
											<label>Location</label>
											<input
												type="text"
												value={bioData.location}
												onChange={(e) =>
													setBioData({
														...bioData,
														location:
															e.target.value,
													})
												}
											/>
										</div>
									</div>

									<div className={styles.formGroup}>
										<label>Professional Title</label>
										<input
											type="text"
											value={bioData.title}
											onChange={(e) =>
												setBioData({
													...bioData,
													title: e.target.value,
												})
											}
										/>
									</div>

									<div className={styles.formGroup}>
										<label>About Me</label>
										<textarea
											rows="4"
											value={bioData.about}
											onChange={(e) =>
												setBioData({
													...bioData,
													about: e.target.value,
												})
											}
										></textarea>
									</div>

									<div className={styles.formGroup}>
										<label>Skills (comma-separated)</label>
										<input
											type="text"
											value={bioData.skills.join(", ")}
											onChange={(e) =>
												setBioData({
													...bioData,
													skills: e.target.value
														.split(",")
														.map((skill) =>
															skill.trim()
														),
												})
											}
										/>
									</div>

									<button
										type="submit"
										className={styles.updateButton}
									>
										Update Profile
									</button>
								</form>
							</section>
						)}

						{/* Applications Tab */}
						{activeTab === "applications" && (
							<section className={styles.applicationsSection}>
								<h2>Job Applications</h2>
								<div className={styles.applicationsList}>
									{sortedApplications.length > 0 ? (
										sortedApplications.map((app) => {
											const liveInterviews =
												getLiveInterviews(app);
											return (
												<div
													key={app.id}
													className={`${
														styles.applicationCard
													} ${
														liveInterviews.length >
														0
															? styles.liveInterview
															: ""
													}`}
												>
													<div
														className={
															styles.applicationHeader
														}
													>
														<h3>{app.position}</h3>
														<div
															className={
																styles.headerBadges
															}
														>
															{liveInterviews.length >
																0 && (
																<span
																	className={
																		styles.liveBadge
																	}
																>
																	<i className="fa fa-video-camera"></i>{" "}
																	Live
																	Interview
																</span>
															)}
															<span
																className={`${
																	styles.statusBadge
																} ${
																	styles[
																		app.status
																			.toLowerCase()
																			.replace(
																				" ",
																				""
																			)
																	]
																}`}
															>
																{app.status}
															</span>
														</div>
													</div>
													<div
														className={
															styles.applicationDetails
														}
													>
														<p
															className={
																styles.company
															}
														>
															<i className="fa fa-building"></i>{" "}
															{app.company}
														</p>
														<p
															className={
																styles.date
															}
														>
															<i className="fa fa-calendar"></i>{" "}
															Applied on:{" "}
															{new Date(
																app.appliedDate
															).toLocaleDateString()}
														</p>
													</div>
													{app.interviews.length >
														0 && (
														<div
															className={
																styles.interviews
															}
														>
															<h4>Interviews</h4>
															<ul>
																{app.interviews.map(
																	(
																		interview,
																		idx
																	) => {
																		const isLive =
																			isInterviewLive(
																				interview
																			);
																		return (
																			<li
																				key={
																					idx
																				}
																				className={
																					isLive
																						? styles.liveInterviewItem
																						: ""
																				}
																			>
																				<span
																					className={
																						styles.interviewType
																					}
																				>
																					{
																						interview.type
																					}
																				</span>
																				<span
																					className={
																						styles.interviewDateTime
																					}
																				>
																					{new Date(
																						interview.date
																					).toLocaleDateString()}{" "}
																					at{" "}
																					{
																						interview.time
																					}
																				</span>
																				{isLive &&
																					interview.meetingLink && (
																						<a
																							href={
																								interview.meetingLink
																							}
																							target="_blank"
																							rel="noopener noreferrer"
																							className={
																								styles.joinButton
																							}
																						>
																							<i className="fa fa-video-camera"></i>{" "}
																							Join
																						</a>
																					)}
																			</li>
																		);
																	}
																)}
															</ul>
														</div>
													)}
													<div
														className={
															styles.applicationActions
														}
													>
														<Link
															to={`/application/${app.id}`}
															className={
																styles.viewTimelineButton
															}
														>
															<i className="fa fa-info-circle"></i>{" "}
															View Application
															Details
														</Link>
													</div>
												</div>
											);
										})
									) : (
										<p className={styles.noApplications}>
											No job applications yet.
										</p>
									)}
								</div>
							</section>
						)}
					</div>
				</div>
			</div>
		</div>
	);
};

export default Profile;

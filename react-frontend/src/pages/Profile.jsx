import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import styles from "./Profile.module.css";

const Profile = () => {
	const navigate = useNavigate();
	const [cvFile, setCvFile] = useState(null);
	const [cvFilePath, setCvFilePath] = useState(null);
	const [isUploading, setIsUploading] = useState(false);
	const [bioData, setBioData] = useState({
		name: "John Doe",
		email: "john.doe@example.com",
		phone: "+1 (555) 123-4567",
		location: "New York, USA",
		title: "Senior Software Engineer",
		about: "Experienced software engineer with 5+ years of experience in developing web applications using modern technologies.",
		skills: ["JavaScript", "React", "Node.js", "Python", "Docker"],
	});

	// Sample job applications data
	const [applications, setApplications] = useState([
		{
			id: 1,
			company: "Tech Innovations Inc.",
			position: "Senior Frontend Developer",
			appliedDate: "2023-08-15",
			status: "In Progress",
			interviews: [{ date: "2023-08-25", type: "Technical" }],
		},
		{
			id: 2,
			company: "Global Systems",
			position: "Full-Stack Developer",
			appliedDate: "2023-07-10",
			status: "Rejected",
			interviews: [],
		},
		{
			id: 3,
			company: "DataViz Solutions",
			position: "React Developer",
			appliedDate: "2023-09-01",
			status: "Shortlisted",
			interviews: [
				{ date: "2023-09-15", type: "HR Round" },
				{ date: "2023-09-20", type: "Technical" },
			],
		},
	]);

	// Sample upcoming interviews data
	const [upcomingInterviews, setUpcomingInterviews] = useState([
		{
			id: 123,
			position: "Technical Interview - Software Engineer",
			company: "Tech Innovations Inc.",
			date: "2023-09-15",
			time: "10:00 AM",
		},
		{
			id: 456,
			position: "HR Discussion - React Developer",
			company: "DataViz Solutions",
			date: "2023-09-28",
			time: "2:30 PM",
		},
	]);

	// Check authentication when component mounts
	useEffect(() => {
		const isLoggedIn = localStorage.getItem("candidateLoggedIn") === "true";
		if (!isLoggedIn) {
			navigate("/login");
		}
	}, [navigate]);

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

					{/* Application Statistics Card - Moved from Dashboard */}
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
												location: e.target.value,
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
												.map((skill) => skill.trim()),
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

					{/* Upcoming Interviews Section - Moved from Dashboard */}
					<section className={styles.interviewsSection}>
						<h2>Upcoming Interviews</h2>
						<div className={styles.interviewsList}>
							{upcomingInterviews.length > 0 ? (
								upcomingInterviews.map((interview) => (
									<div
										key={interview.id}
										className={styles.interviewItem}
									>
										<div className={styles.interviewInfo}>
											<h4>{interview.position}</h4>
											<p>{interview.company}</p>
										</div>
										<div className={styles.interviewMeta}>
											<div
												className={
													styles.interviewDateTime
												}
											>
												<i className="fa fa-calendar"></i>
												<span>
													{new Date(
														interview.date
													).toLocaleDateString()}
													, {interview.time}
												</span>
											</div>
											<Link
												to={`/interview/${interview.id}`}
												className={
													styles.interviewButton
												}
											>
												Join
											</Link>
										</div>
									</div>
								))
							) : (
								<p className={styles.noInterviews}>
									No upcoming interviews scheduled.
								</p>
							)}
						</div>
					</section>

					<section className={styles.applicationsSection}>
						<h2>Job Applications</h2>
						<div className={styles.applicationsList}>
							{applications.length > 0 ? (
								applications.map((app) => (
									<div
										key={app.id}
										className={styles.applicationCard}
									>
										<div
											className={styles.applicationHeader}
										>
											<h3>{app.position}</h3>
											<span
												className={`${
													styles.statusBadge
												} ${
													styles[
														app.status
															.toLowerCase()
															.replace(" ", "")
													]
												}`}
											>
												{app.status}
											</span>
										</div>
										<div
											className={
												styles.applicationDetails
											}
										>
											<p className={styles.company}>
												<i className="fa fa-building"></i>{" "}
												{app.company}
											</p>
											<p className={styles.date}>
												<i className="fa fa-calendar"></i>{" "}
												Applied on:{" "}
												{new Date(
													app.appliedDate
												).toLocaleDateString()}
											</p>
										</div>
										{app.interviews.length > 0 && (
											<div className={styles.interviews}>
												<h4>Interviews</h4>
												<ul>
													{app.interviews.map(
														(interview, idx) => (
															<li key={idx}>
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
																		styles.interviewDate
																	}
																>
																	{new Date(
																		interview.date
																	).toLocaleDateString()}
																</span>
															</li>
														)
													)}
												</ul>
											</div>
										)}
									</div>
								))
							) : (
								<p className={styles.noApplications}>
									No job applications yet.
								</p>
							)}
						</div>
					</section>
				</div>
			</div>
		</div>
	);
};

export default Profile;

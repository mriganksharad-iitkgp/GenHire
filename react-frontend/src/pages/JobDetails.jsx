import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import styles from "./JobDetails.module.css";

const JobDetails = () => {
	const { jobId } = useParams();
	const navigate = useNavigate();
	const [job, setJob] = useState(null);
	const [isLoading, setIsLoading] = useState(true);
	const [applyModalOpen, setApplyModalOpen] = useState(false);

	// Sample job data - in a real app, this would be fetched from an API
	const sampleJobs = {
		1001: {
			id: 1001,
			title: "Senior Frontend Developer",
			company: "Tech Innovations Inc.",
			logo: "../android-chrome-192x192.png",
			location: "San Francisco, CA (Remote)",
			type: "Full-time",
			experience: "5+ years",
			postedDate: "2023-09-01",
			skills: [
				"React",
				"TypeScript",
				"GraphQL",
				"Redux",
				"Jest",
				"CSS/SASS",
				"Responsive Design",
			],
			salary: "$120,000 - $150,000",
			description:
				"We are looking for an experienced Frontend Developer with expertise in React to join our growing team. You will be responsible for building user interfaces for our web applications, collaborating with UX designers, and implementing responsive designs.",
			responsibilities: [
				"Develop new user-facing features using React.js",
				"Build reusable components for future use",
				"Translate designs and wireframes into high-quality code",
				"Optimize applications for maximum performance",
				"Collaborate with back-end developers and web designers",
				"Troubleshoot and debug applications",
			],
			requirements: [
				"5+ years of experience with frontend development",
				"Strong proficiency in React, Redux, and TypeScript",
				"Experience with GraphQL and RESTful APIs",
				"Thorough understanding of responsive design principles",
				"Knowledge of testing and debugging processes",
				"Excellent problem-solving skills and attention to detail",
			],
			benefits: [
				"Competitive salary and equity",
				"Health, dental, and vision insurance",
				"Flexible work schedule",
				"Remote work options",
				"Professional development budget",
				"401(k) matching",
			],
		},
		1002: {
			id: 1002,
			title: "Full Stack Engineer",
			company: "Global Systems",
			logo: "../android-chrome-192x192.png",
			location: "New York, NY",
			type: "Full-time",
			experience: "3+ years",
			postedDate: "2023-09-05",
			skills: [
				"Node.js",
				"React",
				"MongoDB",
				"AWS",
				"Express",
				"JavaScript",
				"Docker",
			],
			salary: "$130,000 - $160,000",
			description:
				"Join our engineering team to build innovative solutions for enterprise clients. As a Full Stack Engineer, you will design and implement features across the entire stack and contribute to our technological decisions.",
			responsibilities: [
				"Develop and maintain web applications using Node.js and React",
				"Design and implement database schemas and APIs",
				"Work with cloud services, primarily AWS",
				"Participate in code reviews and ensure code quality",
				"Collaborate with product managers and designers",
				"Mentor junior developers",
			],
			requirements: [
				"3+ years of experience in full stack development",
				"Proficiency in Node.js, React, and MongoDB",
				"Experience with AWS or other cloud platforms",
				"Knowledge of containerization with Docker",
				"Solid understanding of JavaScript and web development fundamentals",
				"Experience with CI/CD pipelines",
			],
			benefits: [
				"Competitive compensation package",
				"Comprehensive health benefits",
				"Unlimited PTO",
				"Home office stipend",
				"Learning and development allowance",
				"Regular team events and retreats",
			],
		},
	};

	// Check authentication and load job data
	useEffect(() => {
		const isLoggedIn = localStorage.getItem("candidateLoggedIn") === "true";
		if (!isLoggedIn) {
			navigate("/login");
			return;
		}

		// Simulate API call to fetch job data
		setIsLoading(true);
		setTimeout(() => {
			if (sampleJobs[jobId]) {
				setJob(sampleJobs[jobId]);
			} else {
				// If job not found, set a generic job with placeholder info
				setJob({
					id: jobId,
					title: "Job Position",
					company: "Example Company",
					logo: "../android-chrome-192x192.png",
					location: "Remote",
					type: "Full-time",
					experience: "Not specified",
					postedDate: new Date().toISOString().split("T")[0],
					skills: ["Skill 1", "Skill 2", "Skill 3"],
					salary: "Competitive",
					description:
						"This is a placeholder for a job that will be implemented later.",
					responsibilities: [
						"Responsibility 1",
						"Responsibility 2",
						"Responsibility 3",
					],
					requirements: [
						"Requirement 1",
						"Requirement 2",
						"Requirement 3",
					],
					benefits: ["Benefit 1", "Benefit 2", "Benefit 3"],
				});
			}
			setIsLoading(false);
		}, 800);
	}, [jobId, navigate]);

	if (isLoading) {
		return (
			<div className={styles.loadingContainer}>
				<div className={styles.loader}></div>
				<p>Loading job details...</p>
			</div>
		);
	}

	return (
		<div className={styles.jobDetailsContainer}>
			<div className={styles.content}>
				<div className={styles.jobHeader}>
					<div className={styles.companyLogo}>
						<img src={job.logo} alt={job.company} />
					</div>
					<div className={styles.jobInfo}>
						<h1>{job.title}</h1>
						<div className={styles.companyDetails}>
							<span className={styles.company}>
								{job.company}
							</span>
							<span className={styles.location}>
								<i className="fa fa-map-marker"></i>{" "}
								{job.location}
							</span>
							<span className={styles.jobType}>{job.type}</span>
						</div>
						<div className={styles.metaDetails}>
							<span className={styles.experience}>
								<i className="fa fa-briefcase"></i> Experience:{" "}
								{job.experience}
							</span>
							<span className={styles.salary}>
								<i className="fa fa-money"></i> {job.salary}
							</span>
							<span className={styles.postedDate}>
								<i className="fa fa-calendar"></i> Posted:{" "}
								{new Date(job.postedDate).toLocaleDateString()}
							</span>
						</div>
					</div>
					<div className={styles.actions}>
						<button
							className={styles.applyButton}
							onClick={() => setApplyModalOpen(true)}
						>
							Apply Now
						</button>
						<button className={styles.saveButton}>
							<i className="fa fa-bookmark-o"></i> Save
						</button>
					</div>
				</div>

				<div className={styles.jobBody}>
					<div className={styles.mainDetails}>
						<section className={styles.section}>
							<h2>Description</h2>
							<p>{job.description}</p>
						</section>

						<section className={styles.section}>
							<h2>Key Responsibilities</h2>
							<ul>
								{job.responsibilities.map((item, index) => (
									<li key={index}>{item}</li>
								))}
							</ul>
						</section>

						<section className={styles.section}>
							<h2>Requirements</h2>
							<ul>
								{job.requirements.map((item, index) => (
									<li key={index}>{item}</li>
								))}
							</ul>
						</section>

						<section className={styles.section}>
							<h2>Benefits</h2>
							<ul>
								{job.benefits.map((item, index) => (
									<li key={index}>{item}</li>
								))}
							</ul>
						</section>
					</div>

					<div className={styles.sideDetails}>
						<div className={styles.infoCard}>
							<h3>Skills</h3>
							<div className={styles.skillTags}>
								{job.skills.map((skill, index) => (
									<span
										key={index}
										className={styles.skillTag}
									>
										{skill}
									</span>
								))}
							</div>
						</div>

						<div className={styles.infoCard}>
							<h3>About Company</h3>
							<div className={styles.companyBox}>
								<img src={job.logo} alt={job.company} />
								<h4>{job.company}</h4>
								<p>
									This company information will be implemented
									in a future update.
								</p>
							</div>
						</div>

						<div className={styles.applyCard}>
							<h3>Interested in this job?</h3>
							<button
								className={styles.applyNowBtn}
								onClick={() => setApplyModalOpen(true)}
							>
								Apply Now
							</button>
							<p>or</p>
							<Link
								to="/profile"
								className={styles.updateProfileLink}
							>
								Update your profile first
							</Link>
						</div>
					</div>
				</div>
			</div>

			{/* Application Modal - Placeholder for future implementation */}
			{applyModalOpen && (
				<div className={styles.modalOverlay}>
					<div className={styles.modal}>
						<div className={styles.modalHeader}>
							<h3>Apply for {job.title}</h3>
							<button
								className={styles.closeButton}
								onClick={() => setApplyModalOpen(false)}
							>
								<i className="fa fa-times"></i>
							</button>
						</div>
						<div className={styles.modalBody}>
							<p>
								The application form will be implemented in a
								future update.
							</p>
							<p>
								For now, this is a placeholder to show the
								application flow.
							</p>
							<div className={styles.formPlaceholder}>
								<div className={styles.formField}></div>
								<div className={styles.formField}></div>
								<div className={styles.formField}></div>
							</div>
						</div>
						<div className={styles.modalFooter}>
							<button
								className={styles.cancelButton}
								onClick={() => setApplyModalOpen(false)}
							>
								Cancel
							</button>
							<button
								className={styles.submitButton}
								onClick={() => {
									alert(
										"Application submitted successfully!"
									);
									setApplyModalOpen(false);
								}}
							>
								Submit Application
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default JobDetails;

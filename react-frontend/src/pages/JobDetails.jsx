import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import styles from "./JobDetails.module.css";

const JobDetails = () => {
	const { jobId } = useParams();
	const navigate = useNavigate();
	const [job, setJob] = useState(null);
	const [isLoading, setIsLoading] = useState(true);
	const [applyModalOpen, setApplyModalOpen] = useState(false);
	const [matchScoreModalOpen, setMatchScoreModalOpen] = useState(false);
	const [matchScore, setMatchScore] = useState(null);

	// Function to handle PDF download
	const handleDownloadPDF = () => {
		// In a real app, you would generate a PDF on the server or use a library like jsPDF
		// Here we'll simulate a download by creating a simple text blob

		if (!job) return;

		const jobTitle = job.title;
		const jobContent = `
Job Description: ${job.title}
Company: ${job.company}
Location: ${job.location}
Job Type: ${job.type}
Experience: ${job.experience}
Salary: ${job.salary}
Posted Date: ${job.postedDate}

Description:
${job.description}

Key Responsibilities:
${job.responsibilities.map((resp) => `- ${resp}`).join("\n")}

Requirements:
${job.requirements.map((req) => `- ${req}`).join("\n")}

Benefits:
${job.benefits.map((benefit) => `- ${benefit}`).join("\n")}
		`;

		const blob = new Blob([jobContent], { type: "text/plain" });
		const url = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.href = url;
		link.download = `${jobTitle.replace(/\s+/g, "-")}-Job-Description.txt`;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(url);
	};

	// Function to check CV match score
	const handleCheckMatchScore = () => {
		// In a real app, this would call an API to analyze the user's CV against the job
		// Here we'll simulate a backend response with just a percentage
		setIsLoading(true);

		setTimeout(() => {
			// Generate a random score between 60 and 95 to simulate backend response
			const score = Math.floor(Math.random() * 36) + 60;
			setMatchScore(score);
			setMatchScoreModalOpen(true);
			setIsLoading(false);
		}, 1000);
	};

	// Sample job data - in a real app, this would be fetched from an API
	const sampleJobs = {
		1001: {
			id: 1001,
			title: "Senior Business Development Manager",
			company: "CompanyXYZ",
			logo: "../android-chrome-192x192.png",
			location: "San Francisco, CA (Remote)",
			type: "Full-time",
			experience: "5+ years",
			postedDate: "2023-09-01",
			skills: [
				"Sales Strategy",
				"Client Acquisition",
				"Market Research",
				"Negotiation",
				"CRM Software",
				"Business Planning",
				"Revenue Growth",
			],
			salary: "$120,000 - $150,000",
			description:
				"We are looking for an experienced Business Development Manager to join our growing team. You will be responsible for identifying new business opportunities, developing client relationships, and contributing to our overall growth strategy.",
			responsibilities: [
				"Develop and execute business development strategies",
				"Identify and pursue new market opportunities",
				"Build and maintain relationships with key clients and partners",
				"Negotiate and close business deals",
				"Collaborate with marketing and sales teams",
				"Track and report on business development metrics",
			],
			requirements: [
				"5+ years of experience in business development",
				"Strong track record of identifying opportunities and closing deals",
				"Experience with CRM systems and sales processes",
				"Excellent communication and presentation skills",
				"Strategic thinking and analytical abilities",
				"Results-oriented mindset with excellent negotiation skills",
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
			title: "Strategic Partnerships Manager",
			company: "CompanyXYZ",
			logo: "../android-chrome-192x192.png",
			location: "New York, NY",
			type: "Full-time",
			experience: "3+ years",
			postedDate: "2023-09-05",
			skills: [
				"Partnership Management",
				"Relationship Building",
				"Contract Negotiation",
				"Business Strategy",
				"Market Analysis",
				"Revenue Growth",
				"Account Management",
			],
			salary: "$130,000 - $160,000",
			description:
				"Join our business team to develop strategic partnerships for our enterprise solutions. As a Strategic Partnerships Manager, you will identify and cultivate relationships with key partners to drive mutual growth and success.",
			responsibilities: [
				"Identify and develop strategic partnership opportunities",
				"Build and manage relationships with key stakeholders",
				"Negotiate partnership agreements and contracts",
				"Develop joint business plans with partners",
				"Collaborate with product and marketing teams",
				"Monitor partnership performance and optimize strategies",
			],
			requirements: [
				"3+ years of experience in partnership management or business development",
				"Proven track record of building successful partnerships",
				"Experience with contract negotiation and relationship management",
				"Strong business acumen and strategic thinking",
				"Excellent communication and interpersonal skills",
				"Ability to work cross-functionally and drive results",
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
					company: "CompanyXYZ",
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
						<button
							className={styles.saveButton}
							onClick={handleDownloadPDF}
						>
							<i className="fa fa-file-pdf-o"></i> Download JD
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
									Join our team at CompanyXYZ and be part of
									our mission to innovate and transform the
									industry. We offer competitive benefits and
									a collaborative work environment.
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
							<button
								className={styles.downloadJdBtn}
								onClick={handleDownloadPDF}
							>
								<i className="fa fa-file-pdf-o"></i> Download
								Job Description
							</button>
							<button
								className={styles.matchScoreBtn}
								onClick={handleCheckMatchScore}
							>
								<i className="fa fa-check-circle"></i> Check CV
								Match Score
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

			{/* Match Score Modal - Simplified to just show percentage */}
			{matchScoreModalOpen && (
				<div className={styles.modalOverlay}>
					<div className={styles.modal}>
						<div className={styles.modalHeader}>
							<h3>CV Match Score</h3>
							<button
								className={styles.closeButton}
								onClick={() => setMatchScoreModalOpen(false)}
							>
								<i className="fa fa-times"></i>
							</button>
						</div>
						<div className={styles.modalBody}>
							<div className={styles.matchScoreResult}>
								<div
									className={styles.scoreCircle}
									style={{ "--score": `${matchScore}%` }}
								>
									<span className={styles.scoreValue}>
										{matchScore}%
									</span>
								</div>
								<div className={styles.scoreDetails}>
									<h4>
										Your CV matches {matchScore}% of the job
										requirements
									</h4>
									<p>
										This score is generated based on how
										your skills and experience align with
										the job requirements.
									</p>
								</div>
							</div>
						</div>
						<div className={styles.modalFooter}>
							<button
								className={styles.cancelButton}
								onClick={() => setMatchScoreModalOpen(false)}
							>
								Close
							</button>
							<button
								className={styles.submitButton}
								onClick={() => {
									setMatchScoreModalOpen(false);
									setApplyModalOpen(true);
								}}
							>
								Apply Now
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default JobDetails;

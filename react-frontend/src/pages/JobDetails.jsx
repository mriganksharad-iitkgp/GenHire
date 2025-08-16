import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import Toast from "../components/Toast";
import styles from "./JobDetails.module.css";

const JobDetails = () => {
	const { jobId } = useParams();
	const navigate = useNavigate();
	const [job, setJob] = useState(null);
	const [isLoading, setIsLoading] = useState(true);
	const [applyModalOpen, setApplyModalOpen] = useState(false);
	const [matchScoreModalOpen, setMatchScoreModalOpen] = useState(false);
	const [matchScore, setMatchScore] = useState(null);
	const [userType, setUserType] = useState("candidate");
	const [hasApplied, setHasApplied] = useState(false);
	const [appliedAt, setAppliedAt] = useState(null);
	const [applicationStatus, setApplicationStatus] = useState(null);
	const [pendingWithdrawal, setPendingWithdrawal] = useState(false);
	
	// Toast state
	const [toast, setToast] = useState(null);

	// Show toast function
	const showToast = (message, type = 'info') => {
		setToast({ message, type });
	};

	// Utility to normalize list-like fields
	const toList = (val) => {
		if (!val) return [];
		if (Array.isArray(val)) return val.filter((x) => String(x).trim());
		const txt = String(val).replace(/\r/g, '').trim();
		if (!txt) return [];
		// split on newlines first, then commas
		const parts = [];
		txt.split('\n').forEach(line => {
			line.split(',').forEach(p => {
				const s = p.trim();
				if (s) parts.push(s);
			});
		});
		return parts;
	};

	// Load job details from backend
	useEffect(() => {
		const init = async () => {
			const token = localStorage.getItem("companyxyz-token");
			const user = JSON.parse(localStorage.getItem("companyxyz-user") || "null");
			if (!token) {
				navigate("/login");
				return;
			}
			setUserType(user?.user_type || user?.userType || "candidate");
			setIsLoading(true);
			try {
				const res = await fetch(`http://localhost:5000/api/jobs/${jobId}`, {
					headers: {
						Authorization: `Bearer ${token}`,
					},
				});
				if (!res.ok) {
					throw new Error("Failed to load job");
				}
				const data = await res.json();
				// Normalize fields for UI fallbacks
				setJob({
					...data,
					company: data.company || "TechCorp Solutions",
					logo: data.logo || "../android-chrome-192x192.png",
					responsibilities: toList(data.responsibilities),
					requirements: toList(data.requirements),
					benefits: toList(data.benefits),
					postedDate: data.created_at || data.postedDate || new Date().toISOString(),
					skills: Array.isArray(data.skills) ? data.skills : toList(data.skills),
					salary: data.salary || "Competitive",
					experience: data.experience || "Not specified",
				});

				// Check if user has already applied to this job
				try {
					const appsRes = await fetch('http://localhost:5000/api/applications', {
						headers: { Authorization: `Bearer ${token}` }
					});
					if (appsRes.ok) {
						const apps = await appsRes.json();
						const found = (apps || []).find(a => String(a.job_id) === String(jobId) || String(a.job_details?._id) === String(jobId));
						if (found) {
							setHasApplied(true);
							setAppliedAt(found.applied_at || null);
							setApplicationStatus(found.status || 'pending');
						}
					}
				} catch (e) {
					// ignore app check errors
				}
			} catch (e) {
				// Fallback to a minimal placeholder if fetch fails
				setJob({
					id: jobId,
					title: "Job Position",
					company: "TechCorp Solutions",
					logo: "../android-chrome-192x192.png",
					location: "Remote",
					type: "Full-time",
					experience: "Not specified",
					postedDate: new Date().toISOString(),
					skills: ["Skill 1", "Skill 2", "Skill 3"],
					salary: "Competitive",
					description:
						"This is a placeholder for a job that will be implemented later.",
					responsibilities: ["Responsibility 1", "Responsibility 2", "Responsibility 3"],
					requirements: ["Requirement 1", "Requirement 2", "Requirement 3"],
					benefits: ["Benefit 1", "Benefit 2", "Benefit 3"],
				});
			} finally {
				setIsLoading(false);
			}
		};
		init();
	}, [jobId, navigate]);

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
	// Apply for job from details page
	const handleApply = async () => {
		const token = localStorage.getItem("companyxyz-token");
		if (!token) {
			navigate("/login");
			return;
		}
		try {
			const res = await fetch(`http://localhost:5000/api/jobs/${jobId}/apply`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${token}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					cover_letter: `I am interested in applying for ${job?.title}.`
				})
			});
			const data = await res.json();
			if (!res.ok) {
				showToast(data.error || 'Failed to submit application', 'error');
				return;
			}
			showToast('Application submitted successfully!', 'success');
			setApplyModalOpen(false);
			// Optimistically toggle applied state for immediate UX feedback
			setHasApplied(true);
			setAppliedAt(new Date().toISOString());
			setApplicationStatus('pending');
		} catch (e) {
			showToast('Failed to submit application', 'error');
		}
	};

	// Withdraw application
	const handleWithdraw = async () => {
		const token = localStorage.getItem("companyxyz-token");
		if (!token) {
			navigate("/login");
			return;
		}

		// If this is the confirmation step
		if (pendingWithdrawal) {
			try {
				const res = await fetch(`http://localhost:5000/api/jobs/${jobId}/withdraw`, {
					method: 'DELETE',
					headers: {
						'Authorization': `Bearer ${token}`,
						'Content-Type': 'application/json'
					}
				});
				const data = await res.json();
				if (!res.ok) {
					showToast(data.error || 'Failed to withdraw application', 'error');
					return;
				}
				showToast('Application withdrawn successfully!', 'success');
				// Reset application state
				setHasApplied(false);
				setAppliedAt(null);
				setApplicationStatus(null);
				setPendingWithdrawal(false);
			} catch (e) {
				showToast('Failed to withdraw application', 'error');
				setPendingWithdrawal(false);
			}
		} else {
			// First click - show warning and set pending
			setPendingWithdrawal(true);
			showToast('Click "Withdraw Application" again to confirm. This action cannot be undone.', 'warning');
		}
	};

	// Check if withdrawal is allowed
	const canWithdraw = () => {
		return hasApplied && applicationStatus && ['pending', 'applied'].includes(applicationStatus.toLowerCase());
	};

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
						{hasApplied ? (
							canWithdraw() ? (
								<button
									onClick={handleWithdraw}
									className={`${styles.applyButton} ${styles.withdrawButton} ${pendingWithdrawal ? styles.confirmWithdraw : ''}`}
								>
									{pendingWithdrawal ? 'Confirm Withdrawal' : 'Withdraw Application'}
								</button>
							) : (
								<button
									className={`${styles.applyButton} ${styles.appliedButton}`}
									disabled
								>
									Application Submitted
								</button>
							)
						) : (
							<button
								className={styles.applyButton}
								onClick={() => setApplyModalOpen(true)}
								disabled={userType === 'recruiter'}
							>
								Apply Now
							</button>
						)}
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
							{toList(job.responsibilities).length ? (
								<ul>
									{toList(job.responsibilities).map((item, index) => (
										<li key={index}>{item}</li>
									))}
								</ul>
							) : (
								<p className={styles.muted}>Not specified</p>
							)}
						</section>

						<section className={styles.section}>
							<h2>Requirements</h2>
							{toList(job.requirements).length ? (
								<ul>
									{toList(job.requirements).map((item, index) => (
										<li key={index}>{item}</li>
									))}
								</ul>
							) : (
								<p className={styles.muted}>Not specified</p>
							)}
						</section>

						<section className={styles.section}>
							<h2>Benefits</h2>
							{toList(job.benefits).length ? (
								<ul>
									{toList(job.benefits).map((item, index) => (
										<li key={index}>{item}</li>
									))}
								</ul>
							) : (
								<p className={styles.muted}>Not specified</p>
							)}
						</section>
					</div>

					<div className={styles.sideDetails}>
						<div className={styles.infoCard}>
							<h3>Skills</h3>
							<div className={styles.skillTags}>
								{toList(job.skills).map((skill, index) => (
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
									Join our team at {job.company} and be part of
									our mission to innovate and transform the
									industry. We offer competitive benefits and
									a collaborative work environment.
								</p>
							</div>
						</div>

						<div className={styles.applyCard}>
							<h3>Interested in this job?</h3>
							{hasApplied ? (
								canWithdraw() ? (
									<button
										onClick={handleWithdraw}
										className={`${styles.applyNowBtn} ${styles.withdrawBtn} ${pendingWithdrawal ? styles.confirmWithdraw : ''}`}
									>
										{pendingWithdrawal ? 'Confirm Withdrawal' : 'Withdraw Application'}
									</button>
								) : (
									<button
										className={`${styles.applyNowBtn} ${styles.appliedBtn}`}
										disabled
									>
										Application Submitted
									</button>
								)
							) : (
								<button
									className={styles.applyNowBtn}
									onClick={() => setApplyModalOpen(true)}
									disabled={userType === 'recruiter'}
								>
									Apply Now
								</button>
							)}
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
							{hasApplied && appliedAt && (
								<p style={{ color: '#2f4ca3', fontWeight: 600, margin: '6px 0 0' }}>
									Applied on {new Date(appliedAt).toLocaleDateString()}
								</p>
							)}
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
							{userType === 'recruiter' ? (
								<button className={styles.submitButton} disabled>
									Recruiters cannot apply
								</button>
							) : (
								<button
									className={styles.submitButton}
									onClick={handleApply}
								>
									Submit Application
								</button>
							)}
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
			{toast && (
				<Toast
					message={toast.message}
					type={toast.type}
					onClose={() => setToast(null)}
				/>
			)}
		</div>
	);
};

export default JobDetails;

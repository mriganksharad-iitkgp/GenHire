import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import Toast from "../components/Toast";
import JobEditModal from "../components/JobEditModal";
import CVSelectionModal from "../components/CVSelectionModal";
import styles from "./JobDetails.module.css";
import InterviewReportModal from '../components/InterviewReportModal';
import { getToken, getUser, clearSession, isLoggedIn } from "../utils/sessionManager";
import { authedFetch } from "../utils/authedFetch";
import { useCandidateData } from "../contexts/CandidateDataContext";

const JobDetails = () => {
	const { jobId } = useParams();
	const navigate = useNavigate();
	const [job, setJob] = useState(null);
	const [isLoading, setIsLoading] = useState(true);
	const [isApplying, setIsApplying] = useState(false);
	const [showCVModal, setShowCVModal] = useState(false);
	const [matchScoreModalOpen, setMatchScoreModalOpen] = useState(false);
	const [matchScore, setMatchScore] = useState(null);
	const [userType, setUserType] = useState("candidate");
	const [hasApplied, setHasApplied] = useState(false);
	const [appliedAt, setAppliedAt] = useState(null);
	const [applicationStatus, setApplicationStatus] = useState(null);
	const [pendingWithdrawal, setPendingWithdrawal] = useState(false);
	const [isEditModalOpen, setIsEditModalOpen] = useState(false);
	
	const { invalidateApplications } = useCandidateData();
	
	// Toast state
	const [toast, setToast] = useState(null);

	// Show toast function
	const showToast = (message, type = 'info') => {
		setToast({ message, type });
	};

	const parseApplyResponse = async (response) => {
		const contentType = response.headers.get('content-type') || '';
		if (contentType.includes('application/json')) {
			return response.json();
		}

		const text = await response.text();
		return {
			error: text
				? `Server returned an unexpected response (${response.status}). Please try again.`
				: 'Failed to submit application'
		};
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

	// Format date utility
	const formatDate = (dateString) => {
		if (!dateString) return 'Not specified';
		try {
			return new Date(dateString).toLocaleDateString('en-US', {
				year: 'numeric',
				month: 'long',
				day: 'numeric'
			});
		} catch {
			return dateString;
		}
	};

	// Get status info for jobs
	const getStatusInfo = (status) => {
		const statusMap = {
			draft: { color: '#6b7280', label: 'Draft', description: 'Job is being prepared' },
			active: { color: '#10b981', label: 'Active', description: 'Job is live and accepting applications' },
			paused: { color: '#f59e0b', label: 'Paused', description: 'Job is temporarily stopped' },
			closed: { color: '#ef4444', label: 'Closed', description: 'Job is closed, no longer accepting applications' }
		};
		const normalizedStatus = String(status || 'active').toLowerCase();
		return statusMap[normalizedStatus] || statusMap.active;
	};

	// Load job details from backend
	useEffect(() => {
		const init = async () => {
			const token = getToken();
			const user = getUser();
			const currentUserType = user?.user_type || user?.userType || "candidate";
			setUserType(currentUserType);
			if (!token) {
				navigate("/login");
				return;
			}
			setIsLoading(true);
			try {
				const res = await authedFetch(`${process.env.REACT_APP_API_URL}/api/jobs/${jobId}`, {
					headers: {
						Authorization: `Bearer ${token}`,
					},
				});
				if (!res.ok) {
					throw new Error("Failed to load job");
				}
				const data = await res.json();
				// Normalize fields for UI fallbacks with comprehensive job data
				const jobData = {
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
					// Enhanced job information
					department: data.department || "General",
					deadline: data.deadline || null,
					updated_at: data.updated_at || data.created_at,
					status: data.status || 'active'
				};

				// Only add application statistics for recruiters
				if (currentUserType === 'recruiter') {
					jobData.applicants = data.applicants || 0;
					jobData.pending = data.pending || 0;
					jobData.interviewed = data.interviewed || 0;
					jobData.selected = data.selected || 0;
					jobData.rejected = data.rejected || 0;
				}

				setJob(jobData);

				// Check if user has already applied to this job. An invite-created
				// skeleton row exists before the candidate has actually submitted
				// (no cv_snapshot, processing_status='awaiting_candidate'); we treat
				// those as "not yet applied" so the Apply button stays available.
				try {
					const res = await authedFetch(`${process.env.REACT_APP_API_URL}/api/applications`, {
						headers: { Authorization: `Bearer ${token}` }
					});
					const appsRes = res;
					if (appsRes.ok) {
						const apps = await appsRes.json();
						const found = (apps || []).find(a => String(a.job_id) === String(jobId) || String(a.job_details?._id) === String(jobId));
						const isInviteSkeleton = !!found && (
							found.processing_status === 'awaiting_candidate' ||
							!found.cv_snapshot
						);
						if (found && !isInviteSkeleton) {
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
	const handleCVSelectionSubmit = async (cvSelection) => {
		const token = getToken();
		if (!token) {
			navigate("/login");
			return;
		}
		
		setIsApplying(true);
		
		// Close modal and show success immediately for better UX
		setShowCVModal(false);
		showToast('Application submitted! CV scoring is being processed...', 'success');
		
		// Optimistically toggle applied state for immediate UX feedback
		setHasApplied(true);
		setAppliedAt(new Date().toISOString());
		setApplicationStatus('pending');
		setIsApplying(false);
		
		try {
			const res = await authedFetch(`${process.env.REACT_APP_API_URL}/api/jobs/${jobId}/apply`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${token}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					cv_id: cvSelection.cv_id,
					use_manual_cv: cvSelection.use_manual_cv,
					cover_letter: `I am interested in applying for ${job?.title}.`
				})
			});
			const data = await parseApplyResponse(res);
			if (!res.ok) {
				// Revert optimistic update on error
				setHasApplied(false);
				setAppliedAt(null);
				setApplicationStatus(null);
				showToast(data.error || 'Failed to submit application', 'error');
				return;
			}
			// Application successful - backend is processing CV score
			invalidateApplications();
		} catch (e) {
			// Revert optimistic update on error
			setHasApplied(false);
			setAppliedAt(null);
			setApplicationStatus(null);
			showToast('Failed to submit application', 'error');
		}
	};

	// Withdraw application
	const handleWithdraw = async () => {
		const token = getToken();
		if (!token) {
			navigate("/login");
			return;
		}

		// If this is the confirmation step
		if (pendingWithdrawal) {
			try {
				const res = await authedFetch(`${process.env.REACT_APP_API_URL}/api/jobs/${jobId}/withdraw`, {
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
				invalidateApplications();
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

	// Handle job update
	const handleJobUpdate = async (updatedJobData) => {
		try {
			const token = getToken();
			if (!token) {
				navigate("/login");
				return;
			}

			const response = await authedFetch(`${process.env.REACT_APP_API_URL}/api/jobs/${jobId}`, {
				method: 'PUT',
				headers: {
					'Authorization': `Bearer ${token}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(updatedJobData)
			});

			if (!response.ok) {
				throw new Error('Failed to update job');
			}

			const updatedJob = await response.json();
			
			// Update local job state
			setJob({
				...updatedJob,
				company: updatedJob.company || "TechCorp Solutions",
				logo: updatedJob.logo || "../android-chrome-192x192.png",
				responsibilities: toList(updatedJob.responsibilities),
				requirements: toList(updatedJob.requirements),
				benefits: toList(updatedJob.benefits),
				postedDate: updatedJob.created_at || updatedJob.postedDate || new Date().toISOString(),
				skills: Array.isArray(updatedJob.skills) ? updatedJob.skills : toList(updatedJob.skills),
				salary: updatedJob.salary || "Competitive",
				experience: updatedJob.experience || "Not specified",
			});

			setIsEditModalOpen(false);
			showToast('Job updated successfully! 🎉', 'success');
		} catch (error) {
			console.error('Error updating job:', error);
			showToast('Failed to update job. Please try again.', 'error');
			throw error;
		}
	};

	if (isLoading) {
		return (
			<div className={styles.loadingContainer}>
				<div className={styles.loader}></div>
				<p>Loading job details...</p>
			</div>
		);
	}

	const statusInfo = getStatusInfo(job?.status);

	return (
		<div className={styles.jobDetailsContainer}>
			<div className={styles.content}>
				{/* Enhanced Job Header with Status */}
				<div className={styles.jobHeader}>
					<div className={styles.headerContent}>
						<div className={styles.titleSection}>
							<div className={styles.companyLogo}>
								<img src={job.logo} alt={job.company} />
							</div>
							<div className={styles.jobInfo}>
								<h1 className={styles.jobTitle}>{job.title}</h1>
								<div className={styles.companyDetails}>
									<span className={styles.company}>
										<i className="fa fa-building"></i>
										{job.company}
									</span>
									<span className={styles.location}>
										<i className="fa fa-map-marker"></i>
										{job.location}
									</span>
									<span className={styles.jobType}>{job.type}</span>
								</div>
							</div>
						</div>
						<div className={styles.statusSection}>
							<div 
								className={styles.statusBadge}
								style={{ backgroundColor: statusInfo.color }}
							>
								<i className="fa fa-circle"></i>
								{statusInfo.label}
							</div>
							<small className={styles.statusDescription}>
								{statusInfo.description}
							</small>
						</div>
					</div>
					<div className={styles.actions}>
						{userType === 'recruiter' ? (
							<>
								<button
									className={styles.editButton}
									onClick={() => setIsEditModalOpen(true)}
								>
									<i className="fa fa-edit"></i> Edit Job
								</button>
								<button
									className={styles.saveButton}
									onClick={handleDownloadPDF}
								>
									<i className="fa fa-file-pdf-o"></i> Download JD
								</button>
							</>
						) : (
							<>
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
										onClick={() => setShowCVModal(true)}
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
							</>
						)}
					</div>
				</div>

				<div className={styles.jobBody}>
					{/* Key Information Grid */}
					<div className={styles.keyInfoGrid}>
						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-sitemap"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Department</span>
								<span className={styles.infoValue}>{job.department}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-map-marker"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Location</span>
								<span className={styles.infoValue}>{job.location}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-clock-o"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Job Type</span>
								<span className={styles.infoValue}>{job.type}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-user-o"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Experience</span>
								<span className={styles.infoValue}>{job.experience}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-money"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Salary Range</span>
								<span className={styles.infoValue}>{job.salary}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-calendar"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Posted Date</span>
								<span className={styles.infoValue}>{formatDate(job.created_at)}</span>
							</div>
						</div>

						{job.deadline && (
							<div className={styles.infoCard}>
								<div className={styles.infoIcon}>
									<i className="fa fa-calendar-check-o"></i>
								</div>
								<div className={styles.infoContent}>
									<span className={styles.infoLabel}>Application Deadline</span>
									<span className={styles.infoValue}>{formatDate(job.deadline)}</span>
								</div>
							</div>
						)}

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-refresh"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Last Updated</span>
								<span className={styles.infoValue}>{formatDate(job.updated_at)}</span>
							</div>
						</div>
					</div>

					{/* Application Statistics - Only visible to recruiters */}
					{userType === 'recruiter' && (
						<div className={styles.section}>
							<h3 className={styles.sectionTitle}>
								<i className="fa fa-bar-chart"></i>
								Application Statistics
							</h3>
							<div className={styles.statsGrid}>
								<div className={styles.statCard}>
									<div className={styles.statIcon}>
										<i className="fa fa-users"></i>
									</div>
									<div className={styles.statContent}>
										<div className={styles.statNumber}>{job.applicants || 0}</div>
										<div className={styles.statLabel}>Total Applicants</div>
									</div>
								</div>

								<div className={styles.statCard}>
									<div className={styles.statIcon}>
										<i className="fa fa-hourglass-half"></i>
									</div>
									<div className={styles.statContent}>
										<div className={styles.statNumber}>{job.pending || 0}</div>
										<div className={styles.statLabel}>Pending Review</div>
									</div>
								</div>

								<div className={styles.statCard}>
									<div className={styles.statIcon}>
										<i className="fa fa-comments"></i>
									</div>
									<div className={styles.statContent}>
										<div className={styles.statNumber}>{job.interviewed || 0}</div>
										<div className={styles.statLabel}>Interviewed</div>
									</div>
								</div>

								<div className={styles.statCard}>
									<div className={styles.statIcon}>
										<i className="fa fa-check-circle"></i>
									</div>
									<div className={styles.statContent}>
										<div className={styles.statNumber}>{job.selected || 0}</div>
										<div className={styles.statLabel}>Selected</div>
									</div>
								</div>

								<div className={styles.statCard}>
									<div className={styles.statIcon}>
										<i className="fa fa-times-circle"></i>
									</div>
									<div className={styles.statContent}>
										<div className={styles.statNumber}>{job.rejected || 0}</div>
										<div className={styles.statLabel}>Rejected</div>
									</div>
								</div>
							</div>
						</div>
					)}

					<div className={styles.mainDetails}>
						{/* Enhanced Job Description */}
						<section className={styles.section}>
							<h2 className={styles.sectionTitle}>
								<i className="fa fa-file-text-o"></i>
								Job Description
							</h2>
							<div className={styles.contentCard}>
								<p className={styles.description}>{job.description}</p>
							</div>
						</section>

						{/* Enhanced Key Responsibilities */}
						<section className={styles.section}>
							<h2 className={styles.sectionTitle}>
								<i className="fa fa-tasks"></i>
								Key Responsibilities
							</h2>
							<div className={styles.contentCard}>
								{toList(job.responsibilities).length ? (
									<ul className={styles.listItems}>
										{toList(job.responsibilities).map((item, index) => (
											<li key={index} className={styles.listItem}>
												<i className="fa fa-check"></i>
												{item}
											</li>
										))}
									</ul>
								) : (
									<p className={styles.muted}>Not specified</p>
								)}
							</div>
						</section>

						{/* Enhanced Requirements */}
						<section className={styles.section}>
							<h2 className={styles.sectionTitle}>
								<i className="fa fa-graduation-cap"></i>
								Qualifications & Requirements
							</h2>
							<div className={styles.contentCard}>
								{toList(job.requirements).length ? (
									<ul className={styles.listItems}>
										{toList(job.requirements).map((item, index) => (
											<li key={index} className={styles.listItem}>
												<i className="fa fa-circle"></i>
												{item}
											</li>
										))}
									</ul>
								) : (
									<p className={styles.muted}>Not specified</p>
								)}
							</div>
						</section>

						{/* Enhanced Benefits */}
						<section className={styles.section}>
							<h2 className={styles.sectionTitle}>
								<i className="fa fa-gift"></i>
								Benefits & Perks
							</h2>
							<div className={styles.contentCard}>
								{toList(job.benefits).length ? (
									<ul className={styles.listItems}>
										{toList(job.benefits).map((item, index) => (
											<li key={index} className={styles.listItem}>
												<i className="fa fa-plus"></i>
												{item}
											</li>
										))}
									</ul>
								) : (
									<p className={styles.muted}>Not specified</p>
								)}
							</div>
						</section>
					</div>

					<div className={styles.sideDetails}>
						{/* Enhanced Skills Section */}
						{job.skills && job.skills.length > 0 && (
							<div className={styles.section}>
								<h3 className={styles.sectionTitle}>
									<i className="fa fa-cogs"></i>
									Required Skills
									<span className={styles.skillCount}>({job.skills.length})</span>
								</h3>
								<div className={styles.contentCard}>
									<div className={styles.skillsContainer}>
										{job.skills.map((skill, index) => (
											<span key={index} className={styles.skillTag}>
												<i className="fa fa-star"></i>
												{skill}
											</span>
										))}
									</div>
								</div>
							</div>
						)}

						{/* Enhanced About Company Section */}
						<div className={styles.section}>
							<h3 className={styles.sectionTitle}>
								<i className="fa fa-building"></i>
								About Company
							</h3>
							<div className={styles.contentCard}>
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
						</div>

						<div className={styles.applyCard}>
							{userType === 'recruiter' ? (
								<>
									<h3><i className="fa fa-cog"></i> Manage Job</h3>
									<button
										className={styles.editJobBtn}
										onClick={() => setIsEditModalOpen(true)}
									>
										<i className="fa fa-edit"></i> Edit Job Details
									</button>
									<button
										className={styles.downloadJdBtn}
										onClick={handleDownloadPDF}
									>
										<i className="fa fa-file-pdf-o"></i> Download
										Job Description
									</button>
								</>
							) : (
								<>
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
											onClick={() => setShowCVModal(true)}
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
								</>
							)}
						</div>
					</div>
				</div>
			</div>

			{/* CV Selection Modal */}
			<CVSelectionModal
				isOpen={showCVModal}
				onClose={() => setShowCVModal(false)}
				onSubmit={handleCVSelectionSubmit}
				jobTitle={job?.title}
				mode="apply"
			/>

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
									setShowCVModal(true);
								}}
							>
								Apply Now
							</button>
						</div>
					</div>
				</div>
			)}

			{/* Job Edit Modal */}
			<JobEditModal
				isOpen={isEditModalOpen}
				onClose={() => setIsEditModalOpen(false)}
				onJobUpdate={handleJobUpdate}
				jobData={job}
			/>

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

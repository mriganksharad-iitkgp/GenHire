import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import Toast from "../components/Toast";
import styles from "./Dashboard.module.css";

const Dashboard = () => {
	const navigate = useNavigate();
	const [searchQuery, setSearchQuery] = useState("");
	const [typeFilter, setTypeFilter] = useState("");
	const [locationFilter, setLocationFilter] = useState("");
	const [experienceFilter, setExperienceFilter] = useState("");
	const [jobOpenings, setJobOpenings] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const [applications, setApplications] = useState([]);
	
	// Toast state
	const [toast, setToast] = useState(null);

	// Show toast function
	const showToast = (message, type = 'info') => {
		setToast({ message, type });
	};

	// Load jobs from backend
	useEffect(() => {
		loadJobs();
		loadApplications();
	}, []);

	const loadJobs = async () => {
		try {
			const token = localStorage.getItem('companyxyz-token');
			if (!token) {
				navigate('/login');
				return;
			}

			const response = await fetch('http://localhost:5000/api/jobs', {
				headers: {
					'Authorization': `Bearer ${token}`,
					'Content-Type': 'application/json'
				}
			});

			if (response.ok) {
				const jobs = await response.json();
				setJobOpenings(jobs);
			} else {
				setError('Failed to load jobs');
			}
		} catch (error) {
			console.error('Error loading jobs:', error);
			setError('Failed to load jobs');
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		const isLoggedIn = localStorage.getItem("companyxyz-token") !== null;
		if (!isLoggedIn) {
			navigate("/login");
			return;
		}
		loadJobs();
		loadApplications();
	}, [navigate]);

	const loadApplications = async () => {
		try {
			const token = localStorage.getItem('companyxyz-token');
			if (!token) return;

			const response = await fetch('http://localhost:5000/api/applications', {
				headers: {
					'Authorization': `Bearer ${token}`,
					'Content-Type': 'application/json'
				}
			});

			if (response.ok) {
				const apps = await response.json();
				setApplications(apps);
			}
		} catch (error) {
			console.error('Error loading applications:', error);
		}
	};

	const applyForJob = async (jobId) => {
		try {
			const token = localStorage.getItem('companyxyz-token');
			const user = JSON.parse(localStorage.getItem('companyxyz-user') || 'null');
			if (!token) {
				navigate('/login');
				return;
			}

			// Prevent recruiters from applying
			const role = (user?.user_type || user?.userType || 'candidate').toLowerCase();
			if (role === 'recruiter') {
				showToast('Recruiters cannot apply to jobs.', 'error');
				return;
			}

			const response = await fetch(`http://localhost:5000/api/jobs/${jobId}/apply`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${token}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					cover_letter: `I am interested in applying for this position and believe my skills align well with the requirements.`
				})
			});

			if (response.ok) {
				showToast('Application submitted successfully!', 'success');
				loadApplications(); // Reload applications
			} else {
				const errorData = await response.json();
				showToast(errorData.error || 'Failed to submit application', 'error');
			}
		} catch (error) {
			console.error('Error applying for job:', error);
			showToast('Failed to submit application', 'error');
		}
	};

	const hasApplied = (jobId) => {
		return applications.some(app => app.job_id === jobId.toString());
	};

	const getApplicationStatus = (jobId) => {
		const application = applications.find(app => app.job_id === jobId.toString());
		return application ? application.status : null;
	};

	const canWithdrawApplication = (jobId) => {
		const status = getApplicationStatus(jobId);
		// Allow withdrawal only if status is pending or applied
		return status && ['pending', 'applied'].includes(status.toLowerCase());
	};

	const [pendingWithdrawal, setPendingWithdrawal] = useState(null);

	const withdrawApplication = async (jobId) => {
		try {
			const token = localStorage.getItem('companyxyz-token');
			if (!token) {
				navigate('/login');
				return;
			}

			// If this is the confirmation step
			if (pendingWithdrawal === jobId) {
				const response = await fetch(`http://localhost:5000/api/jobs/${jobId}/withdraw`, {
					method: 'DELETE',
					headers: {
						'Authorization': `Bearer ${token}`,
						'Content-Type': 'application/json'
					}
				});

				if (response.ok) {
					showToast('Application withdrawn successfully!', 'success');
					loadApplications(); // Reload applications
				} else {
					const errorData = await response.json();
					showToast(errorData.error || 'Failed to withdraw application', 'error');
				}
				setPendingWithdrawal(null);
			} else {
				// First click - show warning and set pending
				setPendingWithdrawal(jobId);
				showToast('Click "Withdraw Application" again to confirm. This action cannot be undone.', 'warning');
			}
		} catch (error) {
			console.error('Error withdrawing application:', error);
			showToast('Failed to withdraw application', 'error');
			setPendingWithdrawal(null);
		}
	};

	// Check authentication when component mounts

	// Helpers for robust filtering
	const parseMinYears = (expStr) => {
		if (!expStr) return null;
		const s = String(expStr).toLowerCase();
		// Match formats like '5+ years', '3 years', '0-1', '1-2 years'
		const range = s.match(/(\d+)\s*-\s*(\d+)/);
		if (range) {
			return parseInt(range[1], 10);
		}
		const single = s.match(/(\d+)\s*\+?/);
		if (single) {
			return parseInt(single[1], 10);
		}
		return null;
	};

	const filteredJobs = jobOpenings.filter((job) => {
		const q = searchQuery.trim().toLowerCase();
		const title = String(job.title || '').toLowerCase();
		const desc = String(job.description || '').toLowerCase();
		const dept = String(job.department || '').toLowerCase();
		const skills = Array.isArray(job.skills) ? job.skills : [];

		const matchesSearch =
			q === '' ||
			title.includes(q) ||
			desc.includes(q) ||
			dept.includes(q) ||
			skills.some((skill) => String(skill).toLowerCase().includes(q));

		const typeSel = typeFilter.trim().toLowerCase();
		const matchesType =
			typeSel === '' || String(job.type || '').toLowerCase() === typeSel;

		const locSel = locationFilter.trim().toLowerCase();
		const matchesLocation =
			locSel === '' || String(job.location || '').toLowerCase().includes(locSel);

		const expSel = experienceFilter.trim();
		const minYears = parseMinYears(job.experience);
		let matchesExperience = true;
		if (expSel === '0-1') {
			matchesExperience = minYears === null || minYears <= 1;
		} else if (expSel === '2+') {
			matchesExperience = minYears !== null ? minYears >= 2 : true;
		} else if (expSel === '5+') {
			matchesExperience = minYears !== null ? minYears >= 5 : true;
		}

		return matchesSearch && matchesType && matchesLocation && matchesExperience;
	});

	return (
		<div className={styles.dashboardContainer}>
			<div className={styles.content}>
				<div className={styles.welcomeSection}>
					<h2>Find Your Dream Job at Top Companies</h2>
					<p>
						Discover exciting career opportunities and be part of
						innovative teams transforming the industry.
					</p>
				</div>

				<div className={styles.jobFilters}>
					<div className={styles.searchBar}>
						<input
							type="text"
							placeholder="Search for positions, skills, or departments"
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
						/>
						<button className={styles.searchButton}>
							<i className="fa fa-search"></i>
						</button>
					</div>

					<div className={styles.filterOptions}>
						<select
							value={typeFilter}
							onChange={(e) => setTypeFilter(e.target.value)}
							className={styles.filterSelect}
						>
							<option value="">All Job Types</option>
							<option value="Full-time">Full-time</option>
							<option value="Part-time">Part-time</option>
							<option value="Contract">Contract</option>
							<option value="Internship">Internship</option>
						</select>

						<select
							value={locationFilter}
							onChange={(e) => setLocationFilter(e.target.value)}
							className={styles.filterSelect}
						>
							<option value="">All Locations</option>
							<option value="Remote">Remote</option>
							<option value="Hybrid">Hybrid</option>
							<option value="San Francisco">San Francisco</option>
							<option value="New York">New York</option>
							<option value="Boston">Boston</option>
							<option value="Seattle">Seattle</option>
						</select>

						<select
							value={experienceFilter}
							onChange={(e) =>
								setExperienceFilter(e.target.value)
							}
							className={styles.filterSelect}
						>
							<option value="">All Experience Levels</option>
							<option value="0-1">Entry Level (0-1 year)</option>
							<option value="2+">Mid Level (2+ years)</option>
							<option value="5+">Senior Level (5+ years)</option>
						</select>
					</div>
				</div>

				<div className={styles.jobListings}>
					<h3>Current Openings ({filteredJobs.length})</h3>

					{loading ? (
						<div className={styles.loading}>
							<p>Loading jobs...</p>
						</div>
					) : error ? (
						<div className={styles.error}>
							<p>{error}</p>
						</div>
					) : filteredJobs.length === 0 ? (
						<div className={styles.noJobsFound}>
							<p>
								No positions match your current filters. Try
								adjusting your search criteria.
							</p>
						</div>
					) : (
						filteredJobs.map((job) => (
							<div key={job._id} className={styles.jobCard}>
								<div className={styles.jobMain}>
									<div className={styles.jobTitleSection}>
										<h4 className={styles.jobTitle}>
											{job.title}
										</h4>
										<div className={styles.companyInfo}>
											<span className={styles.companyName}>
												<i className="fa fa-building"></i>{" "}
												{job.company || 'TechCorp Solutions'}
											</span>
											<span
												className={styles.jobLocation}
											>
												<i className="fa fa-map-marker"></i>{" "}
												{job.location}
											</span>
										</div>
									</div>

									<div className={styles.jobAttributes}>
										<span className={styles.jobType}>
											{job.type}
										</span>
										<span className={styles.jobExperience}>
											<i className="fa fa-briefcase"></i>{" "}
											{job.experience}
										</span>
										<span className={styles.jobSalary}>
											<i className="fa fa-money"></i>{" "}
											{job.salary}
										</span>
										<span className={styles.jobDate}>
											<i className="fa fa-calendar"></i>{" "}
											Posted:{" "}
											{job.created_at ? new Date(job.created_at).toLocaleDateString() : ''}
										</span>
									</div>

									<div className={styles.jobDescription}>
										<p>{job.description}</p>
									</div>

									<div className={styles.jobSkills}>
										{job.skills && job.skills.map((skill, index) => (
											<span
												key={index}
												className={styles.skillTag}
											>
												{skill}
											</span>
										))}
									</div>
								</div>

								<div className={styles.jobActions}>
									<Link
										to={`/job/${job._id}`}
										className={styles.viewButton}
									>
										View Details
									</Link>
									{hasApplied(job._id) ? (
										canWithdrawApplication(job._id) ? (
											<button
												onClick={() => withdrawApplication(job._id)}
												className={`${styles.applyButton} ${styles.withdrawButton} ${pendingWithdrawal === job._id ? styles.confirmWithdraw : ''}`}
											>
												{pendingWithdrawal === job._id ? 'Confirm Withdrawal' : 'Withdraw Application'}
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
											onClick={() => applyForJob(job._id)}
											className={styles.applyButton}
										>
											Apply Now
										</button>
									)}
								</div>
							</div>
						))
					)}
				</div>
			</div>
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

export default Dashboard;

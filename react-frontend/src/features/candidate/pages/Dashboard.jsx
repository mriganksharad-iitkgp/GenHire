import React, { useState, useEffect, useMemo, useDeferredValue, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import Toast from "shared/components/ui/Toast";
import SkeletonCard from "shared/components/ui/SkeletonCard";
import Pagination from "shared/components/ui/Pagination";
import CVSelectionModal from "features/candidate/components/CVSelectionModal";
import { useCandidateData } from "features/candidate/context/CandidateDataContext";
import { INDIA_LOCATION_OPTIONS, canonicalizeJobRole } from "shared/constants/jobTaxonomy";
import styles from "./Dashboard.module.css";
import { getToken, getUser, isLoggedIn } from "shared/utils/session";
import { authedFetch } from "shared/api/client";

const Dashboard = () => {
	const navigate = useNavigate();
	const { loadJobsCached, loadApplicationsCached, invalidateApplications } = useCandidateData();
	const [searchQuery, setSearchQuery] = useState("");
	const deferredSearchQuery = useDeferredValue(searchQuery);
	const normalizedSearchQuery = String(deferredSearchQuery ?? "").trim();
	const [typeFilter, setTypeFilter] = useState("");
	const [locationFilter, setLocationFilter] = useState("");
	const [experienceFilter, setExperienceFilter] = useState("");
	const [jobRoleFilter, setJobRoleFilter] = useState("");
	const [companyFilter, setCompanyFilter] = useState("");
	const [skillsFilter, setSkillsFilter] = useState("");
	const [jobOpenings, setJobOpenings] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);
	const [applications, setApplications] = useState([]);
	const [applyingJobIds, setApplyingJobIds] = useState(new Set()); // Track all jobs currently being applied to
	const [withdrawingJobId, setWithdrawingJobId] = useState(null); // Track which job is being withdrawn
	const [pendingWithdrawal, setPendingWithdrawal] = useState(null);
	const [showCVModal, setShowCVModal] = useState(false);
	const [selectedJobForApplication, setSelectedJobForApplication] = useState(null);
	
	// Pagination state
	const [currentPage, setCurrentPage] = useState(1);
	const itemsPerPage = 10;
	
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

	// Reset page when filters change
	useEffect(() => {
		setCurrentPage(1);
	}, [searchQuery, typeFilter, locationFilter, experienceFilter, jobRoleFilter, companyFilter, skillsFilter]);

	// Poll for application updates when there are pending/processing applications
	useEffect(() => {
		const hasPending = applications.some(
			app => app.processing_status === 'pending' || app.processing_status === 'processing'
		);
		if (!hasPending) return;

		const interval = setInterval(() => {
			// Only poll if the user is actively viewing the page
			if (document.visibilityState === 'visible') {
				loadApplications(true);
			}
		}, 5000);

		return () => clearInterval(interval);
	}, [applications]);

	const loadJobs = async (force = false) => {
		try {
			const token = getToken();
			if (!token) {
				navigate('/login');
				return;
			}

			// Use cached data if available
			const jobs = await loadJobsCached(force, async () => {
				const response = await authedFetch(`${process.env.REACT_APP_API_URL}/api/jobs`, {
					headers: {
						'Authorization': `Bearer ${token}`,
						'Content-Type': 'application/json'
					}
				});

				if (response.ok) {
					return await response.json();
				} else {
					throw new Error('Failed to load jobs');
				}
			});

			setJobOpenings(jobs);
			setError(null);
		} catch (error) {
			console.error('Error loading jobs:', error);
			setError('Failed to load jobs');
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		const loggedIn = isLoggedIn();
		if (!loggedIn) {
			navigate("/login");
			return;
		}
		loadJobs();
		loadApplications();
	}, [navigate]);

	const loadApplications = async (force = false) => {
		try {
			const token = getToken();
			if (!token) return;

			// Use cached data if available
			const apps = await loadApplicationsCached(force, async () => {
				const response = await authedFetch(`${process.env.REACT_APP_API_URL}/api/applications`, {
					headers: {
						'Authorization': `Bearer ${token}`,
						'Content-Type': 'application/json'
					}
				});

				if (response.ok) {
					return await response.json();
				} else {
					throw new Error('Failed to load applications');
				}
			});

			setApplications(apps);
		} catch (error) {
			console.error('Error loading applications:', error);
		}
	};

	const applyForJob = (jobId) => {
		const token = getToken();
		const user = getUser();
		
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

		// Find the job to get its title
		const job = jobOpenings.find(j => j._id === jobId);
		setSelectedJobForApplication({ id: jobId, title: job?.title || 'this position' });
		setShowCVModal(true);
	};

	const handleCVSelectionSubmit = async (cvSelection) => {
		const jobId = selectedJobForApplication?.id;
		if (!jobId) return;

		setApplyingJobIds(prev => new Set([...prev, jobId]));

		// Close modal immediately for better UX
		setShowCVModal(false);
		setSelectedJobForApplication(null);
		
		try {
			const token = getToken();
			const response = await authedFetch(`${process.env.REACT_APP_API_URL}/api/jobs/${jobId}/apply`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${token}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					cv_id: cvSelection.cv_id,
					use_manual_cv: cvSelection.use_manual_cv,
					cover_letter: `I am interested in applying for this position and believe my skills align well with the requirements.`
				})
			});

			const data = await parseApplyResponse(response);

			if (response.ok) {
				// Application successful - backend is processing CV score
				showToast('Application submitted! CV scoring is being processed...', 'success');
				// Optimistically add to local applications so button changes instantly
				setApplications(prev => [...prev, {
					job_id: jobId.toString(),
					status: 'pending',
					processing_status: 'pending',
					applied_at: new Date().toISOString()
				}]);
				// Invalidate applications cache so next load gets fresh data
				invalidateApplications();
			} else {
				showToast(data.error || 'Failed to submit application', 'error');
				// If already applied, force-reload applications so the button state updates
				if (data.error && data.error.toLowerCase().includes('already applied')) {
					invalidateApplications();
					await loadApplications(true);
				}
			}
		} catch (error) {
			console.error('Error applying for job:', error);
			showToast('Failed to submit application', 'error');
		} finally {
			setApplyingJobIds(prev => {
				const next = new Set(prev);
				next.delete(jobId);
				return next;
			});
		}
	};

	const hasApplied = useCallback((jobId) => {
		// Treat invite-created skeletons (no CV uploaded yet, awaiting candidate
		// submission) as "not yet applied" so the Apply button stays available
		// for invitees who haven't completed the apply step.
		return applications.some(app => {
			if (String(app.job_id) !== String(jobId)) return false;
			const isSkeleton =
				app.processing_status === 'awaiting_candidate';
			return !isSkeleton;
		});
	}, [applications]);

	const getApplicationStatus = (jobId) => {
		const application = applications.find(app => app.job_id === jobId.toString());
		return application ? application.status : null;
	};

	const canWithdrawApplication = (jobId) => {
		const status = getApplicationStatus(jobId);
		// Allow withdrawal only if status is pending or applied
		return status && ['pending', 'applied'].includes(status.toLowerCase());
	};

	// Pull the cached candidate user once per render — used to scope apply-rights
	// for invite-only (burner) accounts.
	const cachedUser = (() => {
		try {
			return getUser();
		} catch (_) {
			return null;
		}
	})();
	const isInviteOnly = !!(cachedUser && (cachedUser.is_invite_only || cachedUser.isInviteOnly));
	const invitedJobIds = (cachedUser?.invited_job_ids || cachedUser?.invitedJobIds || []).map(String);
	const isAllowedToApply = (jobId) =>
		!isInviteOnly || invitedJobIds.includes(String(jobId));

	// Function to get the correct button state and text
	const getJobButtonState = (jobId) => {
		const hasAppliedToJob = hasApplied(jobId);
		const canWithdraw = canWithdrawApplication(jobId);
		const isPendingWithdrawal = pendingWithdrawal === jobId;
		const isApplying = applyingJobIds.has(jobId);
		const allowedToApply = isAllowedToApply(jobId);

		// Invite-only candidate viewing a job they weren't invited to.
		if (!hasAppliedToJob && !allowedToApply) {
			return {
				type: 'blocked',
				text: 'Invite required',
				className: `${styles.applyButton} ${styles.appliedButton}`,
				onClick: () => showToast('You can only apply to jobs you were invited to.', 'warning'),
				disabled: true,
			};
		}

		// State 1: Apply Now (not applied yet)
		if (!hasAppliedToJob) {
			return {
				type: 'apply',
				text: isApplying ? (
					<>
						<i className="fa fa-spinner fa-spin"></i> Applying...
					</>
				) : 'Apply Now',
				className: styles.applyButton,
				onClick: () => applyForJob(jobId),
				disabled: isApplying
			};
		}
		
		// State 2: Withdraw Application (applied and can withdraw, not pending)
		if (hasAppliedToJob && canWithdraw && !isPendingWithdrawal) {
			const isWithdrawing = withdrawingJobId === jobId;
			return {
				type: 'withdraw',
				text: isWithdrawing ? (
					<>
						<i className="fa fa-spinner fa-spin"></i> Withdrawing...
					</>
				) : 'Withdraw Application',
				className: `${styles.applyButton} ${styles.withdrawButton}`,
				onClick: () => withdrawApplication(jobId),
				disabled: isWithdrawing
			};
		}
		
		// State 3: Confirm Withdrawal (applied, can withdraw, and pending confirmation)
		if (hasAppliedToJob && canWithdraw && isPendingWithdrawal) {
			const isWithdrawing = withdrawingJobId === jobId;
			return {
				type: 'confirm_withdraw',
				text: isWithdrawing ? (
					<>
						<i className="fa fa-spinner fa-spin"></i> Withdrawing...
					</>
				) : 'Confirm Withdrawal',
				className: `${styles.applyButton} ${styles.withdrawButton} ${styles.confirmWithdraw}`,
				onClick: () => withdrawApplication(jobId),
				disabled: isWithdrawing
			};
		}
		
		// State 4: Application Submitted (applied but cannot withdraw anymore)
		if (hasAppliedToJob && !canWithdraw) {
			return {
				type: 'submitted',
				text: 'Application Submitted',
				className: `${styles.applyButton} ${styles.appliedButton}`,
				onClick: () => {},
				disabled: true
			};
		}
		
		// Fallback to Apply Now
		return {
			type: 'apply',
			text: isApplying ? (
				<>
					<i className="fa fa-spinner fa-spin"></i> Applying...
				</>
			) : 'Apply Now',
			className: styles.applyButton,
			onClick: () => applyForJob(jobId),
			disabled: isApplying
		};
	};

	const withdrawApplication = async (jobId) => {
		try {
			const token = getToken();
			if (!token) {
				navigate('/login');
				return;
			}

			// If this is NOT the confirmation step (first click)
			if (pendingWithdrawal !== jobId) {
				// First click - show warning and set pending
				setPendingWithdrawal(jobId);
				showToast('Click "Confirm Withdrawal" to proceed. This action cannot be undone.', 'warning');
				
				// Auto-clear pending state after 10 seconds
				setTimeout(() => {
					setPendingWithdrawal(prev => prev === jobId ? null : prev);
				}, 10000);
				return;
			}

			// This is the confirmation step (second click)
			setWithdrawingJobId(jobId);
			
			const response = await authedFetch(`${process.env.REACT_APP_API_URL}/api/jobs/${jobId}/withdraw`, {
				method: 'DELETE',
				headers: {
					'Authorization': `Bearer ${token}`,
					'Content-Type': 'application/json'
				}
			});

			if (response.ok) {
				showToast('Application withdrawn successfully!', 'success');
				// Invalidate cache and reload
				invalidateApplications();
				await loadApplications(true); // Force reload
			} else {
				const errorData = await response.json();
				showToast(errorData.error || 'Failed to withdraw application', 'error');
			}
			setPendingWithdrawal(null);
			setWithdrawingJobId(null);
		} catch (error) {
			console.error('Error withdrawing application:', error);
			showToast('Failed to withdraw application', 'error');
			setPendingWithdrawal(null);
			setWithdrawingJobId(null);
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

	// Hardcoded standard job roles for the filter dropdown (prevents messy duplicates from recruiter-typed titles)
	const STANDARD_JOB_ROLES = [
		// Engineering & Tech
		"Software Engineer", "Frontend Developer", "Backend Developer", "Full Stack Developer",
		"Mobile Developer", "DevOps Engineer", "Cloud Engineer", "Site Reliability Engineer",
		"Data Engineer", "Data Scientist", "Data Analyst", "Machine Learning Engineer",
		"AI Engineer", "QA Engineer", "Security Engineer", "Embedded Engineer",
		// Product & Design
		"Product Manager", "Product Designer", "UX Designer", "UI Designer", "UX Researcher",
		// Business & Management
		"Business Analyst", "Project Manager", "Scrum Master", "Engineering Manager",
		"Technical Lead", "CTO", "VP of Engineering",
		// Marketing & Growth
		"Marketing Manager", "Content Writer", "SEO Specialist", "Growth Manager",
		"Digital Marketing Manager", "Social Media Manager",
		// Sales & Support
		"Sales Executive", "Account Manager", "Customer Success Manager", "Support Engineer",
		// Operations & HR
		"Operations Manager", "HR Manager", "Recruiter", "People Operations",
		// Finance & Legal
		"Financial Analyst", "Accountant", "Legal Counsel",
	];
	
	// Get unique companies for the filter dropdown
	const uniqueCompanies = [...new Set(jobOpenings.map(job => job.company || 'TechCorp Solutions').filter(Boolean))].sort();

	// Include custom recruiter-entered locations in addition to standard options
	const uniqueLocations = [...new Set(jobOpenings.map(job => job.location).filter(Boolean))].sort();
	const locationOptions = [...new Set([...INDIA_LOCATION_OPTIONS, ...uniqueLocations])];
	
	// Get unique skills for the filter dropdown
	const uniqueSkills = [...new Set(jobOpenings.flatMap(job => Array.isArray(job.skills) ? job.skills : []).filter(Boolean))].sort();

	// --- Search Suggestions Logic ---
	const [showSuggestions, setShowSuggestions] = useState(false);
	const [searchSuggestions, setSearchSuggestions] = useState({ roles: [], companies: [], locations: [], skills: [] });
	const searchInputRef = React.useRef(null);
	const suggestionsRef = React.useRef(null);

	// Compute categorized suggestions from loaded jobs data
	const computeSuggestions = React.useCallback((query) => {
		if (!query || query.trim().length < 1) {
			setSearchSuggestions({ roles: [], companies: [], locations: [], skills: [] });
			return;
		}

		const q = query.trim().toLowerCase();
		const MAX_PER_CATEGORY = 3;

		// Collect all unique values
		const allRoles = [...new Set(jobOpenings.map(j => j.title).filter(Boolean))];
		const allCompanies = [...new Set(jobOpenings.map(j => j.company).filter(Boolean))];
		const allLocations = [...new Set(jobOpenings.map(j => j.location).filter(Boolean))];
		const allSkills = [...new Set(jobOpenings.flatMap(j => Array.isArray(j.skills) ? j.skills : []).filter(Boolean))];

		// Match against query (prefix match first, then contains)
		const match = (items) => {
			const prefixMatches = items.filter(item => item.toLowerCase().startsWith(q));
			const containsMatches = items.filter(item => !item.toLowerCase().startsWith(q) && item.toLowerCase().includes(q));
			return [...prefixMatches, ...containsMatches].slice(0, MAX_PER_CATEGORY);
		};

		setSearchSuggestions({
			roles: match(allRoles),
			companies: match(allCompanies),
			locations: match(allLocations),
			skills: match(allSkills),
		});
	}, [jobOpenings]);

	// Recompute suggestions when searchQuery changes
	useEffect(() => {
		computeSuggestions(normalizedSearchQuery);
	}, [normalizedSearchQuery, computeSuggestions]);

	// Close suggestions on outside click
	useEffect(() => {
		const handleClickOutside = (e) => {
			if (
				suggestionsRef.current && !suggestionsRef.current.contains(e.target) &&
				searchInputRef.current && !searchInputRef.current.contains(e.target)
			) {
				setShowSuggestions(false);
			}
		};
		document.addEventListener('mousedown', handleClickOutside);
		return () => document.removeEventListener('mousedown', handleClickOutside);
	}, []);

	const hasSuggestions = searchSuggestions.roles.length > 0 || searchSuggestions.companies.length > 0 || searchSuggestions.locations.length > 0 || searchSuggestions.skills.length > 0;

	const handleSuggestionClick = (value) => {
		setSearchQuery(value);
		setShowSuggestions(false);
	};

	// Highlight matching text in suggestions
	const highlightMatch = (text, query) => {
		if (!query) return text;
		const idx = text.toLowerCase().indexOf(query.toLowerCase());
		if (idx === -1) return text;
		return (
			<>
				{text.slice(0, idx)}
				<span className={styles.suggestionHighlight}>{text.slice(idx, idx + query.length)}</span>
				{text.slice(idx + query.length)}
			</>
		);
	};
	// --- End Search Suggestions Logic ---

	const getRelevanceScore = useCallback((job, query) => {
		if (!query) return 0;
		const q = query.toLowerCase();
		const title = String(job.title || '').toLowerCase();
		if (title.includes(q)) return 4;

		const skills = Array.isArray(job.skills) ? job.skills : [];
		if (skills.some((skill) => String(skill).toLowerCase().includes(q))) return 3;

		const desc = String(job.description || '').toLowerCase();
		if (desc.includes(q)) return 2;

		const dept = String(job.department || '').toLowerCase();
		const companyStr = String(job.company || 'TechCorp Solutions').toLowerCase();
		const locationStr = String(job.location || '').toLowerCase();
		
		if (dept.includes(q) || companyStr.includes(q) || locationStr.includes(q)) return 1;
		
		return 0;
	}, []);

	const filteredJobs = useMemo(() => {
		return jobOpenings.filter((job) => {
			// Invite-only (burner) candidates only see jobs they were invited to.
			// Direct URLs to other jobs still resolve, but they won't surface here.
			if (isInviteOnly && !invitedJobIds.includes(String(job._id))) {
				return false;
			}

			const q = normalizedSearchQuery.toLowerCase();
			const title = String(job.title || '').toLowerCase();
			const desc = String(job.description || '').toLowerCase();
			const dept = String(job.department || '').toLowerCase();
			const companyStr = String(job.company || 'TechCorp Solutions').toLowerCase();
			const locationStr = String(job.location || '').toLowerCase();
			const skills = Array.isArray(job.skills) ? job.skills : [];

			const matchesSearch =
				q === '' ||
				title.includes(q) ||
				desc.includes(q) ||
				dept.includes(q) ||
				companyStr.includes(q) ||
				locationStr.includes(q) ||
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

			const roleSel = jobRoleFilter.trim();
			const canonicalJobRole = canonicalizeJobRole(job.title || '');
			const matchesJobRole = roleSel === '' || canonicalJobRole === roleSel;

			const companySel = companyFilter.trim();
			const matchesCompany = companySel === '' || String(job.company || 'TechCorp Solutions') === companySel;

			const skillSel = skillsFilter.trim();
			const matchesSkill = skillSel === '' || (Array.isArray(job.skills) && job.skills.includes(skillSel));

			return matchesSearch && matchesType && matchesLocation && matchesExperience && matchesJobRole && matchesCompany && matchesSkill;
		}).sort((a, b) => {
			// Sort 1: Application status (unapplied jobs first)
			const aApplied = hasApplied(a._id);
			const bApplied = hasApplied(b._id);
			if (aApplied && !bApplied) return 1;
			if (!aApplied && bApplied) return -1;
			
			// Sort 2: Relevance Score (highest first)
			if (normalizedSearchQuery) {
				const scoreA = getRelevanceScore(a, normalizedSearchQuery);
				const scoreB = getRelevanceScore(b, normalizedSearchQuery);
				if (scoreA !== scoreB) {
					return scoreB - scoreA;
				}
			}

			// Sort 3: Creation date (newest first)
			const aDate = new Date(a.created_at || 0);
			const bDate = new Date(b.created_at || 0);
			return bDate - aDate;
		});
	}, [
		jobOpenings, 
		normalizedSearchQuery, 
		typeFilter, 
		locationFilter, 
		experienceFilter, 
		jobRoleFilter, 
		companyFilter, 
		skillsFilter, 
		isInviteOnly, 
		invitedJobIds, 
		hasApplied,
		getRelevanceScore
	]);

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
					<div className={styles.searchBarWrapper}>
					<div className={styles.searchBar}>
						<input
							ref={searchInputRef}
							type="text"
							placeholder="Search for positions, skills, companies, or locations..."
							value={String(searchQuery ?? "")}
							onChange={(e) => setSearchQuery(String(e.target.value ?? ""))}
							onFocus={() => setShowSuggestions(true)}
							onKeyDown={(e) => {
								if (e.key === 'Escape') setShowSuggestions(false);
								if (e.key === 'Enter') {
									setShowSuggestions(false);
								}
							}}
							autoComplete="off"
						/>
						<button
							type="button"
							className={styles.searchButton}
							onClick={() => {
								setShowSuggestions(false);
							}}
							aria-label="Search jobs"
						>
							<i className="fa fa-search"></i>
						</button>
					</div>

					{/* Suggestions Dropdown */}
					{showSuggestions && hasSuggestions && (
						<div className={styles.suggestionsDropdown} ref={suggestionsRef}>
							{searchSuggestions.roles.length > 0 && (
								<div className={styles.suggestionCategory}>
									<div className={styles.suggestionCategoryHeader}>
										<span>Roles</span>
									</div>
									{searchSuggestions.roles.map((role, i) => (
										<div
											key={`role-${i}`}
											className={styles.suggestionItem}
											onMouseDown={() => handleSuggestionClick(role)}
										>
											<span className={styles.suggestionItemIcon}>
												<svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fillRule="evenodd" d="M6 3.75A2.75 2.75 0 018.75 1h2.5A2.75 2.75 0 0114 3.75v.443c.572.055 1.14.122 1.706.2C17.053 4.582 18 5.75 18 7.07v3.469c0 1.126-.694 2.191-1.83 2.54-1.952.599-4.024.921-6.17.921s-4.219-.322-6.17-.921C2.694 12.73 2 11.665 2 10.539V7.07c0-1.321.947-2.489 2.294-2.676A41.047 41.047 0 016 4.193V3.75z" clipRule="evenodd" /></svg>
											</span>
											<span className={styles.suggestionItemText}>{highlightMatch(role, searchQuery)}</span>
										</div>
									))}
								</div>
							)}

							{searchSuggestions.companies.length > 0 && (
								<div className={styles.suggestionCategory}>
									<div className={styles.suggestionCategoryHeader}>
										<span>Companies</span>
									</div>
									{searchSuggestions.companies.map((company, i) => (
										<div
											key={`company-${i}`}
											className={styles.suggestionItem}
											onMouseDown={() => handleSuggestionClick(company)}
										>
											<span className={styles.suggestionItemIcon}>
												<svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fillRule="evenodd" d="M4 16.5v-13h-.25a.75.75 0 010-1.5h12.5a.75.75 0 010 1.5H16v13h.25a.75.75 0 010 1.5h-3.5a.75.75 0 01-.75-.75v-2.5a.75.75 0 00-.75-.75h-2.5a.75.75 0 00-.75.75v2.5a.75.75 0 01-.75.75h-3.5a.75.75 0 010-1.5H4z" clipRule="evenodd" /></svg>
											</span>
											<span className={styles.suggestionItemText}>{highlightMatch(company, searchQuery)}</span>
										</div>
									))}
								</div>
							)}

							{searchSuggestions.locations.length > 0 && (
								<div className={styles.suggestionCategory}>
									<div className={styles.suggestionCategoryHeader}>
										<span>Locations</span>
									</div>
									{searchSuggestions.locations.map((loc, i) => (
										<div
											key={`loc-${i}`}
											className={styles.suggestionItem}
											onMouseDown={() => handleSuggestionClick(loc)}
										>
											<span className={styles.suggestionItemIcon}>
												<svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fillRule="evenodd" d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 00.281-.14 15.862 15.862 0 002.53-1.718C14.977 15.578 17 13.046 17 10a7 7 0 10-14 0c0 3.046 2.023 5.578 3.856 7.065a15.862 15.862 0 002.53 1.718 9.94 9.94 0 00.3.148l.018.008.006.003zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" /></svg>
											</span>
											<span className={styles.suggestionItemText}>{highlightMatch(loc, searchQuery)}</span>
										</div>
									))}
								</div>
							)}

							{searchSuggestions.skills.length > 0 && (
								<div className={styles.suggestionCategory}>
									<div className={styles.suggestionCategoryHeader}>
										<span>Skills</span>
									</div>
									{searchSuggestions.skills.map((skill, i) => (
										<div
											key={`skill-${i}`}
											className={styles.suggestionItem}
											onMouseDown={() => handleSuggestionClick(skill)}
										>
											<span className={styles.suggestionItemIcon}>
												<svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" /></svg>
											</span>
											<span className={styles.suggestionItemText}>{highlightMatch(skill, searchQuery)}</span>
										</div>
									))}
								</div>
							)}
						</div>
					)}
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
							{locationOptions.map((locationOption) => (
								<option key={locationOption} value={locationOption}>
									{locationOption}
								</option>
							))}
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

						<select
						value={jobRoleFilter}
						onChange={(e) => setJobRoleFilter(e.target.value)}
						className={styles.filterSelect}
					>
						<option value="">All Job Roles</option>
						{STANDARD_JOB_ROLES.map((role, index) => (
							<option key={index} value={role}>
								{role}
							</option>
						))}
					</select>

						<select
							value={companyFilter}
							onChange={(e) => setCompanyFilter(e.target.value)}
							className={styles.filterSelect}
						>
							<option value="">All Companies</option>
							{uniqueCompanies.map((company, index) => (
								<option key={index} value={company}>
									{company}
								</option>
							))}
						</select>

						<select
							value={skillsFilter}
							onChange={(e) => setSkillsFilter(e.target.value)}
							className={styles.filterSelect}
						>
							<option value="">All Skills</option>
							{uniqueSkills.map((skill, index) => (
								<option key={index} value={skill}>
									{skill}
								</option>
							))}
						</select>
					</div>
				</div>

				<div className={styles.jobListings}>
					{searchQuery && searchQuery.trim() !== '' && (
						<p className={styles.searchHint}>
							Showing search for "{searchQuery}"
						</p>
					)}
					<h3>Current Openings ({filteredJobs.length})</h3>

					{loading ? (
						<div>
							{Array.from({ length: 5 }).map((_, i) => (
								<SkeletonCard key={i} variant="job" />
							))}
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
						<>
							{(() => {
								const unappliedJobs = filteredJobs.filter(job => !hasApplied(job._id));
								const appliedJobs = filteredJobs.filter(job => hasApplied(job._id));
								
								// Pagination logic
								const startIndex = (currentPage - 1) * itemsPerPage;
								const endIndex = startIndex + itemsPerPage;
								const paginatedUnappliedJobs = unappliedJobs.slice(startIndex, endIndex);
								const paginatedAppliedJobs = appliedJobs.slice(Math.max(0, startIndex - unappliedJobs.length), Math.max(0, endIndex - unappliedJobs.length));
								const totalPages = Math.ceil(filteredJobs.length / itemsPerPage);
								
								return (
									<>
										{/* Available Jobs First */}
										{paginatedUnappliedJobs.length > 0 && (
											<div className={styles.jobSection}>
												<h4 className={styles.jobSectionHeader + ' ' + styles.jobSectionHeaderAvailable}>
													<i className="fa fa-circle"></i>
													Available Jobs ({unappliedJobs.length})
												</h4>
												{paginatedUnappliedJobs.map((job) => (
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
																to={`/jobs/${job._id}`}
																className={styles.viewButton}
															>
																View Details
															</Link>
															{(() => {
																const buttonState = getJobButtonState(job._id);
																return (
																	<button
																		onClick={buttonState.onClick}
																		className={buttonState.className}
																		disabled={buttonState.disabled}
																	>
																		{buttonState.text}
																	</button>
																);
															})()}
														</div>
													</div>
												))}
											</div>
										)}
										
										{/* Applied Jobs Section */}
										{paginatedAppliedJobs.length > 0 && (
											<div className={styles.jobSection} style={{marginTop: '2rem'}}>
												<h4 className={styles.jobSectionHeader + ' ' + styles.jobSectionHeaderApplied}>
													<i className="fa fa-check-circle"></i>
													Your Applications ({appliedJobs.length})
												</h4>
												{paginatedAppliedJobs.map((job) => (
													<div key={job._id} className={`${styles.jobCard} ${styles.appliedJobCard}`}>
														<div className={styles.jobMain}>
															<div className={styles.jobTitleSection}>
																<h4 className={styles.jobTitle}>
																	{job.title}
																	<span className={styles.appliedBadge}>
																		<i className="fa fa-check"></i> Applied
																	</span>
																</h4>
																<div className={styles.companyInfo}>
																	<span className={styles.companyName}>
																		<i className="fa fa-building"></i> {job.company || 'TechCorp Solutions'}
																	</span>
																	<span className={styles.jobLocation}>
																		<i className="fa fa-map-marker"></i> {job.location}
																	</span>
																	<span className={styles.applicationStatusText}>
																		Status: {getApplicationStatus(job._id) || 'Pending'}
																	</span>
																</div>
															</div>

															<div className={styles.jobAttributes}>
																<span className={styles.jobType}>{job.type}</span>
																<span className={styles.jobExperience}>
																	<i className="fa fa-briefcase"></i> {job.experience}
																</span>
																<span className={styles.jobSalary}>
																	<i className="fa fa-money"></i> {job.salary}
																</span>
																<span className={styles.jobDate}>
																	<i className="fa fa-calendar"></i> Posted: {job.created_at ? new Date(job.created_at).toLocaleDateString() : ''}
																</span>
															</div>

															<div className={styles.jobDescription}>
																<p>{job.description}</p>
															</div>

															<div className={styles.jobSkills}>
																{job.skills && job.skills.map((skill, index) => (
																	<span key={index} className={styles.skillTag}>{skill}</span>
																))}
															</div>
														</div>

														<div className={styles.jobActions}>
															<Link to={`/jobs/${job._id}`} className={styles.viewButton}>
																View Details
															</Link>
															{(() => {
																const buttonState = getJobButtonState(job._id);
																return (
																	<button
																		onClick={buttonState.onClick}
																		className={buttonState.className}
																		disabled={buttonState.disabled}
																	>
																		{buttonState.text}
																	</button>
																);
															})()}
														</div>
													</div>
												))}
											</div>
										)}
										
										{/* Pagination */}
										<Pagination
											currentPage={currentPage}
											totalPages={totalPages}
											onPageChange={setCurrentPage}
											totalItems={filteredJobs.length}
											itemsPerPage={itemsPerPage}
										/>
									</>
								);
							})()}
						</>
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
			
			{/* CV Selection Modal */}
			<CVSelectionModal
				isOpen={showCVModal}
				onClose={() => {
					setShowCVModal(false);
					setSelectedJobForApplication(null);
				}}
				onSubmit={handleCVSelectionSubmit}
				jobTitle={selectedJobForApplication?.title}
				mode="apply"
			/>
		</div>
	);
};

export default Dashboard;

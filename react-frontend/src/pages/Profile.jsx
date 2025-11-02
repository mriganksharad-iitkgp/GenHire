import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import InterviewReportModal from "../components/InterviewReportModal";
import Toast from "../components/Toast";
import styles from "./Profile.module.css";
import SidebarProfile from "../components/candidate/SidebarProfile";
import BioForm from "../components/candidate/BioForm";
import ApplicationsList from "../components/candidate/ApplicationsList";
import useCandidateProfile from "../hooks/candidate/useCandidateProfile";
import useCandidateApplications from "../hooks/candidate/useCandidateApplications";
import { viewCV as apiViewCV } from "../services/api";

const Profile = () => {
	const navigate = useNavigate();
	const [activeTab, setActiveTab] = useState("bio"); // Add state for active tab
	const [cvFile, setCvFile] = useState(null);
	
	// Filter states for applications
	const [companyFilter, setCompanyFilter] = useState("");
	const [statusFilter, setStatusFilter] = useState("");
	
	// Interview report modal state
	const [isReportOpen, setIsReportOpen] = useState(false);
	const [reportData, setReportData] = useState(null);
	const [reportScores, setReportScores] = useState({ cv: null, interview: null });

	// Toast state
	const [toast, setToast] = useState(null);

	// Show toast function
	const showToast = useCallback((message, type = 'info') => {
		setToast({ message, type });
	}, []);

	// Check authentication when component mounts
	useEffect(() => {
		const isLoggedIn = localStorage.getItem("companyxyz-token") !== null;
		if (!isLoggedIn) {
			navigate("/login");
			return;
		}

		// Check for hash in URL to set active tab
		const hash = window.location.hash;
		if (hash === "#applications") {
			setActiveTab("applications");
		} else if (hash === "#bio") {
			setActiveTab("bio");
		}
		
		// Also check URL search params for tab navigation
		const urlParams = new URLSearchParams(window.location.search);
		const tabParam = urlParams.get('tab');
		if (tabParam === 'applications') {
			setActiveTab("applications");
		} else if (tabParam === 'bio') {
			setActiveTab("bio");
		}
		}, [navigate]);

	// Add hash change listener to handle navigation from navbar
	useEffect(() => {
		const handleHashChange = () => {
			const hash = window.location.hash;
			if (hash === "#applications") {
				setActiveTab("applications");
			} else if (hash === "#bio") {
				setActiveTab("bio");
			}
		};

		// Listen for hash changes
		window.addEventListener('hashchange', handleHashChange);
		
		// Also check on mount if hash exists
		handleHashChange();

		return () => {
			window.removeEventListener('hashchange', handleHashChange);
		};
	}, []);

	// Hooks for profile and applications
	const { bio, setBio, profilePhotoUrl, cvPath, cvDetails, loading: loadingProfile, uploadingCV, uploadingPhoto, save, uploadCvFile, uploadProfilePhoto, saveCvDetails } = useCandidateProfile(showToast);
	const { applications, loading: loadingApps, openReport, companies, load: reloadApplications } = useCandidateApplications(showToast);
	
	// Check for interview completion on mount and force immediate refresh
	useEffect(() => {
		const interviewCompleted = localStorage.getItem('interview-just-completed');
		if (interviewCompleted === 'true') {
			console.log('🎯 Interview completion detected on Profile mount - forcing immediate refresh...');
			localStorage.removeItem('interview-just-completed'); // Clear immediately
			
			// Force multiple refreshes with delays to ensure database sync
			reloadApplications(true);
			setTimeout(() => reloadApplications(true), 1000);
			setTimeout(() => reloadApplications(true), 2000);
			setTimeout(() => reloadApplications(true), 3000);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []); // Run only once on mount - reloadApplications is stable
	
	// Reload applications when page becomes visible (after returning from interview)
	useEffect(() => {
		const handleVisibilityChange = () => {
			if (document.visibilityState === 'visible') {
				// Check if interview was just completed
				const interviewCompleted = localStorage.getItem('interview-just-completed');
				if (interviewCompleted === 'true') {
					localStorage.removeItem('interview-just-completed'); // Clear the flag
					
					// Multiple refresh attempts with increasing delays to ensure update is caught
					reloadApplications(true);
					
					setTimeout(() => {
						reloadApplications(true);
					}, 1000);
					
					setTimeout(() => {
						reloadApplications(true);
					}, 2000);
					
					setTimeout(() => {
						reloadApplications(true);
					}, 3000);
				} else {
					// Force reload when page becomes visible again
					reloadApplications(true); // Force parameter bypasses throttle
				}
			}
		};
		
		// Also reload when hash changes to applications tab
		const handleHashChange = () => {
			if (window.location.hash === '#applications') {
				reloadApplications(true);
			}
		};
		
		document.addEventListener('visibilitychange', handleVisibilityChange);
		window.addEventListener('hashchange', handleHashChange);
		
		return () => {
			document.removeEventListener('visibilitychange', handleVisibilityChange);
			window.removeEventListener('hashchange', handleHashChange);
		};
	}, [reloadApplications]);

	// Handle tab change
	const handleTabChange = (tab) => {
		setActiveTab(tab);
		window.location.hash = `#${tab}`;
		
		// If switching to applications tab, check for interview completion and refresh
		if (tab === 'applications') {
			const interviewCompleted = localStorage.getItem('interview-just-completed');
			if (interviewCompleted === 'true') {
				localStorage.removeItem('interview-just-completed');
				reloadApplications(true);
			} else {
				// Always refresh when switching to applications tab for latest data
				reloadApplications(true);
			}
		}
	};

	// Handle CV upload
		const handleCVUpload = async (e) => {
		e.preventDefault();
			if (!cvFile) {
			showToast("Please select a CV file.", "error");
			return;
		}
			const ok = await uploadCvFile(cvFile);
			if (ok) setCvFile(null);
	};

	// Handle photo upload
		const handlePhotoUpload = async (file) => {
			if (!file) return;
			await uploadProfilePhoto(file);
		};

	// Handle CV viewing
		const handleViewCV = async () => {
			try {
				const blob = await apiViewCV();
				const url = window.URL.createObjectURL(blob);
				window.open(url, '_blank');
			} catch (e) {
				showToast("Error viewing CV", "error");
			}
		};

	// Handle profile data update
	const handleProfileUpdate = async (e) => {
		e.preventDefault();
		const ok = await save();
		if (!ok) return;
	};

	// Handle CV details save
	const handleSaveCvDetails = async (formData) => {
		try {
			const success = await saveCvDetails(formData);
			if (success) {
				showToast('CV details saved successfully!', 'success');
			}
		} catch (error) {
			console.error('Error saving CV details:', error);
			showToast('Failed to save CV details. Please try again.', 'error');
		}
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

	// Sort applications by applied date (newest first)
	// Filter and sort applications
	const filteredApplications = applications.filter((app) => {
		const matchesCompany = companyFilter === "" || app.company.toLowerCase().includes(companyFilter.toLowerCase());
		const matchesStatus = statusFilter === "" || app.status.toLowerCase() === statusFilter.toLowerCase();
		return matchesCompany && matchesStatus;
	});
	
	const sortedApplications = [...filteredApplications].sort((a, b) => new Date(b.appliedDate) - new Date(a.appliedDate));

	// Get unique companies for filter dropdown
		const uniqueCompanies = useMemo(() => companies, [companies]);

		const openInterviewReport = async (app) => {
			const report = await openReport(app);
			if (!report) return;
			setReportData(report);
			const cv = typeof app.cvScore === 'number' ? Math.round(app.cvScore) : null;
			const interview = typeof app.interviewScore === 'number' ? Math.round(app.interviewScore) : (typeof report.final_score === 'number' ? Math.round(report.final_score) : null);
			setReportScores({ cv, interview });
			setIsReportOpen(true);
		};
		
	// Handle Give Interview action for shortlisted candidates
	const handleGiveInterview = async (application) => {
		try {
			showToast(`Starting interview session for ${application.position}...`, 'info');
			
			// Navigate directly to the interview page with application ID
			// Chat.jsx will handle the API call to start the interview
			navigate(`/interview/start`, {
				state: { applicationId: application.id }
			});
			
		} catch (error) {
			console.error('Error starting interview:', error);
			showToast('Failed to start interview session. Please try again.', 'error');
		}
	};

	return (
		<div className={styles.profileContainer}>
		<div className={styles.content}>
			<SidebarProfile
				photoUrl={profilePhotoUrl}
				isUploadingPhoto={uploadingPhoto}
				onPhotoSelected={(e) => {
					const file = e.target.files?.[0];
					if (file) handlePhotoUpload(file);
				}}
				cvFileName={cvFile ? cvFile.name : undefined}
				cvPath={cvPath}
				onViewCV={handleViewCV}
				onCvFileChange={(e) => setCvFile(e.target.files?.[0] || null)}
				onUploadCv={handleCVUpload}
				uploadingCV={uploadingCV}
				cvDetails={cvDetails}
				onSaveCvDetails={handleSaveCvDetails}
				showToast={showToast}
			>						{/* Application Statistics Card */}
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
												app.status === "Pending"
										).length
									}
								</span>
								<span className={styles.statLabel}>
									Pending
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
											(app) => app.status === "Interviewed"
										).length
									}
								</span>
								<span className={styles.statLabel}>
									Interviewed
								</span>
							</div>
							<div className={styles.statItem}>
								<span className={styles.statNumber}>
									{
										applications.filter(
											(app) => app.status === "Selected"
										).length
									}
								</span>
								<span className={styles.statLabel}>
									Selected
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
						</SidebarProfile>

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
													<BioForm bio={bio} onChange={setBio} onSubmit={handleProfileUpdate} />
												)}

						{/* Applications Tab */}
												{activeTab === "applications" && (
													<ApplicationsList
														applications={applications}
														companies={uniqueCompanies}
														companyFilter={companyFilter}
														statusFilter={statusFilter}
														setCompanyFilter={setCompanyFilter}
														setStatusFilter={setStatusFilter}
														onClearFilters={() => { setCompanyFilter(""); setStatusFilter(""); }}
														onViewCV={handleViewCV}
														onOpenReport={openInterviewReport}
														onGiveInterview={handleGiveInterview}
													/>
												)}
					</div>
					</div>
				</div>
								{/* Interview Report Modal */}
			<InterviewReportModal
				isOpen={isReportOpen}
				onClose={() => setIsReportOpen(false)}
				report={reportData}
				cvScore={reportScores.cv}
				interviewScore={reportScores.interview}
			/>
			
			{/* Toast Notification */}
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

export default Profile;

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import InterviewReportModal from "features/interview/components/InterviewReportModal";
import DeleteAccountModal from "shared/components/account/DeleteAccountModal";
import Toast from "shared/components/ui/Toast";
import SkeletonCard from "shared/components/ui/SkeletonCard";
import styles from "./Profile.module.css";
import SidebarProfile from "features/candidate/components/SidebarProfile";
import BioForm from "features/candidate/components/BioForm";
import IdentityCardUpload from "features/candidate/components/IdentityCardUpload";
import ApplicationsList from "features/candidate/components/ApplicationsList";
import useCandidateProfile from "features/candidate/hooks/useCandidateProfile";
import useCandidateApplications from "features/candidate/hooks/useCandidateApplications";
import cvService from "features/candidate/api/cvService";
import { getToken } from "shared/utils/session";
import KioskLaunchGuide, { openKiosk } from "features/interview/components/KioskLaunchGuide";

const Profile = () => {
	const navigate = useNavigate();
	const [activeTab, setActiveTab] = useState("bio"); // Add state for active tab
	const [cvFile, setCvFile] = useState(null);

	// Filter states for applications
	const [companyFilter, setCompanyFilter] = useState("");
	const [statusFilter, setStatusFilter] = useState("");
	const [jobTypeFilter, setJobTypeFilter] = useState("");
	const [locationFilter, setLocationFilter] = useState("");
	const [dateRangeFilter, setDateRangeFilter] = useState("");

	// Interview report modal state
	const [isReportOpen, setIsReportOpen] = useState(false);
	const [reportData, setReportData] = useState(null);
	const [reportScores, setReportScores] = useState({ cv: null, interview: null });

	// Delete account modal state
	const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

	// Toast state
	const [toast, setToast] = useState(null);

	// Show toast function
	const showToast = useCallback((message, type = 'info') => {
		setToast({ message, type });
	}, []);

	// Check authentication when component mounts
	useEffect(() => {
		const isLoggedIn = getToken() !== null;
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

	// Add hash change listener to handle navigation from navbar (NO RELOADING)
	useEffect(() => {
		const handleHashChange = () => {
			const hash = window.location.hash;
			// ONLY change tab, don't reload data
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
	const { bio, setBio, profilePhotoUrl, cvPath, cvDetails, uploadingCV, uploadingPhoto, save, uploadCvFile, uploadProfilePhoto, saveCvDetails } = useCandidateProfile(showToast);
	const { applications, loading: loadingApps, openReport, companies } = useCandidateApplications(showToast);
	// Note: applications now update live via CandidateDataContext's realtime
	// subscription (see contexts/CandidateDataContext.jsx) — an interview
	// completing, a status change, etc. all patch the cache directly, so this
	// page no longer needs to poll/refresh itself on interview completion.

	// Handle tab change
	const handleTabChange = (tab) => {
		setActiveTab(tab);
		window.location.hash = `#${tab}`;
	};

	// Handle CV upload
	const handleCVUpload = async (e) => {
		e.preventDefault();
		if (!cvFile) {
			showToast("Please select a CV file.", "error");
			return;
		}
		const ok = await uploadCvFile(cvFile);
		if (ok) {
			setCvFile(null);
		}
	};

	// Handle photo upload
	const handlePhotoUpload = async (file) => {
		if (!file) return;
		await uploadProfilePhoto(file);
	};

	// Handle CV viewing
	const handleViewCV = async (application = null) => {
		try {
			const token = getToken();
			let url;

			// Case 1: Viewing CV for a specific application (from application card)
			if (application?.cv_id) {
				url = `${process.env.REACT_APP_API_URL}/api/cv/${application.cv_id}/preview?token=${token}`;
			} else if (application?.id) {
				// Case 2: Application-level CV view (legacy path)
				url = `${process.env.REACT_APP_API_URL}/api/applications/${application.id}/cv?token=${token}`;
			} else {
				// Case 3: "View Uploaded CV" button — use the primary CV from new multi-CV system
				try {
					const res = await cvService.listCVs();
					const cvs = res?.cvs || [];
					const primaryCv = cvs.find(c => c.is_primary) || cvs[0];
					if (!primaryCv) {
						showToast("No CV uploaded yet. Please upload a CV first.", "error");
						return;
					}
					url = `${process.env.REACT_APP_API_URL}/api/cv/${primaryCv.cv_id}/preview?token=${token}`;
				} catch (innerErr) {
					showToast("No CV uploaded yet. Please upload a CV first.", "error");
					return;
				}
			}

			if (url) {
				window.open(url, '_blank');
			}
		} catch (e) {
			showToast("Failed to open CV. The file may no longer be available.", "error");
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

	// Get unique companies and locations for filter dropdowns
	const uniqueCompanies = useMemo(() => companies, [companies]);
	const uniqueLocations = useMemo(() => {
		const locs = [...new Set(applications.filter(a => a.location).map(a => a.location))];
		return locs.sort();
	}, [applications]);

	const openInterviewReport = async (app) => {
		const report = await openReport(app);
		if (!report) return;
		setReportData(report);
		const cv = typeof app.cvScore === 'number' ? Math.round(app.cvScore) : null;
		const interview = typeof app.interviewScore === 'number' ? Math.round(app.interviewScore) : (typeof report.final_score === 'number' ? Math.round(report.final_score) : null);
		setReportScores({ cv, interview });
		setIsReportOpen(true);
	};

	const [launchApplication, setLaunchApplication] = useState(null);
	const handleGiveInterview = (application) => {
		if (window.electronAPI) { navigate('/interviews/start', { state: { applicationId: application.id } }); return; }
		setLaunchApplication(application);
	};
	const launchInterview = () => openKiosk({ applicationId: launchApplication.id, token: getToken(), apiUrl: process.env.REACT_APP_API_URL || window.location.origin });
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
					onDeleteAccount={() => setIsDeleteModalOpen(true)}
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
												app.statusKey === "pending"
										).length
									}
								</span>
								<span className={styles.statLabel}>
									Awaiting Review
								</span>
							</div>
							<div className={styles.statItem}>
								<span className={styles.statNumber}>
									{
										applications.filter(
											(app) =>
												app.statusKey === "shortlisted"
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
											(app) => app.statusKey === "interviewed"
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
											(app) => app.statusKey === "screening_cleared"
										).length
									}
								</span>
								<span className={styles.statLabel}>
									Screening Cleared
								</span>
							</div>
							<div className={styles.statItem}>
								<span className={styles.statNumber}>
									{
										applications.filter(
											(app) => app.statusKey === "rejected"
										).length
									}
								</span>
								<span className={styles.statLabel}>
									Not Cleared
								</span>
							</div>
						</div>
					</div>

					{/* Identity card: required before interviews, one-time upload */}
					<IdentityCardUpload showToast={showToast} />
				</SidebarProfile>

				<div className={styles.mainContent}>
					{/* Tab Navigation */}
					<div className={styles.tabNavigation}>
						<button
							className={`${styles.tabButton} ${activeTab === "bio" ? styles.activeTab : ""
								}`}
							onClick={() => handleTabChange("bio")}
						>
							<i className="fa fa-user"></i> Bio Data
						</button>
						<button
							className={`${styles.tabButton} ${activeTab === "applications"
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
							loadingApps && applications.length === 0 ? (
								<div>
									{Array.from({ length: 3 }).map((_, i) => (
										<SkeletonCard key={i} variant="job" />
									))}
								</div>
							) : (
								<ApplicationsList
									applications={applications}
									companies={uniqueCompanies}
									locations={uniqueLocations}
									companyFilter={companyFilter}
									statusFilter={statusFilter}
									jobTypeFilter={jobTypeFilter}
									locationFilter={locationFilter}
									dateRangeFilter={dateRangeFilter}
									setCompanyFilter={setCompanyFilter}
									setStatusFilter={setStatusFilter}
									setJobTypeFilter={setJobTypeFilter}
									setLocationFilter={setLocationFilter}
									setDateRangeFilter={setDateRangeFilter}
									onClearFilters={() => {
										setCompanyFilter("");
										setStatusFilter("");
										setJobTypeFilter("");
										setLocationFilter("");
										setDateRangeFilter("");
									}}
									onViewCV={handleViewCV}
									onOpenReport={openInterviewReport}
									onGiveInterview={handleGiveInterview}
								/>
							)
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
			{/* Delete Account Modal */}
			<DeleteAccountModal
				isOpen={isDeleteModalOpen}
				onClose={() => setIsDeleteModalOpen(false)}
			/>
			{/* Toast Notification */}
			{toast && (
				<Toast
					message={toast.message}
					type={toast.type}
					onClose={() => setToast(null)}
				/>
			)}

            <KioskLaunchGuide isOpen={!!launchApplication} onClose={() => setLaunchApplication(null)} onOpen={launchInterview} />
        </div>
    );
};
export default Profile;

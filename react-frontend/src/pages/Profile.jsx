import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import InterviewReportModal from "../components/InterviewReportModal";
import DeleteAccountModal from "../components/common/DeleteAccountModal";
import Toast from "../components/Toast";
import SkeletonCard from "../components/SkeletonCard";
import styles from "./Profile.module.css";
import SidebarProfile from "../components/candidate/SidebarProfile";
import BioForm from "../components/candidate/BioForm";
import ApplicationsList from "../components/candidate/ApplicationsList";
import useCandidateProfile from "../hooks/candidate/useCandidateProfile";
import useCandidateApplications from "../hooks/candidate/useCandidateApplications";
import { viewApplicationCV } from "../services/api";
import cvService from "../services/cvService";
import { getToken, getUser, clearSession, isLoggedIn } from "../utils/sessionManager";

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
	const { bio, setBio, profilePhotoUrl, cvPath, cvDetails, loading: loadingProfile, uploadingCV, uploadingPhoto, save, uploadCvFile, uploadProfilePhoto, saveCvDetails } = useCandidateProfile(showToast);
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

	// States for interview launch flow
	const [isLaunchingInterview, setIsLaunchingInterview] = useState(false);
	const [showDownloadModal, setShowDownloadModal] = useState(false);
	const [pendingDeepLink, setPendingDeepLink] = useState(null);

	const triggerDownload = () => {
		const link = document.createElement('a');
		link.href = 'https://storage.googleapis.com/genhire-downloads/Genhire.exe';
		link.download = 'Genhire.exe';
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	};

	const retryLaunchInterview = () => {
		if (!pendingDeepLink) return;
		setShowDownloadModal(false);
		const iframe = document.createElement("iframe");
		iframe.style.display = "none";
		iframe.src = pendingDeepLink;
		document.body.appendChild(iframe);
		setTimeout(() => { if (document.body.contains(iframe)) document.body.removeChild(iframe); }, 5000);
	};

	// Handle Give Interview action for shortlisted candidates
	const handleGiveInterview = async (application) => {
		try {
			// Check if we are already inside the secure browser via Electron injected API
			if (window.electronAPI) {
				showToast(`Starting interview session for ${application.position}...`, 'info');
				navigate(`/interview/start`, {
					state: { applicationId: application.id }
				});
				return;
			}

			setIsLaunchingInterview(true);
			showToast(`Preparing your interview for ${application.position}...`, 'info');

			// Pre-create session on the platform side so Electron starts instantly (no LLM wait in kiosk)
			const apiUrl = process.env.REACT_APP_API_URL || window.location.origin;
			const sessionRes = await fetch(`${apiUrl}/api/interviews/start`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Authorization": `Bearer ${getToken()}`
				},
				body: JSON.stringify({ application_id: application.id })
			});

			if (!sessionRes.ok) {
				const errData = await sessionRes.json();
				throw new Error(errData.error || errData.message || "Failed to prepare interview session");
			}

			const sessionData = await sessionRes.json();

			const payload = {
				sessionId: sessionData.session_id,
				initialQuestion: sessionData.initial_questions[0],
				applicationId: application.id,
				token: getToken(),
				apiUrl,
				proctoringConfig: sessionData.proctoring_config || {}
			};
			const encodedPayload = btoa(JSON.stringify(payload));
			const customUri = `secure-interview://start?initData=${encodeURIComponent(encodedPayload)}`;

			// Store for retry after install
			setPendingDeepLink(customUri);

			// Fire deep link via hidden iframe
			const iframe = document.createElement("iframe");
			iframe.style.display = "none";
			iframe.src = customUri;
			document.body.appendChild(iframe);
			setTimeout(() => { if (document.body.contains(iframe)) document.body.removeChild(iframe); }, 5000);

			// If window still has focus after 4s → GenHire not installed
			const detectTimer = setTimeout(() => {
				if (document.hasFocus()) {
					triggerDownload();
					setShowDownloadModal(true);
				}
				setIsLaunchingInterview(false);
			}, 4000);

			window.addEventListener('blur', () => {
				clearTimeout(detectTimer);
				setIsLaunchingInterview(false);
			}, { once: true });

		} catch (error) {
			setIsLaunchingInterview(false);
			console.error('Error launching secure browser:', error);
			showToast(error.message || 'Failed to prepare the interview session. Please try again.', 'error');
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

			{/* GenHire not installed — download modal */}
			{showDownloadModal && (
				<div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.7)',zIndex:9999,display:'flex',alignItems:'center',justifyContent:'center'}}>
					<div style={{background:'#1e293b',border:'1px solid #334155',borderRadius:'16px',padding:'36px 40px',maxWidth:'480px',width:'90%',color:'#f1f5f9',fontFamily:'inherit'}}>
						<div style={{fontSize:'2.5rem',marginBottom:'12px'}}>📥</div>
						<h2 style={{margin:'0 0 8px',fontSize:'1.4rem',color:'#f1f5f9'}}>Install GenHire Secure Browser</h2>
						<p style={{margin:'0 0 20px',color:'#94a3b8',fontSize:'0.95rem'}}>
							GenHire was not detected on this device. Your installer download has started automatically.
						</p>
						<div style={{background:'#0f172a',borderRadius:'10px',padding:'16px 20px',marginBottom:'24px'}}>
							<p style={{margin:'0 0 10px',color:'#7dd3fc',fontWeight:600,fontSize:'0.9rem'}}>Follow these steps:</p>
							<ol style={{margin:0,paddingLeft:'20px',color:'#cbd5e1',fontSize:'0.9rem',lineHeight:'1.9'}}>
								<li>Open <strong>Genhire.exe</strong> from your Downloads folder</li>
								<li>Click <strong>Install</strong> — the app will launch automatically</li>
								<li>Return here and click <strong>Retry</strong> below</li>
							</ol>
						</div>
						<div style={{display:'flex',gap:'12px',flexWrap:'wrap'}}>
							<button onClick={triggerDownload} style={{flex:1,padding:'10px 16px',background:'transparent',border:'1px solid #475569',borderRadius:'8px',color:'#94a3b8',cursor:'pointer',fontSize:'0.9rem'}}>
								Download Again
							</button>
							<button onClick={retryLaunchInterview} style={{flex:2,padding:'10px 16px',background:'#3b82f6',border:'none',borderRadius:'8px',color:'#fff',cursor:'pointer',fontWeight:600,fontSize:'0.95rem'}}>
								Retry — Launch Interview
							</button>
						</div>
						<button onClick={() => setShowDownloadModal(false)} style={{marginTop:'16px',width:'100%',padding:'8px',background:'transparent',border:'none',color:'#64748b',cursor:'pointer',fontSize:'0.85rem'}}>
							Cancel
						</button>
					</div>
				</div>
			)}

			{/* Launching overlay */}
			{isLaunchingInterview && (
				<div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.5)',zIndex:9998,display:'flex',alignItems:'center',justifyContent:'center'}}>
					<div style={{background:'#1e293b',border:'1px solid #334155',borderRadius:'16px',padding:'36px 40px',maxWidth:'360px',width:'90%',color:'#f1f5f9',textAlign:'center',fontFamily:'inherit'}}>
						<div style={{width:'40px',height:'40px',border:'3px solid #334155',borderTop:'3px solid #3b82f6',borderRadius:'50%',animation:'spin 0.8s linear infinite',margin:'0 auto 20px'}}></div>
						<h3 style={{margin:'0 0 8px',fontSize:'1.1rem'}}>Preparing Your Interview</h3>
						<p style={{margin:0,color:'#94a3b8',fontSize:'0.9rem'}}>Setting up your session — this takes just a moment...</p>
						<style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
					</div>
				</div>
			)}
		</div>
	);
};

export default Profile;

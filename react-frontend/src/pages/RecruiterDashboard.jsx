import React, { useState, useEffect, useCallback } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import Navbar from "../components/Navbar";
import Toast from "../components/Toast";
import JobCreationModal from "../components/JobCreationModal";
import JobDetailsModal from "../components/JobDetailsModal";
import JobEditModal from "../components/JobEditModal";
import CVViewer from "../components/CVViewer";
import InterviewReportModal from "../components/InterviewReportModal";
import { Tabs, SectionHeader, OverviewMetrics, JobsGrid, CandidatesFilters, CandidatesList, ProfileForm, RecentActivity } from "../components/recruiter";
import styles from "./RecruiterDashboard.module.css";
import useAuth from "../hooks/useAuth";
import useJobs from "../hooks/useJobs";
import useApplications from "../hooks/useApplications";
import { getProfile, updateCompanyProfile as apiUpdateCompanyProfile } from "../services/api";

const RecruiterDashboard = () => {
	const navigate = useNavigate();
	const [searchParams, setSearchParams] = useSearchParams();
	const [activeTab, setActiveTab] = useState("overview");
	const { user, logout } = useAuth('recruiter');
	const [isEditingProfile, setIsEditingProfile] = useState(false);
	const [toasts, setToasts] = useState([]);

	// Toast helper (declared early so hooks can use it)
	const showToast = useCallback((message, type = 'info') => {
		const id = Date.now();
		const newToast = { id, message, type };
		setToasts(prev => [...prev, newToast]);
	}, []);
	const [isJobModalOpen, setIsJobModalOpen] = useState(false);
	const [isCVViewerOpen, setIsCVViewerOpen] = useState(false);
	const [selectedCandidate, setSelectedCandidate] = useState(null);
	const [selectedJob, setSelectedJob] = useState(null);
	const [isJobDetailsModalOpen, setIsJobDetailsModalOpen] = useState(false);
	const [isJobEditModalOpen, setIsJobEditModalOpen] = useState(false);
	const [isReportOpen, setIsReportOpen] = useState(false);
	const [reportData, setReportData] = useState(null);
	const [reportScores, setReportScores] = useState({ cv: null, interview: null });
	const [selectedPosition, setSelectedPosition] = useState("");
	const [selectedStatus, setSelectedStatus] = useState("");
	const [companyProfile, setCompanyProfile] = useState({
		companyName: "TechCorp Solutions",
		industry: "Technology",
		location: "San Francisco, CA",
		size: "100-500 employees",
		website: "https://techcorp.com",
		description: "Leading technology solutions provider focused on AI and machine learning innovations."
	});

	// Jobs and applications via hooks
	const { jobs: jobPostings, load: loadJobs, create: saveJobPosting, update: updateJobPosting, remove: deleteJobPosting } = useJobs(showToast);
	const { applications, load: loadApplications, updateStatus: updateApplicationStatus, fetchInterviewReport } = useApplications(showToast);

	// Load company profile once; hooks load jobs/applications themselves
	useEffect(() => {
		loadCompanyProfile();
	}, []);

	const loadCompanyProfile = async () => {
		try {
			const profileData = await getProfile();
			if (profileData?.user_type === 'recruiter') {
				setCompanyProfile({
					companyName: profileData.company_name || "TechCorp Solutions",
					industry: profileData.company_industry || "Technology",
					location: profileData.location || "San Francisco, CA",
					size: profileData.company_size || "100-500 employees",
					website: profileData.company_website || "https://techcorp.com",
					description: profileData.company_description || "Leading technology solutions provider focused on AI and machine learning innovations."
				});
			}
		} catch (error) {
			console.error('Error loading company profile:', error);
		}
	};

	// provided by useJobs

	// provided by useApplications

	// provided by useApplications

	// Sample candidate data (keeping some mock data for reference)
	const [candidates, setCandidates] = useState([
		{
			id: 1,
			name: "John Doe",
			email: "john.doe@email.com",
			phone: "+1 (555) 123-4567",
			jobId: 1,
			jobTitle: "Senior Business Development Manager",
			appliedDate: "2025-08-05",
			status: "Interviewed",
			cvMatchScore: 92,
			interviewScore: 85,
			interviewDate: "2025-08-08",
			experience: "6 years",
			location: "San Francisco, CA",
			skills: ["Sales Strategy", "Client Acquisition", "Market Research"],
			cvUrl: "/uploads/cv/john_doe_cv.pdf"
		},
		{
			id: 2,
			name: "Jane Smith",
			email: "jane.smith@email.com",
			phone: "+1 (555) 987-6543",
			jobId: 1,
			jobTitle: "Senior Business Development Manager",
			appliedDate: "2025-08-06",
			status: "Selected",
			cvMatchScore: 88,
			interviewScore: 91,
			interviewDate: "2025-08-09",
			experience: "7 years",
			location: "San Francisco, CA",
			skills: ["Sales Strategy", "Negotiation", "Team Leadership"],
			cvUrl: "/uploads/cv/jane_smith_cv.pdf"
		},
		{
			id: 3,
			name: "Mike Johnson",
			email: "mike.johnson@email.com",
			phone: "+1 (555) 456-7890",
			jobId: 2,
			jobTitle: "Strategic Partnerships Manager",
			appliedDate: "2025-08-07",
			status: "Pending Interview",
			cvMatchScore: 76,
			interviewScore: null,
			interviewDate: null,
			experience: "4 years",
			location: "New York, NY",
			skills: ["Partnership Development", "Contract Negotiation"],
			cvUrl: "/uploads/cv/mike_johnson_cv.pdf"
		},
		{
			id: 4,
			name: "Sarah Wilson",
			email: "sarah.wilson@email.com",
			phone: "+1 (555) 321-0987",
			jobId: 1,
			jobTitle: "Senior Business Development Manager",
			appliedDate: "2025-08-08",
			status: "Rejected",
			cvMatchScore: 65,
			interviewScore: 58,
			interviewDate: "2025-08-09",
			experience: "3 years",
			location: "Los Angeles, CA",
			skills: ["Sales", "Customer Relations"],
			cvUrl: "/uploads/cv/sarah_wilson_cv.pdf"
		}
	]);

	useEffect(() => {
		// Check URL parameters for active tab
		const tabParam = searchParams.get("tab");
		if (tabParam && ["overview", "jobs", "candidates", "profile"].includes(tabParam)) {
			setActiveTab(tabParam);
		}
	}, [searchParams]);

	// replaced by useJobs

	// provided by useJobs

	// provided by useJobs

	// provided by useJobs

	const getStatusColor = (status) => {
		const s = String(status || '').toLowerCase();
		switch (s) {
			case "active": return "#27ae60";
			case "draft": return "#f39c12";
			case "closed": return "#e74c3c";
			case "scheduled": return "#3498db";
			case "selected": return "#27ae60";
			case "rejected": return "#e74c3c";
			case "interviewed": return "#9b59b6";
			case "pending":
			case "pending interview": return "#f39c12";
			case "reviewed": return "#3498db";
			case "shortlisted": return "#8e44ad";
			default: return "#95a5a6";
		}
	};

	const displayStatus = (status) => {
		const s = String(status || '').toLowerCase();
		const map = {
			active: 'Active',
			published: 'Published',
			closed: 'Closed',
			draft: 'Draft',
			scheduled: 'Scheduled',
			pending: 'Pending',
			reviewed: 'Reviewed',
			shortlisted: 'Shortlisted',
			interviewed: 'Interviewed',
			selected: 'Selected',
			rejected: 'Rejected'
		};
		return map[s] || (s ? (s.charAt(0).toUpperCase() + s.slice(1)) : '');
	};

	const handleLogout = () => {
		logout();
	};

	const getCandidatesForJob = (jobId) => {
		// applications from backend contain job_id as string matching job._id
		const jId = String(jobId || '');
		return applications.filter(app => String(app.job_id) === jId);
	};

	// Filter applications based on selected position and status
	const getFilteredCandidates = () => {
		let filtered = applications;

		if (selectedPosition) {
			filtered = filtered.filter(app => app.job_details?.title === selectedPosition);
		}

		if (selectedStatus) {
			// Map backend status to display status
			const statusMap = {
				'pending': 'Pending Interview',
				'reviewed': 'Pending Interview',
				'shortlisted': 'Pending Interview',
				'interviewed': 'Interviewed',
				'selected': 'Selected',
				'rejected': 'Rejected'
			};
			filtered = filtered.filter(app => statusMap[String(app.status || '').toLowerCase()] === selectedStatus);
		}

		return filtered;
	};

	const viewInterviewReport = async (applicationId) => {
		const report = await fetchInterviewReport(applicationId);
		if (!report) return;
		setReportData(report);
		const app = applications.find(a => a._id === applicationId);
		const cv = typeof app?.cv_score === 'number' ? Math.round(app.cv_score) : (typeof app?.similarity_score === 'number' ? Math.round(app.similarity_score * 100) : null);
		const interview = typeof app?.interview_score === 'number' ? Math.round(app.interview_score) : (typeof report.final_score === 'number' ? Math.round(report.final_score) : null);
		setReportScores({ cv, interview });
		setIsReportOpen(true);
	};

	// Handle filter changes
	const handlePositionFilter = (e) => {
		setSelectedPosition(e.target.value);
	};

	const handleStatusFilter = (e) => {
		setSelectedStatus(e.target.value);
	};

	const handleClearFilters = () => {
		setSelectedPosition("");
		setSelectedStatus("");
		showToast("Filters cleared", "info");
	};

	// Ensure job stats refresh after application status changes
	const handleUpdateApplicationStatus = async (applicationId, newStatus) => {
		const ok = await updateApplicationStatus(applicationId, newStatus);
		if (ok) {
			// refresh jobs to keep counts accurate
			loadJobs();
		}
	};

	// Handle tab changes with URL updates
	const handleTabChange = (tab) => {
		setActiveTab(tab);
		setSearchParams({ tab });
	};

	// showToast defined earlier for hooks

	const removeToast = (id) => {
		setToasts(prev => prev.filter(toast => toast.id !== id));
	};

	// Function to handle creating a new job
	const handleCreateNewJob = () => {
		setIsJobModalOpen(true);
	};

	const handleJobModalClose = () => {
		setIsJobModalOpen(false);
	};

	const handleJobCreate = async (newJob) => {
		// Save to backend
		const success = await saveJobPosting(newJob);
		if (success) {
			console.log("New job created:", newJob);
		}
	};

	// Function to handle candidate actions
	const handleViewCV = (candidate) => {
		setSelectedCandidate(candidate);
		setIsCVViewerOpen(true);
		showToast(`Opening CV for ${candidate.name}`, "info");
		console.log("Viewing CV for:", candidate);
	};

	const handleCloseCVViewer = () => {
		setIsCVViewerOpen(false);
		setSelectedCandidate(null);
	};

	const handleSelectCandidate = (candidate) => {
		// Update candidate status to selected
		setCandidates(prev => prev.map(c => 
			c.id === candidate.id ? { ...c, status: "Selected" } : c
		));
		showToast(`${candidate.name} has been selected!`, "success");
	};

	const handleRejectCandidate = (candidate) => {
		// Update candidate status to rejected
		setCandidates(prev => prev.map(c => 
			c.id === candidate.id ? { ...c, status: "Rejected" } : c
		));
		showToast(`${candidate.name} has been rejected`, "warning");
	};

	const handleScheduleInterview = (candidate) => {
		showToast(`Interview scheduling for ${candidate.name}`, "info");
		console.log("Scheduling interview for:", candidate);
	};

	// Function to handle job actions
	const handleViewJobDetails = (job) => {
		setSelectedJob(job);
		setIsJobDetailsModalOpen(true);
		showToast(`Viewing details for ${job.title}`, "info");
	};

	const handleViewJobCandidates = (job) => {
		const jobCandidates = getCandidatesForJob(job._id || job.id);
		// Switch to candidates tab and filter by this job
		setActiveTab("candidates");
		setSelectedPosition(job.title);
		// Update URL to reflect the change
		searchParams.set('tab', 'candidates');
		setSearchParams(searchParams);
		showToast(`Showing ${jobCandidates.length} candidates for ${job.title}`, "info");
	};

	const handleEditJob = (job) => {
		setSelectedJob(job);
		setIsJobEditModalOpen(true);
		showToast(`Opening editor for ${job.title}`, "info");
	};

	// Company Profile handlers
	const handleEditProfile = () => {
		setIsEditingProfile(true);
		showToast("Profile editing enabled", "info");
		console.log("Enabling profile editing...");
	};

	const handleSaveProfile = async () => {
		try {
			await apiUpdateCompanyProfile({
				company_name: companyProfile.companyName,
				company_industry: companyProfile.industry,
				company_size: companyProfile.size,
				company_website: companyProfile.website,
				company_description: companyProfile.description
			});
			setIsEditingProfile(false);
			showToast("Company profile saved successfully!", "success");
		} catch (error) {
			console.error("Error saving company profile:", error);
			showToast("Failed to save company profile", "error");
		}
	};

	const handleCancelEdit = () => {
		setIsEditingProfile(false);
		showToast("Changes cancelled", "warning");
		console.log("Cancelling profile edit...");
	};

	// Job modal handlers
	const handleCloseJobDetails = () => {
		setIsJobDetailsModalOpen(false);
		setSelectedJob(null);
	};

	const handleCloseJobEdit = () => {
		setIsJobEditModalOpen(false);
		setSelectedJob(null);
	};

	const handleJobUpdate = async (updatedJob) => {
		const id = updatedJob._id || updatedJob.id;
		const ok = await updateJobPosting(id, updatedJob);
		if (ok) {
			showToast(`${updatedJob.title} has been updated successfully!`, "success");
		}
	};

	const handleEditFromDetails = (job) => {
		// Close the details modal and open the edit modal
		setIsJobDetailsModalOpen(false);
		setIsJobEditModalOpen(true);
		setSelectedJob(job);
		showToast(`Opening editor for ${job.title}`, "info");
	};

	if (!user) {
		return (
			<div className={styles.loadingContainer}>
				<div className={styles.loadingSpinner}>Loading...</div>
			</div>
		);
	}

	return (
		<div className={styles.dashboardContainer}>
			{/* Use shared Navbar component */}
			<Navbar userType="recruiter" />

			{/* Toast notifications */}
			{toasts.map(toast => (
				<Toast
					key={toast.id}
					message={toast.message}
					type={toast.type}
					onClose={() => removeToast(toast.id)}
				/>
			))}

			{/* Job Creation Modal */}
			<JobCreationModal
				isOpen={isJobModalOpen}
				onClose={handleJobModalClose}
				onJobCreate={handleJobCreate}
			/>

			{/* Job Details Modal */}
			<JobDetailsModal
				isOpen={isJobDetailsModalOpen}
				onClose={handleCloseJobDetails}
				job={selectedJob}
				onEdit={handleEditFromDetails}
			/>

			{/* Job Edit Modal */}
			<JobEditModal
				isOpen={isJobEditModalOpen}
				onClose={handleCloseJobEdit}
				job={selectedJob}
				onJobUpdate={handleJobUpdate}
			/>

			{/* CV Viewer Modal */}
			<CVViewer
				isOpen={isCVViewerOpen}
				onClose={handleCloseCVViewer}
				candidate={selectedCandidate}
			/>

			{/* Interview Report Modal */}
			<InterviewReportModal
				isOpen={isReportOpen}
				onClose={() => setIsReportOpen(false)}
				report={reportData}
				cvScore={reportScores.cv}
				interviewScore={reportScores.interview}
			/>

			{/* Navigation Tabs */}
			<Tabs activeTab={activeTab} onChange={handleTabChange} />

			<div className={styles.mainContent}>

				{/* Tab Content */}
				{activeTab === "overview" && (
					<div className={styles.overviewSection}>
						<div className={styles.welcomeSection}>
							<h2>Dashboard Overview</h2>
							<p>Manage your job postings, track candidates, and monitor recruitment progress</p>
						</div>
						<OverviewMetrics 
							jobPostingsCount={jobPostings.filter(job => String(job.status || '').toLowerCase() === "active").length}
							applicationsCount={applications.length}
						/>

						{/* Recent Activity */}
						<RecentActivity applications={applications} />
					</div>
				)}

				{activeTab === "jobs" && (
						<div className={styles.jobsContent}>
							<SectionHeader 
								title="Job Postings Management"
								actions={(
									<button className={styles.primaryButton} onClick={handleCreateNewJob}>
										<i className="fa fa-plus"></i> Create New Job
									</button>
								)}
							/>
							<JobsGrid 
								jobs={jobPostings}
								getStatusColor={getStatusColor}
								displayStatus={displayStatus}
								getCandidatesForJob={getCandidatesForJob}
								onViewDetails={handleViewJobDetails}
								onViewCandidates={handleViewJobCandidates}
								onEdit={handleEditJob}
							/>
						</div>
					)}

					{activeTab === "candidates" && (
						<div className={styles.candidatesContent}>
							<SectionHeader title="Candidate Management" />
							<CandidatesFilters 
								jobPostings={jobPostings}
								selectedPosition={selectedPosition}
								selectedStatus={selectedStatus}
								onPositionChange={(v) => setSelectedPosition(v)}
								onStatusChange={(v) => setSelectedStatus(v)}
								onClear={handleClearFilters}
							/>
							<CandidatesList 
								applications={getFilteredCandidates()}
								totalCount={applications.length}
								selectedPosition={selectedPosition}
								selectedStatus={selectedStatus}
								onClear={handleClearFilters}
								displayStatus={displayStatus}
								updateApplicationStatus={handleUpdateApplicationStatus}
								viewInterviewReport={viewInterviewReport}
							/>
						</div>
					)}

					{activeTab === "profile" && (
                        <div className={styles.profileContent}>
                            <SectionHeader 
                                title="Company Profile"
                                actions={(
                                    !isEditingProfile ? (
                                        <button className={styles.primaryButton} onClick={handleEditProfile}>
                                            <i className="fa fa-edit"></i> Edit Profile
                                        </button>
                                    ) : (
                                        <span style={{ color: "#4a90e2", fontWeight: 500 }}>
                                            <i className="fa fa-edit"></i> Editing Mode
                                        </span>
                                    )
                                )}
                            />
                            <ProfileForm 
                                companyProfile={companyProfile}
                                isEditing={isEditingProfile}
                                onChange={setCompanyProfile}
                                onSave={handleSaveProfile}
                                onCancel={handleCancelEdit}
                            />
                        </div>
                    )}
				</div>
		</div>
	);
};

export default RecruiterDashboard;

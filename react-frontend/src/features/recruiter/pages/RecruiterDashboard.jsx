import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import Navbar from "shared/components/layout/Navbar";
import Toast from "shared/components/ui/Toast";
import SkeletonCard from "shared/components/ui/SkeletonCard";
import JobEditModal from "features/recruiter/components/JobEditModal";
import JobDetailsModal from "features/recruiter/components/JobDetailsModal";
import JobCreationModal from "features/recruiter/components/JobCreationModal";
import { downloadScreeningClearedExport, saveBlob } from "features/recruiter/api/jobExportApi";
import CVViewer from "features/candidate/components/CVViewer";
import InterviewReportModal from "features/interview/components/InterviewReportModal";
import ProctoringResultModal from "features/interview/components/ProctoringResultModal";
import DeleteAccountModal from "shared/components/account/DeleteAccountModal";
import {
  Tabs,
  SectionHeader,
  OverviewMetrics,
  JobsGrid,
  CandidatesFilters,
  CandidatesList,
  ProfileForm,
  RecentActivity,
  InviteCandidatesModal,
} from "features/recruiter/components";
import styles from "./RecruiterDashboard.module.css";
import useAuth from "shared/hooks/useAuth";
import useJobs from "features/candidate/hooks/useJobs";
import useApplications from "features/candidate/hooks/useApplications";
import {
  getProfile,
  updateCompanyProfile as apiUpdateCompanyProfile,
} from "shared/api/endpoints";
import { getUser, setUser } from "shared/utils/session";

const RecruiterDashboard = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState("overview");
  const { user, rejectionReason, refreshUser } = useAuth("recruiter");
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // Check verification status — reads session storage on mount then polls backend every 30s
  const [isVerified, setIsVerified] = useState(true);

  useEffect(() => {
    // Fast initial read from session storage
    const parsed = getUser();
    if (parsed) {
      setIsVerified(parsed.isVerified !== false && parsed.is_verified !== false);
    }

    // Poll backend so admin approval/rejection reflects immediately without manual refresh
    const checkVerificationStatus = async () => {
      try {
        const profile = await getProfile();
        if (profile && profile.user_type === "recruiter") {
          const verified = profile.is_verified !== false;
          setIsVerified(verified);
          // Sync session storage so useAuth hook state stays consistent
          const currentUser = getUser();
          if (currentUser) {
            setUser({
              ...currentUser,
              is_verified: profile.is_verified,
              isVerified: profile.is_verified,
              rejection_reason: profile.rejection_reason || null,
            });
            refreshUser();
          }
        }
      } catch {
        // Silent fail — stale session storage value stays active
      }
    };

    checkVerificationStatus();
    const interval = setInterval(checkVerificationStatus, 30000);
    return () => clearInterval(interval);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Toast helper (declared early so hooks can use it)
  const showToast = useCallback((message, type = "info") => {
    const id = Date.now();
    const newToast = { id, message, type };
    setToasts((prev) => [...prev, newToast]);
  }, []);
  const [isJobModalOpen, setIsJobModalOpen] = useState(false);
  const [isCVViewerOpen, setIsCVViewerOpen] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);
  const [isJobDetailsModalOpen, setIsJobDetailsModalOpen] = useState(false);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [selectedJobForInvite, setSelectedJobForInvite] = useState(null);
  const [isJobEditModalOpen, setIsJobEditModalOpen] = useState(false);
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [isProctoringModalOpen, setIsProctoringModalOpen] = useState(false); // State for the new modal
  const [reportData, setReportData] = useState(null);
  const [reportScores, setReportScores] = useState({
    cv: null,
    interview: null,
  });
  const [selectedPosition, setSelectedPosition] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");
  const [minCvScore, setMinCvScore] = useState("");
  const [minInterviewScore, setMinInterviewScore] = useState("");
  const [minProctoringScore, setMinProctoringScore] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [companyProfile, setCompanyProfile] = useState({
    email: "",
    companyName: "",
    industry: "",
    location: "",
    size: "",
    website: "",
    description: "",
  });

  // Jobs and applications via hooks
  const {
    jobs: jobPostings,
    loading: jobsLoading,
    load: loadJobs,
    create: saveJobPosting,
    update: updateJobPosting,
    remove: deleteJobPosting,
  } = useJobs(showToast);
  const {
    applications,
    loading: applicationsLoading,
    load: loadApplications,
    updateStatus: updateApplicationStatus,
    fetchInterviewReport,
  } = useApplications(showToast);

  // Load company profile once; hooks load jobs/applications themselves
  useEffect(() => {
    loadCompanyProfile();
  }, []);

  const loadCompanyProfile = async () => {
    try {
      const profileData = await getProfile();
      if (profileData?.user_type === "recruiter") {
        setCompanyProfile({
          email: profileData.email || "",
          companyName: profileData.company_name || "",
          industry: profileData.company_industry || "",
          location: profileData.company_location || profileData.location || "",
          size: profileData.company_size || "",
          website: profileData.company_website || "",
          description: profileData.company_description || "",
        });
      }
    } catch (error) {
      console.error("Error loading company profile:", error);
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
      cvUrl: "/uploads/cv/john_doe_cv.pdf",
    },
    {
      id: 2,
      name: "Jane Smith",
      email: "jane.smith@email.com",
      phone: "+1 (555) 987-6543",
      jobId: 1,
      jobTitle: "Senior Business Development Manager",
      appliedDate: "2025-08-06",
      status: "Screening Cleared",
      cvMatchScore: 88,
      interviewScore: 91,
      interviewDate: "2025-08-09",
      experience: "7 years",
      location: "San Francisco, CA",
      skills: ["Sales Strategy", "Negotiation", "Team Leadership"],
      cvUrl: "/uploads/cv/jane_smith_cv.pdf",
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
      cvUrl: "/uploads/cv/mike_johnson_cv.pdf",
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
      cvUrl: "/uploads/cv/sarah_wilson_cv.pdf",
    },
  ]);

  useEffect(() => {
    // Check URL parameters for active tab
    const tabParam = searchParams.get("tab");
    if (
      tabParam &&
      ["overview", "jobs", "candidates", "profile"].includes(tabParam)
    ) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  // replaced by useJobs

  // provided by useJobs

  // provided by useJobs

  // provided by useJobs

  const getStatusColor = (status) => {
    const s = String(status || "").toLowerCase();
    switch (s) {
      case "active":
        return "#27ae60";
      case "draft":
        return "#f39c12";
      case "paused":
        return "#f59e0b";
      case "closed":
        return "#e74c3c";
      case "scheduled":
        return "#3498db";
      case "screening_cleared":
      case "selected": // legacy name for screening_cleared
        return "#27ae60";
      case "rejected":
        return "#e74c3c";
      case "interviewed":
        return "#9b59b6";
      case "pending":
      case "pending interview":
        return "#f39c12";
      case "reviewed":
        return "#3498db";
      case "shortlisted":
        return "#8e44ad";
      default:
        return "#95a5a6";
    }
  };

  const displayStatus = (status) => {
    const s = String(status || "").toLowerCase();
    const map = {
      active: "Active",
      published: "Published",
      closed: "Closed",
      draft: "Draft",
      paused: "Paused",
      scheduled: "Scheduled",
      pending: "Pending",
      reviewed: "Reviewed",
      shortlisted: "Shortlisted",
      interviewed: "Interviewed",
      screening_cleared: "Screening Cleared",
      selected: "Screening Cleared", // legacy name
      rejected: "Screening Not Cleared",
    };
    return map[s] || (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");
  };

  const getCandidatesForJob = (jobId) => {
    // applications from backend contain job_id as string matching job._id
    const jId = String(jobId || "");
    return applications.filter((app) => String(app.job_id) === jId);
  };

  // Filter + sort applications for the shortlist view. Everything here runs
  // client-side over the already-fully-fetched `applications` array (no new
  // network calls) — see Step 7 plan for why full server-side pagination was
  // deliberately left out of this pass.
  const getFilteredCandidates = () => {
    let filtered = applications;

    if (selectedPosition) {
      filtered = filtered.filter(
        (app) => app.job_details?.title === selectedPosition
      );
    }

    if (selectedStatus) {
      // Direct status matching with proper case handling; legacy "selected"
      // docs count as "screening_cleared".
      const normalizeAppStatus = (s) => {
        const v = String(s || "").toLowerCase();
        return v === "selected" ? "screening_cleared" : v;
      };
      const normalizedSelectedStatus = normalizeAppStatus(selectedStatus);
      filtered = filtered.filter(
        (app) => normalizeAppStatus(app.status) === normalizedSelectedStatus
      );
    }

    if (minCvScore) {
      const threshold = Number(minCvScore);
      filtered = filtered.filter(
        (app) => typeof app.cv_score === "number" && app.cv_score >= threshold
      );
    }

    if (minInterviewScore) {
      const threshold = Number(minInterviewScore);
      filtered = filtered.filter(
        (app) => typeof app.interview_score === "number" && app.interview_score >= threshold
      );
    }

    if (minProctoringScore) {
      const threshold = Number(minProctoringScore);
      filtered = filtered.filter(
        (app) => typeof app.proctoring_score === "number" && app.proctoring_score >= threshold
      );
    }

    const byDateDesc = (a, b) => new Date(b.applied_at || 0) - new Date(a.applied_at || 0);
    const byScoreDesc = (field) => (a, b) => {
      const av = typeof a[field] === "number" ? a[field] : -Infinity;
      const bv = typeof b[field] === "number" ? b[field] : -Infinity;
      return bv - av;
    };

    const sorted = [...filtered];
    switch (sortBy) {
      case "oldest":
        sorted.sort((a, b) => -byDateDesc(a, b));
        break;
      case "cv_score":
        sorted.sort(byScoreDesc("cv_score"));
        break;
      case "interview_score":
        sorted.sort(byScoreDesc("interview_score"));
        break;
      case "proctoring_score":
        sorted.sort(byScoreDesc("proctoring_score"));
        break;
      case "combined_score":
        sorted.sort(byScoreDesc("combined_score"));
        break;
      case "newest":
      default:
        sorted.sort(byDateDesc);
        break;
    }

    return sorted;
  };

  const viewInterviewReport = async (applicationId) => {
    const report = await fetchInterviewReport(applicationId);
    if (!report) return;
    setReportData(report);
    const app = applications.find((a) => a._id === applicationId);
    const cv =
      typeof app?.cv_score === "number"
        ? Math.round(app.cv_score)
        : typeof app?.similarity_score === "number"
        ? Math.round(app.similarity_score * 100)
        : null;
    const interview =
      typeof app?.interview_score === "number"
        ? Math.round(app.interview_score)
        : typeof report.final_score === "number"
        ? Math.round(report.final_score)
        : null;
    setReportScores({ cv, interview });
    setIsReportOpen(true);
  };
  const viewProctoringReport = async (applicationId) => {
    const report = await fetchInterviewReport(applicationId);
    if (!report) return;
    setReportData(report);
    setIsProctoringModalOpen(true);
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
    setMinCvScore("");
    setMinInterviewScore("");
    setMinProctoringScore("");
    showToast("Filters cleared", "info");
  };

  // Ensure job stats refresh after application status changes
  const handleUpdateApplicationStatus = async (applicationId, newStatus) => {
    const ok = await updateApplicationStatus(applicationId, newStatus);
    if (ok) {
      // refresh both jobs and applications to keep data in sync
      loadJobs();
      loadApplications();
      showToast(`Application status updated to ${newStatus}`, "success");
    }
  };

  // Handle tab changes with URL updates
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  // showToast defined earlier for hooks

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  // Function to handle creating a new job
  const handleCreateNewJob = () => {
    setIsJobModalOpen(true);
  };

  const handleJobModalClose = () => {
    setIsJobModalOpen(false);
  };

  const handleJobCreate = async (newJob, jdFile) => {
    // Save to backend
    return saveJobPosting(newJob, jdFile);
  };

  // Function to handle candidate actions
  const handleViewCV = (candidate) => {
    setSelectedCandidate(candidate);
    setIsCVViewerOpen(true);
    showToast(`Opening CV for ${candidate.name}`, "info");
  };

  const handleCloseCVViewer = () => {
    setIsCVViewerOpen(false);
    setSelectedCandidate(null);
  };

  const handleSelectCandidate = (candidate) => {
    // Mark candidate as having cleared the screening round
    setCandidates((prev) =>
      prev.map((c) =>
        c.id === candidate.id ? { ...c, status: "Screening Cleared" } : c
      )
    );
    showToast(`${candidate.name} has cleared screening!`, "success");
  };

  const handleRejectCandidate = (candidate) => {
    // Update candidate status to rejected
    setCandidates((prev) =>
      prev.map((c) =>
        c.id === candidate.id ? { ...c, status: "Rejected" } : c
      )
    );
    showToast(`${candidate.name} has been rejected`, "warning");
  };

  const handleScheduleInterview = (candidate) => {
    showToast(`Interview scheduling for ${candidate.name}`, "info");
  };

  // Function to handle job actions
  const handleExportCleared = async (job) => {
    const jobId = job._id || job.id;
    try {
      showToast("Preparing screening-cleared export…", "info");
      const blob = await downloadScreeningClearedExport(jobId, "xlsx");
      const stem = (job.title || "job").replace(/[^\w\- ]+/g, "").trim().replace(/\s+/g, "_");
      saveBlob(blob, `screening_cleared_${stem}.xlsx`);
    } catch (err) {
      showToast(err.message || "Failed to export screening-cleared candidates", "error");
    }
  };

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
    searchParams.set("tab", "candidates");
    setSearchParams(searchParams);
    showToast(
      `Showing ${jobCandidates.length} candidates for ${job.title}`,
      "info"
    );
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
  };

  const handleSaveProfile = async () => {
    try {
      await apiUpdateCompanyProfile({
        company_name: companyProfile.companyName,
        company_industry: companyProfile.industry,
        company_location: companyProfile.location,
        company_size: companyProfile.size,
        company_website: companyProfile.website,
        company_description: companyProfile.description,
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
    // Try multiple sources for the job ID
    const id =
      updatedJob._id || updatedJob.id || selectedJob?._id || selectedJob?.id;
    if (!id) {
      showToast("Error: Job ID not found", "error");
      console.error("Job ID missing from:", { updatedJob, selectedJob });
      return;
    }
    const ok = await updateJobPosting(id, updatedJob);
    if (ok) {
      showToast(
        `${updatedJob.title} has been updated successfully!`,
        "success"
      );
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

      {/* Delete Account Modal */}
      <DeleteAccountModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
      />

      {/* Rejection Banner */}
      {rejectionReason && (
        <div
          className={styles.verificationBanner}
          style={{ backgroundColor: "#fff3f3", borderLeft: "4px solid #dc3545" }}
        >
          <div className={styles.bannerContent}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="#dc3545"
              style={{ width: "28px", height: "28px", flexShrink: 0, marginTop: "2px" }}
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
                clipRule="evenodd"
              />
            </svg>
            <div style={{ flex: 1 }}>
              <strong style={{ color: "#dc3545", fontSize: "15px" }}>
                Your Recruiter Application Was Not Approved
              </strong>
              <p style={{ color: "#842029", margin: "6px 0 4px" }}>
                <strong>Reason:</strong> {rejectionReason}
              </p>
              <p style={{ color: "#6b7280", margin: "0 0 12px", fontSize: "13px" }}>
                To continue using GenHire as a recruiter, please delete this account and
                register again with the correct details. Make sure your company information,
                credentials, and contact details are accurate before reapplying.
              </p>
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                <button
                  onClick={() => setIsDeleteModalOpen(true)}
                  style={{
                    padding: "8px 18px",
                    background: "#dc3545",
                    color: "white",
                    border: "none",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontWeight: "600",
                    fontSize: "13px",
                  }}
                >
                  Delete Account & Reapply
                </button>
                <a
                  href="mailto:support@genhire.com"
                  style={{
                    padding: "8px 18px",
                    background: "transparent",
                    color: "#dc3545",
                    border: "1px solid #dc3545",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontWeight: "600",
                    fontSize: "13px",
                    textDecoration: "none",
                    display: "inline-flex",
                    alignItems: "center",
                  }}
                >
                  Contact Support
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Verification Pending Banner */}
      {!isVerified && !rejectionReason && (
        <div className={styles.verificationBanner}>
          <div className={styles.bannerContent}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="#f59e0b"
              style={{ width: "28px", height: "28px", flexShrink: 0, marginTop: "2px" }}
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
                clipRule="evenodd"
              />
            </svg>
            <div>
              <strong style={{ fontSize: "15px" }}>Account Pending Verification</strong>
              <p style={{ margin: "6px 0 0", color: "#6b7280", fontSize: "13px" }}>
                Your recruiter account is under review by our admin team — this usually takes
                less than 24 hours. You can explore your dashboard and profile in the meantime,
                but job posting and candidate features will be unlocked once approved.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Toast notifications */}
      {toasts.map((toast) => (
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
        showToast={showToast}
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
        jobData={selectedJob}
        onJobUpdate={handleJobUpdate}
        showToast={showToast}
      />

      {/* Invite Candidates Modal */}
      <InviteCandidatesModal
        isOpen={isInviteModalOpen}
        onClose={() => {
          setIsInviteModalOpen(false);
          setSelectedJobForInvite(null);
        }}
        job={selectedJobForInvite}
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
      {/* Proctoring Result Modal */}
      <ProctoringResultModal
        isOpen={isProctoringModalOpen}
        onClose={() => setIsProctoringModalOpen(false)}
        report={reportData}
      />
      {/* Navigation Tabs */}
      <Tabs activeTab={activeTab} onChange={handleTabChange} />

      <div className={styles.mainContent}>
        {/* Tab Content */}
        {activeTab === "overview" && (
          <div className={styles.overviewSection}>
            <div className={styles.welcomeSection}>
              <h2>Dashboard Overview</h2>
              <p>
                Manage your job postings, track candidates, and monitor
                recruitment progress
              </p>
            </div>

            <OverviewMetrics
              jobPostingsCount={
                jobPostings.filter(
                  (job) => String(job.status || "").toLowerCase() === "active"
                ).length
              }
              applicationsCount={applications.length}
              applications={applications}
            />

            {/* Recent Activity */}
            <RecentActivity applications={applications} />
          </div>
        )}

        {activeTab === "jobs" && (
          <div className={styles.jobsContent}>
            <SectionHeader
              title="Job Postings Management"
              actions={
                <button
                  className={`${styles.primaryButton} ${
                    !isVerified ? styles.disabledButton : ""
                  }`}
                  onClick={
                    isVerified
                      ? handleCreateNewJob
                      : () =>
                          showToast(
                            "Your account must be verified to create job postings",
                            "warning"
                          )
                  }
                  disabled={!isVerified}
                >
                  <i className="fa fa-plus"></i> Create New Job
                  {!isVerified && <span className={styles.lockedIcon}>🔒</span>}
                </button>
              }
            />
            {!isVerified && (
              <div className={styles.limitedAccessNotice}>
                <p>
                  Job posting features are disabled until your account is
                  verified. You can still view existing job postings.
                </p>
              </div>
            )}
            {jobsLoading && jobPostings.length === 0 ? (
              <div className={styles.jobsGrid}>
                {Array.from({ length: 3 }).map((_, i) => (
                  <SkeletonCard key={i} variant="job" />
                ))}
              </div>
            ) : (
              <JobsGrid
                jobs={jobPostings}
                getStatusColor={getStatusColor}
                displayStatus={displayStatus}
                getCandidatesForJob={getCandidatesForJob}
                onViewDetails={handleViewJobDetails}
                onViewCandidates={handleViewJobCandidates}
                onExportCleared={handleExportCleared}
                onEdit={
                  isVerified
                    ? handleEditJob
                    : () =>
                        showToast(
                          "Your account must be verified to edit job postings",
                          "warning"
                        )
                }
                onInviteCandidates={
                  isVerified
                    ? (job) => {
                        setSelectedJobForInvite(job);
                        setIsInviteModalOpen(true);
                      }
                    : () =>
                        showToast(
                          "Your account must be verified to invite candidates",
                          "warning"
                        )
                }
              />
            )}
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
              minCvScore={minCvScore}
              onMinCvScoreChange={setMinCvScore}
              minInterviewScore={minInterviewScore}
              onMinInterviewScoreChange={setMinInterviewScore}
              minProctoringScore={minProctoringScore}
              onMinProctoringScoreChange={setMinProctoringScore}
              sortBy={sortBy}
              onSortByChange={setSortBy}
            />
            {applicationsLoading && applications.length === 0 ? (
              <div className={styles.candidatesTable}>
                {Array.from({ length: 4 }).map((_, i) => (
                  <SkeletonCard key={i} variant="job" />
                ))}
              </div>
            ) : (
              <CandidatesList
                applications={getFilteredCandidates()}
                totalCount={applications.length}
                selectedPosition={selectedPosition}
                selectedStatus={selectedStatus}
                onClear={handleClearFilters}
                displayStatus={displayStatus}
                updateApplicationStatus={handleUpdateApplicationStatus}
                viewInterviewReport={viewInterviewReport}
                viewProctoringReport={viewProctoringReport}
              />
            )}
          </div>
        )}

        {activeTab === "profile" && (
          <div className={styles.profileContent}>
            <SectionHeader
              title="Company Profile"
              actions={
                !isEditingProfile ? (
                  <button
                    className={styles.primaryButton}
                    onClick={handleEditProfile}
                  >
                    <i className="fa fa-edit"></i> Edit Profile
                  </button>
                ) : (
                  <span style={{ color: "#4a90e2", fontWeight: 500 }}>
                    <i className="fa fa-edit"></i> Editing Mode
                  </span>
                )
              }
            />
            <ProfileForm
              companyProfile={companyProfile}
              isEditing={isEditingProfile}
              onChange={setCompanyProfile}
              onSave={handleSaveProfile}
              onCancel={handleCancelEdit}
              onDeleteAccount={() => setIsDeleteModalOpen(true)}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default RecruiterDashboard;

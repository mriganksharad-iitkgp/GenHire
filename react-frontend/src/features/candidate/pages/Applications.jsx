import React, { useCallback, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import PortalPageHeader from "shared/components/ui/PortalPageHeader";
import Toast from "shared/components/ui/Toast";
import SkeletonCard from "shared/components/ui/SkeletonCard";
import ApplicationsList from "features/candidate/components/ApplicationsList";
import useCandidateApplications from "features/candidate/hooks/useCandidateApplications";
import useCVPreview from "features/candidate/hooks/useCVPreview";
import InterviewReportModal from "features/interview/components/InterviewReportModal";
import KioskLaunchGuide, { openKiosk } from "features/interview/components/KioskLaunchGuide";
import { getToken } from "shared/utils/session";
import styles from "./Profile.module.css";

export default function Applications() {
  const navigate = useNavigate();
  const [toast, setToast] = useState(null);
  const showToast = useCallback((message, type = "info") => setToast({ message, type }), []);
  const { applications, companies, loading, error, load, openReport } = useCandidateApplications(showToast);
  const [filters, setFilters] = useState({ company:"", status:"", jobType:"", location:"", dateRange:"" });
  const [report, setReport] = useState(null);
  const [reportScores, setReportScores] = useState({ cv:null, interview:null });
  const [launchApplication, setLaunchApplication] = useState(null);
  const { viewCV, preview } = useCVPreview();
  const locations = useMemo(() => [...new Set(applications.map(app => app.location).filter(Boolean))].sort(), [applications]);
  const setFilter = key => value => setFilters(prev => ({ ...prev, [key]:value }));
  const viewReport = async app => {
    const result = await openReport(app);
    if (!result) return;
    setReportScores({ cv:app.cvScore, interview:app.interviewScore ?? result.final_score }); setReport(result);
  };
  const giveInterview = app => {
    if (window.electronAPI) navigate("/interviews/start", { state:{ applicationId:app.id } });
    else setLaunchApplication(app);
  };
  return <div className={styles.profileContainer}><div className={styles.pageContent}>
    <PortalPageHeader title="My Applications" eyebrow="Your opportunities" icon="fa-file-text-o" subtitle="Track your progress, take shortlisted interviews and review your results in one place." actions={<><button className={styles.ghostButton} onClick={() => load(true)} disabled={loading} aria-label="Refresh applications"><i className={`fa fa-refresh ${loading ? "fa-spin" : ""}`} aria-hidden="true" />{loading ? "Refreshing..." : "Refresh"}</button><Link to="/dashboard">Explore jobs <i className="fa fa-arrow-right" aria-hidden="true" /></Link></>} />
    {error && <div className={styles.loadingState} role="alert"><p>{error}{applications.length > 0 && " Your previously loaded applications are shown below."}</p><button className={styles.primaryButton} onClick={() => load(true)} disabled={loading}>Retry</button></div>}
    {loading && !applications.length ? <div aria-label="Loading applications" role="status">{Array.from({length:3}, (_,i) => <SkeletonCard key={i} variant="job" />)}</div> : (!error || applications.length > 0) && <ApplicationsList
      applications={applications} companies={companies} locations={locations}
      companyFilter={filters.company} statusFilter={filters.status} jobTypeFilter={filters.jobType} locationFilter={filters.location} dateRangeFilter={filters.dateRange}
      setCompanyFilter={setFilter("company")} setStatusFilter={setFilter("status")} setJobTypeFilter={setFilter("jobType")} setLocationFilter={setFilter("location")} setDateRangeFilter={setFilter("dateRange")}
      onClearFilters={() => setFilters({company:"",status:"",jobType:"",location:"",dateRange:""})}
      onViewCV={viewCV} onOpenReport={viewReport} onGiveInterview={giveInterview} />}
  </div>{preview}
    <InterviewReportModal isOpen={!!report} onClose={() => setReport(null)} report={report} cvScore={reportScores.cv} interviewScore={reportScores.interview} />
    <KioskLaunchGuide isOpen={!!launchApplication} onClose={() => setLaunchApplication(null)} onOpen={() => openKiosk({ applicationId:launchApplication.id, token:getToken(), apiUrl:process.env.REACT_APP_API_URL || window.location.origin })} />
    {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
  </div>;
}

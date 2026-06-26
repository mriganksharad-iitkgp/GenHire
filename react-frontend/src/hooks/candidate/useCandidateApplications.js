import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getApplications, getInterviewReport } from "../../services/api";
import { useCandidateData } from "../../contexts/CandidateDataContext";

// Helper function to map application data
const mapApplication = (a) => {
  const mappedStatus = (a.status || "pending").replace(/\b\w/g, (c) =>
    c.toUpperCase(),
  );

  const processingStatus = a.processing_status || "completed";
  const isScoringFailed = processingStatus === "scoring_failed";
  const isScoringRetrying = processingStatus === "scoring_retrying";

  return {
    id: a._id,
    company: a.job_details?.company || "TechCorp Solutions",
    logo: a.job_details?.logo || null,
    location: a.job_details?.location || null,
    jobType: a.job_details?.type || null,
    department: a.job_details?.department || null,
    position: a.job_title || a.job_details?.title || "",
    appliedDate: a.applied_at,
    status: mappedStatus,
    processingStatus,
    scoringError: isScoringFailed,
    scoringRetrying: isScoringRetrying,
    scoringErrorMessage: a.processing_error || null,
    scoringRetryCount: a.scoring_retry_count || 0,
    cvScore:
      typeof a.cv_score === "number"
        ? Math.round(a.cv_score)
        : a.similarity_score
          ? Math.round(a.similarity_score * 100)
          : null,
    interviewScore:
      typeof a.interview_score === "number"
        ? Math.round(a.interview_score)
        : null,
    proctoringScore:
      typeof a.proctoring_score === "number"
        ? Math.round(a.proctoring_score)
        : null,
    reportAvailable: !!a.report_available,
    interviews: [],
    minimum_cv_score_required: a.minimum_cv_score_required || null,
    auto_processed: a.auto_processed || false,
  };
};

export default function useCandidateApplications(toast) {
  const {
    applications: cachedApplications,
    loadApplicationsCached,
    applicationsLoaded,
  } = useCandidateData();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(false);
  const toastRef = useRef(toast);

  // Keep latest toast in a ref without causing effect churn
  useEffect(() => {
    toastRef.current = toast;
  }, [toast]);

  const inflightRef = useRef(false);
  const lastLoadAtRef = useRef(0);

  const load = useCallback(
    async (force = false) => {
      // Throttle to at most once per 500ms and avoid parallel calls
      const now = Date.now();
      if (
        !force &&
        (inflightRef.current || now - lastLoadAtRef.current < 500)
      ) {
        return;
      }
      inflightRef.current = true;
      lastLoadAtRef.current = now;
      setLoading(true);

      try {
        // Use cached data from context
        const apps = await loadApplicationsCached(force, async () => {
          const rawApps = await getApplications();
          return rawApps;
        });

        const mapped = (apps || []).map(mapApplication);
        setApplications(mapped);
      } catch (e) {
        toastRef.current?.("Failed to load applications", "error");
      } finally {
        setLoading(false);
        inflightRef.current = false;
      }
    },
    [loadApplicationsCached],
  );

  useEffect(() => {
    // Only load if not already cached
    if (!applicationsLoaded) {
      load();
    } else {
      console.log("📦 Using cached applications from context");
      // Use cached data immediately
      const mapped = (cachedApplications || []).map(mapApplication);
      setApplications(mapped);
    }
  }, [load, applicationsLoaded, cachedApplications]);

  // Poll for updates when there are pending/processing/retrying applications
  // Cap at 2 minutes (24 polls × 5s) to avoid infinite polling
  const pollCountRef = useRef(0);
  const MAX_POLLS = 24;

  useEffect(() => {
    const hasPending = applications.some(
      (a) =>
        a.processingStatus === "pending" ||
        a.processingStatus === "processing" ||
        a.processingStatus === "scoring_retrying",
    );
    if (!hasPending) {
      pollCountRef.current = 0;
      return;
    }

    const interval = setInterval(() => {
      if (pollCountRef.current >= MAX_POLLS) {
        clearInterval(interval);
        return;
      }
      if (document.visibilityState === 'visible') {
        pollCountRef.current += 1;
        load(true); // force reload from API
      }
    }, 5000); // poll every 5 seconds

    return () => clearInterval(interval);
  }, [applications, load]);

  const openReport = useCallback(async (app) => {
    try {
      const report = await getInterviewReport(app.id);
      return report;
    } catch (e) {
      toastRef.current?.("Report not available yet.", "error");
      return null;
    }
  }, []);

  const companies = useMemo(
    () => Array.from(new Set(applications.map((a) => a.company))).sort(),
    [applications],
  );

  return { applications, loading, load, openReport, companies };
}

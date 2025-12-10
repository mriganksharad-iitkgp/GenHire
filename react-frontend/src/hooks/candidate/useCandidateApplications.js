import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getApplications, getInterviewReport } from "../../services/api";
import { useCandidateData } from "../../contexts/CandidateDataContext";

// Helper function to map application data
const mapApplication = (a) => {
  const mappedStatus = (a.status || "pending").replace(/\b\w/g, (c) =>
    c.toUpperCase()
  );

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
    [loadApplicationsCached]
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
    [applications]
  );

  return { applications, loading, load, openReport, companies };
}

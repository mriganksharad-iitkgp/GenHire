import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getApplications,
  getInterviewReport,
  setApplicationStatus,
} from "../services/api";
import useRealtimeApplications from "./useRealtimeApplications";

export default function useApplications(toast) {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getApplications();
      setApplications(data);
    } catch (e) {
      toast?.("Failed to load applications", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  // Live updates (new applicant, candidate-side status echo, interview score
  // landing) patch this list directly — a recruiter no longer has to trigger
  // a reload themselves to see something another actor (the candidate) did.
  useRealtimeApplications(
    useCallback((_type, application) => {
      if (!application || !application._id) return;
      setApplications((current) => {
        const idx = current.findIndex(
          (a) => String(a._id) === String(application._id),
        );
        if (idx === -1) return [application, ...current];
        return current.map((a, i) =>
          i === idx ? { ...a, ...application } : a,
        );
      });
    }, []),
  );

  const updateStatus = useCallback(
    async (applicationId, newStatus) => {
      try {
        await setApplicationStatus(applicationId, newStatus);
        await load();
        toast?.("Application status updated successfully", "success");
        return true;
      } catch (e) {
        toast?.("Failed to update application status", "error");
        return false;
      }
    },
    [load, toast]
  );

  const fetchInterviewReport = useCallback(
    async (applicationId) => {
      try {
        const report = await getInterviewReport(applicationId);
        return report;
      } catch (e) {
        toast?.(e.message || "Report not available", "warning");
        return null;
      }
    },
    [toast]
  );

  const total = useMemo(() => applications.length, [applications]);

  return {
    applications,
    loading,
    load,
    updateStatus,
    fetchInterviewReport,
    total,
  };
}

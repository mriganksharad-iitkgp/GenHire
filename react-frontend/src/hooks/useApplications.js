import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getApplications,
  getInterviewReport,
  setApplicationStatus,
} from "../services/api";

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

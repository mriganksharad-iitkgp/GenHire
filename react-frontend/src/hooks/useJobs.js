import { useCallback, useEffect, useMemo, useState } from "react";
import { createJob, deleteJob, getJobs, updateJob } from "../services/api";

function normalizeJobPayload(jobData) {
  return {
    ...jobData,
    skills: Array.isArray(jobData.skills)
      ? jobData.skills
      : String(jobData.skills || "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
    responsibilities: Array.isArray(jobData.responsibilities)
      ? jobData.responsibilities
      : String(jobData.responsibilities || "")
          .replace(/\r/g, "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
    requirements: Array.isArray(jobData.requirements)
      ? jobData.requirements
      : String(jobData.requirements || "")
          .replace(/\r/g, "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
    benefits: Array.isArray(jobData.benefits)
      ? jobData.benefits
      : String(jobData.benefits || "")
          .replace(/\r/g, "")
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
  };
}

export default function useJobs(toast) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getJobs();
      setJobs(data);
    } catch (e) {
      toast?.("Failed to load jobs", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const create = useCallback(
    async (jobData, jdFile) => {
      try {
        const payload = normalizeJobPayload(jobData);
        const res = await createJob(payload, jdFile);
        setJobs((prev) => [...prev, res.job ?? res]);
        toast?.("Job created successfully!", "success");
        return true;
      } catch (e) {
        toast?.(e.message || "Failed to create job", "error");
        return false;
      }
    },
    [toast]
  );

  const update = useCallback(
    async (jobId, jobData) => {
      try {
        const payload = normalizeJobPayload(jobData);
        await updateJob(jobId, payload);
        setJobs((prev) =>
          prev.map((j) =>
            String(j._id) === String(jobId) ? { ...j, ...payload } : j
          )
        );
        toast?.("Job updated successfully!", "success");
        return true;
      } catch (e) {
        toast?.(e.message || "Failed to update job", "error");
        return false;
      }
    },
    [toast]
  );

  const remove = useCallback(
    async (jobId) => {
      try {
        await deleteJob(jobId);
        setJobs((prev) => prev.filter((j) => String(j._id) !== String(jobId)));
        toast?.("Job deleted successfully!", "success");
        return true;
      } catch (e) {
        toast?.(e.message || "Failed to delete job", "error");
        return false;
      }
    },
    [toast]
  );

  const activeCount = useMemo(
    () =>
      jobs.filter((job) => String(job.status || "").toLowerCase() === "active")
        .length,
    [jobs]
  );

  return { jobs, loading, load, create, update, remove, activeCount };
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getSavedJobs, saveJob, unsaveJob } from "shared/api/endpoints";

/**
 * Candidate job bookmarks.
 *
 * Toggling is optimistic — the bookmark icon flips immediately and rolls back
 * if the request fails, so a save never feels like it did nothing while the
 * round trip is in flight (the old Save button genuinely did nothing, which is
 * the bug this replaces).
 *
 * @param {object} options
 *   enabled - skip all network calls when false (recruiters, logged-out views).
 *             The backend rejects non-candidates with 403, and invite-only
 *             burner accounts too; either way the feature simply stays hidden.
 */
export default function useSavedJobs({ enabled = true } = {}) {
  const [savedJobs, setSavedJobs] = useState([]);
  const [savedIds, setSavedIds] = useState(() => new Set());
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);
  const [pendingIds, setPendingIds] = useState(() => new Set());
  const [available, setAvailable] = useState(true);

  // Guards against setState after unmount when a slow request resolves late.
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return [];
    }
    setLoading(true);
    try {
      const data = await getSavedJobs();
      const list = data?.saved_jobs || [];
      if (!mountedRef.current) return list;
      setSavedJobs(list);
      setSavedIds(new Set(list.map((job) => String(job._id))));
      setError(null);
      setAvailable(true);
      return list;
    } catch (err) {
      if (!mountedRef.current) return [];
      // 403 = this account type has no saved-jobs list. Not an error to show.
      if (err?.status === 403) {
        setAvailable(false);
        setSavedJobs([]);
        setSavedIds(new Set());
        setError(null);
      } else {
        setError(err?.message || "Could not load your saved jobs");
      }
      return [];
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const isSaved = useCallback(
    (jobId) => savedIds.has(String(jobId)),
    [savedIds]
  );

  const isPending = useCallback(
    (jobId) => pendingIds.has(String(jobId)),
    [pendingIds]
  );

  const markPending = useCallback((jobId, pending) => {
    setPendingIds((prev) => {
      const next = new Set(prev);
      if (pending) next.add(String(jobId));
      else next.delete(String(jobId));
      return next;
    });
  }, []);

  /**
   * Save or unsave a job. Resolves to the new saved state (true = saved) so
   * callers can show the right toast, or null when the call failed.
   */
  const toggleSave = useCallback(
    async (jobId, jobForCache = null) => {
      const id = String(jobId);
      if (!enabled || !available || pendingIds.has(id)) return null;

      const wasSaved = savedIds.has(id);
      const nextSaved = !wasSaved;

      // Optimistic flip.
      setSavedIds((prev) => {
        const next = new Set(prev);
        if (nextSaved) next.add(id);
        else next.delete(id);
        return next;
      });
      setSavedJobs((prev) =>
        nextSaved
          ? jobForCache && !prev.some((j) => String(j._id) === id)
            ? [{ ...jobForCache, _id: id, saved_at: new Date().toISOString() }, ...prev]
            : prev
          : prev.filter((j) => String(j._id) !== id)
      );
      markPending(id, true);

      try {
        if (nextSaved) await saveJob(id);
        else await unsaveJob(id);
        // Re-sync so the card carries server-side fields (has_applied,
        // can_apply, resolved company) rather than the optimistic stub.
        if (nextSaved) refresh();
        return nextSaved;
      } catch (err) {
        if (!mountedRef.current) return null;
        // Roll the optimistic flip back — the bookmark did not persist.
        setSavedIds((prev) => {
          const next = new Set(prev);
          if (wasSaved) next.add(id);
          else next.delete(id);
          return next;
        });
        refresh();
        setError(err?.message || "Could not update your saved jobs");
        return null;
      } finally {
        if (mountedRef.current) markPending(id, false);
      }
    },
    [enabled, available, pendingIds, savedIds, markPending, refresh]
  );

  const savedCount = useMemo(() => savedIds.size, [savedIds]);

  return {
    savedJobs,
    savedIds,
    savedCount,
    loading,
    error,
    available,
    isSaved,
    isPending,
    toggleSave,
    refresh,
    clearError: () => setError(null),
  };
}

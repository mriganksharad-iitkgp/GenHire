import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

/**
 * Global data cache for candidate pages to prevent unnecessary reloads.
 *
 * ARCHITECTURE NOTE — why useRef for callbacks:
 * The original implementation put state variables (jobs, cvs, etc.) in
 * useCallback dependency arrays. This caused an infinite loop:
 *   state update -> new callback reference -> child useCallback recreated
 *   -> child useEffect fires -> API call -> state update -> repeat.
 * This produced 10+ /api/cv/list calls per second.
 *
 * Fix: keep "mirror" refs that always hold the latest state value.
 * Callbacks read from refs (stable references), so they never need to be
 * recreated. State setters update both the React state (for re-renders)
 * and the ref (for synchronous reads inside callbacks).
 */

const CandidateDataContext = createContext(null);
const CACHE_EXPIRY_MS = 5 * 60 * 1000;

export const CandidateDataProvider = ({ children }) => {
  // ── Jobs ──────────────────────────────────────────────────────────────────
  const [jobs, setJobs] = useState([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(false);
  const jobsLoadTimeRef = useRef(0);
  const jobsRef = useRef([]);
  const jobsLoadedRef = useRef(false);
  const jobsLoadingRef = useRef(false);

  // ── Applications ──────────────────────────────────────────────────────────
  const [applications, setApplications] = useState([]);
  const [applicationsLoaded, setApplicationsLoaded] = useState(false);
  const [applicationsLoading, setApplicationsLoading] = useState(false);
  const applicationsLoadTimeRef = useRef(0);
  const applicationsRef = useRef([]);
  const applicationsLoadedRef = useRef(false);
  const applicationsLoadingRef = useRef(false);

  // ── CVs ───────────────────────────────────────────────────────────────────
  const [cvs, setCvs] = useState([]);
  const [cvsLoaded, setCvsLoaded] = useState(false);
  const [cvsLoading, setCvsLoading] = useState(false);
  const cvsLoadTimeRef = useRef(0);
  const cvsRef = useRef([]);
  const cvsLoadedRef = useRef(false);
  const cvsLoadingRef = useRef(false);

  // ── Profile ───────────────────────────────────────────────────────────────
  const [profile, setProfile] = useState(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const profileLoadTimeRef = useRef(0);
  const profileRef = useRef(null);
  const profileLoadedRef = useRef(false);
  const profileLoadingRef = useRef(false);

  // ── Synced setters (update both React state AND the ref) ──────────────────
  const _setJobs = (v) => { jobsRef.current = v; setJobs(v); };
  const _setJobsLoaded = (v) => { jobsLoadedRef.current = v; setJobsLoaded(v); };
  const _setJobsLoading = (v) => { jobsLoadingRef.current = v; setJobsLoading(v); };
  const _setApplications = (v) => { applicationsRef.current = v; setApplications(v); };
  const _setApplicationsLoaded = (v) => { applicationsLoadedRef.current = v; setApplicationsLoaded(v); };
  const _setApplicationsLoading = (v) => { applicationsLoadingRef.current = v; setApplicationsLoading(v); };
  const _setCvs = (v) => { cvsRef.current = v; setCvs(v); };
  const _setCvsLoaded = (v) => { cvsLoadedRef.current = v; setCvsLoaded(v); };
  const _setCvsLoading = (v) => { cvsLoadingRef.current = v; setCvsLoading(v); };
  const _setProfile = (v) => { profileRef.current = v; setProfile(v); };
  const _setProfileLoaded = (v) => { profileLoadedRef.current = v; setProfileLoaded(v); };
  const _setProfileLoading = (v) => { profileLoadingRef.current = v; setProfileLoading(v); };

  // ── Stable load callbacks (empty dep array — state read via refs) ──────────

  const loadJobsCached = useCallback(async (force, loadFn) => {
    const now = Date.now();
    const cacheAge = now - jobsLoadTimeRef.current;
    if (!force && jobsLoadedRef.current && cacheAge < CACHE_EXPIRY_MS && !jobsLoadingRef.current) {
      return jobsRef.current;
    }
    if (jobsLoadingRef.current) return jobsRef.current;
    _setJobsLoading(true);
    try {
      const loadedJobs = await loadFn();
      _setJobs(loadedJobs);
      _setJobsLoaded(true);
      jobsLoadTimeRef.current = Date.now();
      return loadedJobs;
    } catch (error) {
      console.error('Error loading jobs:', error);
      throw error;
    } finally {
      _setJobsLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadApplicationsCached = useCallback(async (force, loadFn) => {
    const now = Date.now();
    const cacheAge = now - applicationsLoadTimeRef.current;
    if (!force && applicationsLoadedRef.current && cacheAge < CACHE_EXPIRY_MS && !applicationsLoadingRef.current) {
      return applicationsRef.current;
    }
    if (applicationsLoadingRef.current) return applicationsRef.current;
    _setApplicationsLoading(true);
    try {
      const loadedApps = await loadFn();
      _setApplications(loadedApps);
      _setApplicationsLoaded(true);
      applicationsLoadTimeRef.current = Date.now();
      return loadedApps;
    } catch (error) {
      console.error('Error loading applications:', error);
      throw error;
    } finally {
      _setApplicationsLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * loadCvsCached — STABLE callback, never recreated after mount.
   * Previously had [cvs, cvsLoaded, cvsLoading] in deps which caused
   * state updates to recreate this fn -> children's fetchCVs also
   * recreated -> useEffect fired -> API call -> infinite loop.
   */
  const loadCvsCached = useCallback(async (force, loadFn) => {
    const now = Date.now();
    const cacheAge = now - cvsLoadTimeRef.current;
    if (!force && cvsLoadedRef.current && cacheAge < CACHE_EXPIRY_MS && !cvsLoadingRef.current) {
      return cvsRef.current;
    }
    if (cvsLoadingRef.current) return cvsRef.current;
    _setCvsLoading(true);
    try {
      const loadedCvs = await loadFn();
      _setCvs(loadedCvs);
      _setCvsLoaded(true);
      cvsLoadTimeRef.current = Date.now();
      return loadedCvs;
    } catch (error) {
      console.error('Error loading CVs:', error);
      throw error;
    } finally {
      _setCvsLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadProfileCached = useCallback(async (force, loadFn) => {
    const now = Date.now();
    const cacheAge = now - profileLoadTimeRef.current;
    if (!force && profileLoadedRef.current && cacheAge < CACHE_EXPIRY_MS && !profileLoadingRef.current) {
      return profileRef.current;
    }
    if (profileLoadingRef.current) return profileRef.current;
    _setProfileLoading(true);
    try {
      const loadedProfile = await loadFn();
      _setProfile(loadedProfile);
      _setProfileLoaded(true);
      profileLoadTimeRef.current = Date.now();
      return loadedProfile;
    } catch (error) {
      console.error('Error loading profile:', error);
      throw error;
    } finally {
      _setProfileLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const updateCachedProfile = useCallback((updater) => {
    setProfile(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      if (next) {
        _setProfileLoaded(true);
        profileLoadTimeRef.current = Date.now();
      }
      return next;
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Invalidators ──────────────────────────────────────────────────────────

  const invalidateJobs = useCallback(() => {
    _setJobsLoaded(false);
    jobsLoadTimeRef.current = 0;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const invalidateApplications = useCallback(() => {
    _setApplicationsLoaded(false);
    applicationsLoadTimeRef.current = 0;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const invalidateCvs = useCallback(() => {
    _setCvsLoaded(false);
    cvsLoadTimeRef.current = 0;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const invalidateProfile = useCallback(() => {
    _setProfileLoaded(false);
    profileLoadTimeRef.current = 0;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const clearAllCaches = useCallback(() => {
    _setJobsLoaded(false);
    _setApplicationsLoaded(false);
    _setCvsLoaded(false);
    _setProfileLoaded(false);
    jobsLoadTimeRef.current = 0;
    applicationsLoadTimeRef.current = 0;
    cvsLoadTimeRef.current = 0;
    profileLoadTimeRef.current = 0;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const value = {
    // Jobs
    jobs,
    jobsLoaded,
    jobsLoading,
    loadJobsCached,
    invalidateJobs,

    // Applications
    applications,
    applicationsLoaded,
    applicationsLoading,
    loadApplicationsCached,
    invalidateApplications,

    // CVs
    cvs,
    cvsLoaded,
    cvsLoading,
    loadCvsCached,
    invalidateCvs,

    // Profile
    profile,
    profileLoaded,
    profileLoading,
    loadProfileCached,
    updateCachedProfile,
    invalidateProfile,

    // Global
    clearAllCaches,
  };

  return (
    <CandidateDataContext.Provider value={value}>
      {children}
    </CandidateDataContext.Provider>
  );
};

/**
 * Hook to use candidate data context
 */
export const useCandidateData = () => {
  const context = useContext(CandidateDataContext);
  if (!context) {
    throw new Error('useCandidateData must be used within CandidateDataProvider');
  }
  return context;
};

import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { viewPhoto } from '../services/api';
import { getToken } from '../utils/sessionManager';

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
  const jobsPromiseRef = useRef(null);

  // ── Applications ──────────────────────────────────────────────────────────
  const [applications, setApplications] = useState([]);
  const [applicationsLoaded, setApplicationsLoaded] = useState(false);
  const [applicationsLoading, setApplicationsLoading] = useState(false);
  const applicationsLoadTimeRef = useRef(0);
  const applicationsRef = useRef([]);
  const applicationsLoadedRef = useRef(false);
  const applicationsLoadingRef = useRef(false);
  const applicationsPromiseRef = useRef(null);

  // ── CVs ───────────────────────────────────────────────────────────────────
  const [cvs, setCvs] = useState([]);
  const [cvsLoaded, setCvsLoaded] = useState(false);
  const [cvsLoading, setCvsLoading] = useState(false);
  const cvsLoadTimeRef = useRef(0);
  const cvsRef = useRef([]);
  const cvsLoadedRef = useRef(false);
  const cvsLoadingRef = useRef(false);
  const cvsPromiseRef = useRef(null);

  // ── Profile ───────────────────────────────────────────────────────────────
  const [profile, setProfile] = useState(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const profileLoadTimeRef = useRef(0);
  const profileRef = useRef(null);
  const profileLoadedRef = useRef(false);
  const profileLoadingRef = useRef(false);
  const profilePromiseRef = useRef(null);

  // ── Profile Photo ─────────────────────────────────────────────────────────
  const [profilePhotoUrl, setProfilePhotoUrl] = useState(null);
  const profilePhotoUrlRef = useRef(null);
  const photoPromiseRef = useRef(null);

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
  const _setProfilePhotoUrl = (url) => { profilePhotoUrlRef.current = url; setProfilePhotoUrl(url); };

  const lastTokenRef = useRef(getToken());

  const checkTokenAndClearIfChanged = useCallback(() => {
    const token = getToken();
    if (token !== lastTokenRef.current) {
      console.log("🔑 Token changed, clearing all context caches.");
      lastTokenRef.current = token;
      _setJobs([]);
      _setJobsLoaded(false);
      _setJobsLoading(false);
      _setApplications([]);
      _setApplicationsLoaded(false);
      _setApplicationsLoading(false);
      _setCvs([]);
      _setCvsLoaded(false);
      _setCvsLoading(false);
      _setProfile(null);
      _setProfileLoaded(false);
      _setProfileLoading(false);
      _setProfilePhotoUrl(null);
      jobsLoadTimeRef.current = 0;
      applicationsLoadTimeRef.current = 0;
      cvsLoadTimeRef.current = 0;
      profileLoadTimeRef.current = 0;
      jobsPromiseRef.current = null;
      applicationsPromiseRef.current = null;
      cvsPromiseRef.current = null;
      profilePromiseRef.current = null;
      photoPromiseRef.current = null;
      return true;
    }
    return false;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stable load callbacks (empty dep array — state read via refs) ──────────

  const loadJobsCached = useCallback(async (force, loadFn) => {
    checkTokenAndClearIfChanged();
    const now = Date.now();
    const cacheAge = now - jobsLoadTimeRef.current;
    if (!force && jobsLoadedRef.current && cacheAge < CACHE_EXPIRY_MS) {
      return jobsRef.current;
    }
    if (jobsPromiseRef.current) {
      return jobsPromiseRef.current;
    }

    const promise = (async () => {
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
        jobsPromiseRef.current = null;
      }
    })();

    jobsPromiseRef.current = promise;
    return promise;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadApplicationsCached = useCallback(async (force, loadFn) => {
    checkTokenAndClearIfChanged();
    const now = Date.now();
    const cacheAge = now - applicationsLoadTimeRef.current;
    if (!force && applicationsLoadedRef.current && cacheAge < CACHE_EXPIRY_MS) {
      return applicationsRef.current;
    }
    if (applicationsPromiseRef.current) {
      return applicationsPromiseRef.current;
    }

    const promise = (async () => {
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
        applicationsPromiseRef.current = null;
      }
    })();

    applicationsPromiseRef.current = promise;
    return promise;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * loadCvsCached — STABLE callback, never recreated after mount.
   * Previously had [cvs, cvsLoaded, cvsLoading] in deps which caused
   * state updates to recreate this fn -> children's fetchCVs also
   * recreated -> useEffect fired -> API call -> infinite loop.
   */
  const loadCvsCached = useCallback(async (force, loadFn) => {
    checkTokenAndClearIfChanged();
    const now = Date.now();
    const cacheAge = now - cvsLoadTimeRef.current;
    if (!force && cvsLoadedRef.current && cacheAge < CACHE_EXPIRY_MS) {
      return cvsRef.current;
    }
    if (cvsPromiseRef.current) {
      return cvsPromiseRef.current;
    }

    const promise = (async () => {
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
        cvsPromiseRef.current = null;
      }
    })();

    cvsPromiseRef.current = promise;
    return promise;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadProfilePhoto = useCallback(async (force = false) => {
    const token = getToken();
    if (!token) return null;
    
    // Instead of fetching a blob which fails on GCS redirects, we construct the direct URL
    const url = `${process.env.REACT_APP_API_URL || ''}/api/view-photo?token=${token}&t=${Date.now()}`;
    _setProfilePhotoUrl(url);
    return url;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadProfileCached = useCallback(async (force, loadFn) => {
    checkTokenAndClearIfChanged();
    const now = Date.now();
    const cacheAge = now - profileLoadTimeRef.current;
    if (!force && profileLoadedRef.current && cacheAge < CACHE_EXPIRY_MS) {
      return profileRef.current;
    }
    if (profilePromiseRef.current) {
      return profilePromiseRef.current;
    }

    const promise = (async () => {
      _setProfileLoading(true);
      try {
        const loadedProfile = await loadFn();
        _setProfile(loadedProfile);
        _setProfileLoaded(true);
        profileLoadTimeRef.current = Date.now();

        if (loadedProfile && loadedProfile.profile_photo) {
          loadProfilePhoto(force);
        } else {
          _setProfilePhotoUrl(null);
        }

        return loadedProfile;
      } catch (error) {
        console.error('Error loading profile:', error);
        throw error;
      } finally {
        _setProfileLoading(false);
        profilePromiseRef.current = null;
      }
    })();

    profilePromiseRef.current = promise;
    return promise;
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
    _setJobs([]);
    _setJobsLoaded(false);
    _setJobsLoading(false);
    _setApplications([]);
    _setApplicationsLoaded(false);
    _setApplicationsLoading(false);
    _setCvs([]);
    _setCvsLoaded(false);
    _setCvsLoading(false);
    _setProfile(null);
    _setProfileLoaded(false);
    _setProfileLoading(false);
    _setProfilePhotoUrl(null);
    jobsLoadTimeRef.current = 0;
    applicationsLoadTimeRef.current = 0;
    cvsLoadTimeRef.current = 0;
    profileLoadTimeRef.current = 0;
    jobsPromiseRef.current = null;
    applicationsPromiseRef.current = null;
    cvsPromiseRef.current = null;
    profilePromiseRef.current = null;
    photoPromiseRef.current = null;
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
    profilePhotoUrl,
    loadProfilePhoto,

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

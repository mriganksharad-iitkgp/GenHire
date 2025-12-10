import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

/**
 * Global data cache for candidate pages to prevent unnecessary reloads
 * when switching between Dashboard (Open Positions) and Profile (My Applications)
 * 
 * This context stores jobs and applications data globally, so they persist
 * across route changes and component unmounts/remounts.
 */

const CandidateDataContext = createContext(null);

export const CandidateDataProvider = ({ children }) => {
  // Jobs data (from Dashboard)
  const [jobs, setJobs] = useState([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(false);
  const jobsLoadTimeRef = useRef(0);
  
  // Applications data (from Profile)
  const [applications, setApplications] = useState([]);
  const [applicationsLoaded, setApplicationsLoaded] = useState(false);
  const [applicationsLoading, setApplicationsLoading] = useState(false);
  const applicationsLoadTimeRef = useRef(0);
  
  // CVs data (from CV modal)
  const [cvs, setCvs] = useState([]);
  const [cvsLoaded, setCvsLoaded] = useState(false);
  const [cvsLoading, setCvsLoading] = useState(false);
  
  // Cache expiry time (5 minutes)
  const CACHE_EXPIRY_MS = 5 * 60 * 1000;
  
  /**
   * Load jobs with caching
   * @param {boolean} force - Force reload even if cache is valid
   * @param {function} loadFn - Function that loads jobs from API
   */
  const loadJobsCached = useCallback(async (force, loadFn) => {
    const now = Date.now();
    const cacheAge = now - jobsLoadTimeRef.current;
    
    // Return cached data if valid and not forcing
    if (!force && jobsLoaded && cacheAge < CACHE_EXPIRY_MS && !jobsLoading) {
      console.log('📦 Using cached jobs data (age:', Math.round(cacheAge / 1000), 'seconds)');
      return jobs;
    }
    
    // Don't reload if already loading
    if (jobsLoading) {
      console.log('⏳ Jobs already loading, skipping...');
      return jobs;
    }
    
    console.log('🔄 Loading jobs from API...');
    setJobsLoading(true);
    
    try {
      const loadedJobs = await loadFn();
      setJobs(loadedJobs);
      setJobsLoaded(true);
      jobsLoadTimeRef.current = Date.now();
      return loadedJobs;
    } catch (error) {
      console.error('Error loading jobs:', error);
      throw error;
    } finally {
      setJobsLoading(false);
    }
  }, [jobs, jobsLoaded, jobsLoading]);
  
  /**
   * Load applications with caching
   * @param {boolean} force - Force reload even if cache is valid
   * @param {function} loadFn - Function that loads applications from API
   */
  const loadApplicationsCached = useCallback(async (force, loadFn) => {
    const now = Date.now();
    const cacheAge = now - applicationsLoadTimeRef.current;
    
    // Return cached data if valid and not forcing
    if (!force && applicationsLoaded && cacheAge < CACHE_EXPIRY_MS && !applicationsLoading) {
      console.log('📦 Using cached applications data (age:', Math.round(cacheAge / 1000), 'seconds)');
      return applications;
    }
    
    // Don't reload if already loading
    if (applicationsLoading) {
      console.log('⏳ Applications already loading, skipping...');
      return applications;
    }
    
    console.log('🔄 Loading applications from API...');
    setApplicationsLoading(true);
    
    try {
      const loadedApps = await loadFn();
      setApplications(loadedApps);
      setApplicationsLoaded(true);
      applicationsLoadTimeRef.current = Date.now();
      return loadedApps;
    } catch (error) {
      console.error('Error loading applications:', error);
      throw error;
    } finally {
      setApplicationsLoading(false);
    }
  }, [applications, applicationsLoaded, applicationsLoading]);
  
  /**
   * Load CVs with caching
   * @param {boolean} force - Force reload even if cache is valid
   * @param {function} loadFn - Function that loads CVs from API
   */
  const loadCvsCached = useCallback(async (force, loadFn) => {
    // Return cached data if valid and not forcing
    if (!force && cvsLoaded && !cvsLoading) {
      console.log('📦 Using cached CVs data');
      return cvs;
    }
    
    // Don't reload if already loading
    if (cvsLoading) {
      console.log('⏳ CVs already loading, skipping...');
      return cvs;
    }
    
    console.log('🔄 Loading CVs from API...');
    setCvsLoading(true);
    
    try {
      const loadedCvs = await loadFn();
      setCvs(loadedCvs);
      setCvsLoaded(true);
      return loadedCvs;
    } catch (error) {
      console.error('Error loading CVs:', error);
      throw error;
    } finally {
      setCvsLoading(false);
    }
  }, [cvs, cvsLoaded, cvsLoading]);
  
  /**
   * Invalidate jobs cache (use after applying to a job)
   */
  const invalidateJobs = useCallback(() => {
    console.log('🗑️ Invalidating jobs cache');
    setJobsLoaded(false);
    jobsLoadTimeRef.current = 0;
  }, []);
  
  /**
   * Invalidate applications cache (use after interview completion, withdrawal, etc.)
   */
  const invalidateApplications = useCallback(() => {
    console.log('🗑️ Invalidating applications cache');
    setApplicationsLoaded(false);
    applicationsLoadTimeRef.current = 0;
  }, []);
  
  /**
   * Invalidate CVs cache (use after uploading a new CV)
   */
  const invalidateCvs = useCallback(() => {
    console.log('🗑️ Invalidating CVs cache');
    setCvsLoaded(false);
  }, []);
  
  /**
   * Clear all caches
   */
  const clearAllCaches = useCallback(() => {
    console.log('🗑️ Clearing all caches');
    setJobsLoaded(false);
    setApplicationsLoaded(false);
    setCvsLoaded(false);
    jobsLoadTimeRef.current = 0;
    applicationsLoadTimeRef.current = 0;
  }, []);
  
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
    
    // Global
    clearAllCaches
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

import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";

/**
 * Authentication hook for managing user sessions.
 *
 * Uses sessionStorage (via sessionManager) so each browser tab maintains
 * its own independent session — no cross-tab overwrites on login/refresh.
 *
 * @param {string|null} requiredType - Required user type ('candidate', 'recruiter', 'admin', or null for any)
 * @returns {Object} Authentication state and helpers
 */
import { getToken, getUser, clearSession } from "shared/utils/session";

export default function useAuth(requiredType = "recruiter") {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [isVerified, setIsVerified] = useState(true);
  const [rejectionReason, setRejectionReason] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    const parsed = getUser();
    
    if (!token || !parsed) {
      setIsLoading(false);
      navigate("/login");
      return;
    }
    
    try {
      const userType = parsed.userType || parsed.user_type || 'candidate';
      
      // Check if required type matches (if specified)
      if (requiredType && userType !== requiredType) {
        setIsLoading(false);
        // Redirect based on actual user type
        if (userType === 'admin') {
          navigate("/admin");
        } else if (userType === 'recruiter') {
          navigate("/recruiter/dashboard");
        } else {
          navigate("/");
        }
        return;
      }

      // Set user data
      setUser({
        ...parsed,
        userType: userType
      });
      
      // Set verification status (relevant for recruiters)
      // Check both isVerified (frontend convention) and is_verified (backend convention)
      const verified = parsed.isVerified !== false && parsed.is_verified !== false;
      setIsVerified(verified);
      setRejectionReason(parsed.rejection_reason || null);
      
      // Set permissions
      setPermissions(parsed.permissions || []);
      
      // Store display name for convenience
      if (userType === 'recruiter') {
        sessionStorage.setItem("recruiterName", parsed.name || "Recruiter");
      }
      
      setIsLoading(false);
    } catch (error) {
      console.error('Error parsing user data:', error);
      setIsLoading(false);
      navigate("/login");
    }
  }, [navigate, requiredType]);

  /**
   * Check if user has a specific permission
   * @param {string} permission - Permission to check
   * @returns {boolean} Whether user has the permission
   */
  const hasPermission = useCallback((permission) => {
    // Super admin has all permissions
    if (permissions.includes('*')) {
      return true;
    }
    return permissions.includes(permission);
  }, [permissions]);

  /**
   * Check if user is an admin
   * @returns {boolean}
   */
  const isAdmin = useCallback(() => {
    return user?.userType === 'admin' || user?.user_type === 'admin';
  }, [user]);

  /**
   * Check if user is a recruiter
   * @returns {boolean}
   */
  const isRecruiter = useCallback(() => {
    return user?.userType === 'recruiter' || user?.user_type === 'recruiter';
  }, [user]);

  /**
   * Check if user is a candidate
   * @returns {boolean}
   */
  const isCandidate = useCallback(() => {
    return user?.userType === 'candidate' || user?.user_type === 'candidate';
  }, [user]);

  /**
   * Logout user and redirect to login page
   */
  const logout = useCallback(() => {
    clearSession();
    navigate("/login");
  }, [navigate]);

  /**
   * Refresh user data from sessionStorage (useful after profile updates)
   */
  const refreshUser = useCallback(() => {
    const parsed = getUser();
    if (parsed) {
      try {
        setUser({
          ...parsed,
          userType: parsed.userType || parsed.user_type || 'candidate'
        });
        setIsVerified(parsed.isVerified !== false && parsed.is_verified !== false);
        setRejectionReason(parsed.rejection_reason || null);
        setPermissions(parsed.permissions || []);
      } catch (error) {
        console.error('Error refreshing user data:', error);
      }
    }
  }, []);

  return { 
    user, 
    logout,
    isVerified,
    rejectionReason,
    permissions,
    hasPermission,
    isAdmin,
    isRecruiter,
    isCandidate,
    isLoading,
    refreshUser
  };
}

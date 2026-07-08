import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { CandidateDataProvider } from "contexts/CandidateDataContext";
import ErrorBoundary from "components/ErrorBoundary";

/**
 * App-wide providers (everything that wraps the router).
 * Moved out of App.jsx unchanged.
 */
export function AppProviders({ children }) {
  return (
    <GoogleOAuthProvider clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID}>
      <CandidateDataProvider>
        <ErrorBoundary>{children}</ErrorBoundary>
      </CandidateDataProvider>
    </GoogleOAuthProvider>
  );
}

/**
 * Listens for the global "auth:session-expired" event broadcast by
 * shared/api/client.js and routes to the login page. Must render inside
 * the Router (it navigates).
 */
export function SessionExpiredHandler() {
  const navigate = useNavigate();
  useEffect(() => {
    const handle = () => navigate("/login?expired=1", { replace: true });
    window.addEventListener("auth:session-expired", handle);
    return () => window.removeEventListener("auth:session-expired", handle);
  }, [navigate]);
  return null;
}

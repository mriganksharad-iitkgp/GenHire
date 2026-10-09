import React, { useState, useEffect } from "react";
import { Navigate, Outlet } from "react-router-dom";
import Navbar from "./Navbar";
import styles from "./Layout.module.css";
import { request } from "shared/api/client";
import { getToken, clearSession } from "shared/utils/session";

const Layout = () => {
  const [authenticated, setAuthenticated] = useState(null);
  const [role, setRole] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    setError("");
    const verify = async () => {
      if (!getToken()) { setAuthenticated(false); return; }
      try {
        const profile = await request("/me", { signal:controller.signal, signalOn401:false, catchNetwork:false });
        if (cancelled) return;
        if (!profile?.user_type) throw new Error("Account verification returned an incomplete response.");
        setRole(profile.user_type); setAuthenticated(true);
      } catch (failure) {
        if (cancelled) return;
        if (failure.status === 401) { clearSession(); setAuthenticated(false); }
        else setError(controller.signal.aborted ? "Account verification took too long. Please retry." : "We could not verify your account right now. Please retry.");
      } finally { clearTimeout(timeout); }
    };
    verify();
    return () => { cancelled = true; clearTimeout(timeout); controller.abort(); };
  }, [attempt]);
  if (error) return <div className={styles.loadingContainer}><section className={styles.errorPanel} role="alert"><h2>Unable to open your workspace</h2><p>{error}</p><button onClick={() => setAttempt(value => value + 1)}>Retry</button><a href="/login">Back to sign in</a></section></div>;
  if (authenticated === null) return <div className={styles.loadingContainer}><div className={styles.loadingSpinner} role="status">Opening your workspace...</div></div>;
  if (!authenticated) return <Navigate to="/login" replace />;
  if (role === "recruiter") return <Navigate to="/recruiter/dashboard" replace />;
  if (role === "admin") return <Navigate to="/admin" replace />;
  return <div className={styles.layoutContainer}><Navbar userType={role} /><main className={styles.mainContent}><Outlet /></main></div>;
};
export default Layout;

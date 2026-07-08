import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import AdminLayout from "features/admin/components/AdminLayout";
import styles from "./AdminPages.module.css";
import * as adminApi from "features/admin/api/adminApi";

const AdminOverview = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [pendingRecruiters, setPendingRecruiters] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [statsData, pendingData] = await Promise.all([
        adminApi.getStats(),
        adminApi.getPendingRecruiters(),
      ]);
      setStats(statsData);
      setPendingRecruiters(pendingData.pending_recruiters || []);
    } catch (error) {
      console.error("Error fetching data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [navigate, fetchData]);

  if (loading) {
    return (
      <AdminLayout>
        <div className={styles.loadingContainer}>
          <div className={styles.spinner}></div>
          <p>Loading dashboard...</p>
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout>
      <div className={styles.pageContainer}>
        <div className={styles.pageHeader}>
          <h1>Dashboard Overview</h1>
          <p>Monitor platform activity and manage users</p>
        </div>

        {/* Stats Grid */}
        <div className={styles.statsGrid}>
          <div className={styles.statCard} data-color="purple">
            <div className={styles.statIcon}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
              </svg>
            </div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Total Users</span>
              <span className={styles.statValue}>{stats?.users?.total || 0}</span>
              <span className={styles.statChange}>+{stats?.users?.new_this_week || 0} this week</span>
            </div>
          </div>

          <div 
            className={styles.statCard} 
            data-color="blue"
            onClick={() => navigate("/admin/candidates")}
            style={{ cursor: "pointer" }}
          >
            <div className={styles.statIcon}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
            </div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Candidates</span>
              <span className={styles.statValue}>{stats?.users?.candidates || 0}</span>
            </div>
          </div>

          <div 
            className={styles.statCard} 
            data-color="green"
            onClick={() => navigate("/admin/recruiters")}
            style={{ cursor: "pointer" }}
          >
            <div className={styles.statIcon}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
              </svg>
            </div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Recruiters</span>
              <span className={styles.statValue}>{stats?.recruiters?.verified || 0}</span>
              <span className={styles.statChange}>{stats?.recruiters?.pending_verification || 0} pending</span>
            </div>
          </div>

          <div className={styles.statCard} data-color="orange">
            <div className={styles.statIcon}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
              </svg>
            </div>
            <div className={styles.statContent}>
              <span className={styles.statLabel}>Active Jobs</span>
              <span className={styles.statValue}>{stats?.jobs?.active || 0}</span>
              <span className={styles.statChange}>{stats?.jobs?.total || 0} total</span>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className={styles.quickActionsGrid}>
          {pendingRecruiters.length > 0 && (
            <div className={styles.alertCard}>
              <div className={styles.alertIcon}>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
              </div>
              <div className={styles.alertContent}>
                <h3>Pending Verifications</h3>
                <p>{pendingRecruiters.length} recruiter{pendingRecruiters.length !== 1 ? "s" : ""} waiting for approval</p>
              </div>
              <button 
                className={styles.alertButton}
                onClick={() => navigate("/admin/verification")}
              >
                Review Now
              </button>
            </div>
          )}
        </div>

        {/* Quick Navigation Cards */}
        <div className={styles.sectionHeader}>
          <h2>Quick Navigation</h2>
        </div>
        <div className={styles.navCardsGrid}>
          <div className={styles.navCard} onClick={() => navigate("/admin/candidates")}>
            <div className={styles.navCardIcon} data-color="blue">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
            </div>
            <div className={styles.navCardContent}>
              <h3>Manage Candidates</h3>
              <p>View and manage all candidates, their applications and interview history</p>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={styles.navCardArrow}>
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </div>

          <div className={styles.navCard} onClick={() => navigate("/admin/recruiters")}>
            <div className={styles.navCardIcon} data-color="green">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
              </svg>
            </div>
            <div className={styles.navCardContent}>
              <h3>Manage Recruiters</h3>
              <p>View company profiles, job postings and recruiter statistics</p>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={styles.navCardArrow}>
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </div>

          <div className={styles.navCard} onClick={() => navigate("/admin/admins")}>
            <div className={styles.navCardIcon} data-color="purple">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
              </svg>
            </div>
            <div className={styles.navCardContent}>
              <h3>Manage Admins</h3>
              <p>View and manage administrator accounts</p>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={styles.navCardArrow}>
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};

export default AdminOverview;

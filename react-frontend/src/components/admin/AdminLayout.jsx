import React, { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import styles from "./AdminLayout.module.css";
import * as adminApi from "../../services/adminApi";

const AdminLayout = ({ children, activeTab: externalActiveTab }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [pendingCount, setPendingCount] = useState(0);
  const [adminUser, setAdminUser] = useState(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Determine active tab from route
  const getActiveTab = () => {
    const path = location.pathname;
    if (path.includes("/admin/candidates")) return "candidates";
    if (path.includes("/admin/recruiters")) return "recruiters";
    if (path.includes("/admin/admins")) return "admins";
    if (path.includes("/admin/verification")) return "verification";
    if (path.includes("/admin/cost-statistics")) return "cost-statistics";
    if (path.includes("/admin/jobs")) return "jobs";
    return "overview";
  };

  const activeTab = externalActiveTab || getActiveTab();

  useEffect(() => {
    const user = adminApi.getCurrentAdmin();
    setAdminUser(user);
    
    // Fetch pending recruiters count
    const fetchPendingCount = async () => {
      try {
        const data = await adminApi.getPendingRecruiters();
        setPendingCount(data.count || data.pending_recruiters?.length || 0);
      } catch (error) {
        console.error("Error fetching pending count:", error);
      }
    };
    
    fetchPendingCount();
  }, []);

  const handleLogout = useCallback(() => {
    localStorage.removeItem(process.env.REACT_APP_TOKEN_KEY || "companyxyz-token");
    localStorage.removeItem(process.env.REACT_APP_USER_KEY || "companyxyz-user");
    navigate("/login");
  }, [navigate]);

  const navItems = [
    {
      id: "overview",
      label: "Overview",
      path: "/admin",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
          <polyline points="9 22 9 12 15 12 15 22"></polyline>
        </svg>
      ),
    },
    {
      id: "candidates",
      label: "Candidates",
      path: "/admin/candidates",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      ),
    },
    {
      id: "recruiters",
      label: "Recruiters",
      path: "/admin/recruiters",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
        </svg>
      ),
    },
    {
      id: "admins",
      label: "Admins",
      path: "/admin/admins",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
        </svg>
      ),
    },
    {
      id: "verification",
      label: "Verification",
      path: "/admin/verification",
      badge: pendingCount,
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
      ),
    },
    {
      id: "cost-statistics",
      label: "Cost Statistics",
      path: "/admin/cost-statistics",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="12" y1="1" x2="12" y2="23"></line>
          <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
        </svg>
      ),
    },
  ];

  return (
    <div className={styles.adminContainer}>
      {/* Mobile Header */}
      <header className={styles.mobileHeader}>
        <div className={styles.mobileHeaderContent}>
          <button 
            className={styles.menuToggle}
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {isMobileMenuOpen ? (
                <>
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </>
              ) : (
                <>
                  <line x1="3" y1="12" x2="21" y2="12"></line>
                  <line x1="3" y1="6" x2="21" y2="6"></line>
                  <line x1="3" y1="18" x2="21" y2="18"></line>
                </>
              )}
            </svg>
          </button>
          <div className={styles.mobileBrand}>
            <h2>SmartHire</h2>
            <span className={styles.adminBadge}>Admin</span>
          </div>
          {adminUser && (
            <div className={styles.mobileAvatar}>
              {adminUser.name?.charAt(0).toUpperCase() || "A"}
            </div>
          )}
        </div>
      </header>

      {/* Sidebar */}
      <aside className={`${styles.sidebar} ${isMobileMenuOpen ? styles.sidebarOpen : ""}`}>
        <div className={styles.sidebarHeader}>
          <h2>SmartHire</h2>
          <span className={styles.adminBadge}>Admin</span>
        </div>

        {/* Admin Info */}
        {adminUser && (
          <div className={styles.adminInfo}>
            <div className={styles.adminAvatar}>
              {adminUser.name?.charAt(0).toUpperCase() || "A"}
            </div>
            <div className={styles.adminDetails}>
              <span className={styles.adminName}>{adminUser.name || "Admin"}</span>
              <span className={styles.adminEmail}>{adminUser.email || ""}</span>
            </div>
          </div>
        )}

        <nav className={styles.sidebarNav}>
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`${styles.navItem} ${activeTab === item.id ? styles.active : ""}`}
              onClick={() => {
                navigate(item.path);
                setIsMobileMenuOpen(false);
              }}
            >
              {item.icon}
              {item.label}
              {item.badge > 0 && <span className={styles.navBadge}>{item.badge}</span>}
            </button>
          ))}
        </nav>

        <div className={styles.sidebarFooter}>
          <button className={styles.logoutButton} onClick={handleLogout}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
              <polyline points="16 17 21 12 16 7"></polyline>
              <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
            Logout
          </button>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {isMobileMenuOpen && (
        <div 
          className={styles.mobileOverlay} 
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className={styles.mainContent}>
        {children}
      </main>
    </div>
  );
};

export default AdminLayout;

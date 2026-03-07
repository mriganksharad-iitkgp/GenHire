import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import styles from "./AdminDashboard.module.css";

// Custom debounce hook
const useDebounce = (value, delay) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
};

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("overview");
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [pendingRecruiters, setPendingRecruiters] = useState([]);
  
  // Separate loading states for different sections
  const [initialLoading, setInitialLoading] = useState(true);
  const [usersLoading, setUsersLoading] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null); // For individual actions
  
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  
  // User filters - searchTerm is debounced
  const [searchTerm, setSearchTerm] = useState("");
  const debouncedSearch = useDebounce(searchTerm, 400);
  const [userTypeFilter, setUserTypeFilter] = useState("");
  const [verificationFilter, setVerificationFilter] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  
  // Modal state
  const [selectedUser, setSelectedUser] = useState(null);
  const [showPermissionsModal, setShowPermissionsModal] = useState(false);
  const [selectedPermissions, setSelectedPermissions] = useState([]);
  const [permissionsSaving, setPermissionsSaving] = useState(false);
  
  // Available permissions
  const availablePermissions = useMemo(() => [
    { key: 'users.read', label: 'View Users', description: 'Can view user list and details' },
    { key: 'users.write', label: 'Edit Users', description: 'Can edit user profiles' },
    { key: 'users.verify', label: 'Verify Recruiters', description: 'Can approve/reject recruiters' },
    { key: 'users.delete', label: 'Delete Users', description: 'Can delete user accounts' },
    { key: 'jobs.read', label: 'View All Jobs', description: 'Can view all job postings' },
    { key: 'jobs.write', label: 'Create/Edit Jobs', description: 'Can manage job postings' },
    { key: 'jobs.delete', label: 'Delete Jobs', description: 'Can delete job postings' },
    { key: 'applications.read', label: 'View Applications', description: 'Can view all applications' },
    { key: 'applications.write', label: 'Manage Applications', description: 'Can update application status' },
    { key: 'stats.read', label: 'View Statistics', description: 'Can view platform analytics' },
    { key: '*', label: 'Super Admin', description: 'Full access to all features' },
  ], []);

  const getToken = useCallback(() => {
    return localStorage.getItem(process.env.REACT_APP_TOKEN_KEY || "companyxyz-token");
  }, []);

  // Check auth on mount
  useEffect(() => {
    const token = getToken();
    const userData = localStorage.getItem(process.env.REACT_APP_USER_KEY || "companyxyz-user");
    
    if (!token || !userData) {
      navigate("/login");
      return;
    }
    
    try {
      const parsed = JSON.parse(userData);
      if (parsed.userType !== "admin" && parsed.user_type !== "admin") {
        navigate("/login");
        return;
      }
    } catch {
      navigate("/login");
    }
  }, [navigate, getToken]);

  const fetchStats = useCallback(async (showLoader = true) => {
    if (showLoader) setStatsLoading(true);
    try {
      const token = getToken();
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/admin/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (!response.ok) throw new Error("Failed to fetch stats");
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error("Error fetching stats:", err);
    } finally {
      if (showLoader) setStatsLoading(false);
    }
  }, [getToken]);

  const fetchUsers = useCallback(async (showLoader = true) => {
    if (showLoader) setUsersLoading(true);
    try {
      const token = getToken();
      const params = new URLSearchParams({
        page: currentPage,
        limit: 10,
      });
      
      if (debouncedSearch) params.append("search", debouncedSearch);
      if (userTypeFilter) params.append("user_type", userTypeFilter);
      if (verificationFilter) params.append("is_verified", verificationFilter);
      
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/admin/users?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (!response.ok) throw new Error("Failed to fetch users");
      const data = await response.json();
      setUsers(data.users);
      setTotalPages(data.pagination.total_pages);
    } catch (err) {
      console.error("Error fetching users:", err);
      setError("Failed to load users");
    } finally {
      if (showLoader) setUsersLoading(false);
    }
  }, [currentPage, debouncedSearch, userTypeFilter, verificationFilter, getToken]);

  const fetchPendingRecruiters = useCallback(async (showLoader = true) => {
    if (showLoader) setPendingLoading(true);
    try {
      const token = getToken();
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/admin/pending-recruiters`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (!response.ok) throw new Error("Failed to fetch pending recruiters");
      const data = await response.json();
      setPendingRecruiters(data.pending_recruiters);
    } catch (err) {
      console.error("Error fetching pending recruiters:", err);
    } finally {
      if (showLoader) setPendingLoading(false);
    }
  }, [getToken]);

  // Initial data load
  useEffect(() => {
    const loadInitialData = async () => {
      setInitialLoading(true);
      await Promise.all([
        fetchStats(false),
        fetchUsers(false),
        fetchPendingRecruiters(false)
      ]);
      setInitialLoading(false);
    };
    loadInitialData();
  }, []);

  // Refetch users when debounced search or filters change
  useEffect(() => {
    if (!initialLoading) {
      fetchUsers(true);
    }
  }, [debouncedSearch, userTypeFilter, verificationFilter, currentPage]);

  const showNotification = useCallback((message, type = 'success') => {
    if (type === 'success') {
      setSuccessMessage(message);
      setTimeout(() => setSuccessMessage(""), 4000);
    } else {
      setError(message);
      setTimeout(() => setError(""), 4000);
    }
  }, []);

  const handleVerifyRecruiter = async (recruiterId) => {
    setActionLoading(recruiterId);
    try {
      const token = getToken();
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/admin/users/${recruiterId}/verify`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to verify recruiter");
      }
      
      showNotification("Recruiter verified successfully!");
      // Refresh data without full page loading
      fetchPendingRecruiters(false);
      fetchUsers(false);
      fetchStats(false);
    } catch (err) {
      showNotification(err.message, 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectRecruiter = async (recruiterId, reason = "") => {
    setActionLoading(recruiterId);
    try {
      const token = getToken();
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/admin/users/${recruiterId}/reject`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason: reason || "Account does not meet verification requirements" }),
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to reject recruiter");
      }
      
      showNotification("Recruiter rejected");
      fetchPendingRecruiters(false);
      fetchUsers(false);
    } catch (err) {
      showNotification(err.message, 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleUpdatePermissions = async () => {
    if (!selectedUser) return;
    
    setPermissionsSaving(true);
    try {
      const token = getToken();
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/admin/users/${selectedUser.id}/permissions`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ permissions: selectedPermissions }),
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || "Failed to update permissions");
      }
      
      const message = data.promoted 
        ? `${selectedUser.name} has been promoted to admin!`
        : `Permissions updated for ${selectedUser.name}`;
      
      showNotification(message);
      setShowPermissionsModal(false);
      fetchUsers(false);
      fetchStats(false);
    } catch (err) {
      showNotification(err.message, 'error');
    } finally {
      setPermissionsSaving(false);
    }
  };

  const openPermissionsModal = (user) => {
    setSelectedUser(user);
    setSelectedPermissions(user.permissions || []);
    setShowPermissionsModal(true);
  };

  const handleLogout = () => {
    localStorage.removeItem(process.env.REACT_APP_TOKEN_KEY || "companyxyz-token");
    localStorage.removeItem(process.env.REACT_APP_USER_KEY || "companyxyz-user");
    navigate("/login");
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  // Skeleton components for loading states
  const StatCardSkeleton = () => (
    <div className={`${styles.statCard} ${styles.skeleton}`}>
      <div className={styles.skeletonIcon}></div>
      <div className={styles.skeletonContent}>
        <div className={styles.skeletonLine} style={{ width: '60%' }}></div>
        <div className={styles.skeletonLine} style={{ width: '40%', height: '2rem' }}></div>
      </div>
    </div>
  );

  const TableRowSkeleton = () => (
    <tr className={styles.skeletonRow}>
      <td><div className={styles.skeletonCell}><div className={styles.skeletonAvatar}></div><div className={styles.skeletonLines}><div className={styles.skeletonLine}></div><div className={styles.skeletonLine} style={{ width: '70%' }}></div></div></div></td>
      <td><div className={styles.skeletonBadge}></div></td>
      <td><div className={styles.skeletonBadge}></div></td>
      <td><div className={styles.skeletonLine} style={{ width: '80px' }}></div></td>
      <td><div className={styles.skeletonLine} style={{ width: '60px' }}></div></td>
    </tr>
  );

  if (initialLoading) {
    return (
      <div className={styles.adminContainer}>
        <aside className={styles.sidebar}>
          <div className={styles.sidebarHeader}>
            <div className={styles.logoIcon}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 7h-9"></path>
                <path d="M14 17H5"></path>
                <circle cx="17" cy="17" r="3"></circle>
                <circle cx="7" cy="7" r="3"></circle>
              </svg>
            </div>
            <h2>SmartHire</h2>
            <span className={styles.adminBadge}>Admin</span>
          </div>
          <div className={styles.sidebarLoading}>
            <div className={styles.loadingSpinner}></div>
          </div>
        </aside>
        <main className={styles.mainContent}>
          <div className={styles.loadingContainer}>
            <div className={styles.loadingSpinner}></div>
            <p>Loading admin dashboard...</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className={styles.adminContainer}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <div className={styles.logoIcon}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 7h-9"></path>
              <path d="M14 17H5"></path>
              <circle cx="17" cy="17" r="3"></circle>
              <circle cx="7" cy="7" r="3"></circle>
            </svg>
          </div>
          <h2>SmartHire</h2>
          <span className={styles.adminBadge}>Admin</span>
        </div>
        
        <nav className={styles.sidebarNav}>
          <button
            className={`${styles.navItem} ${activeTab === "overview" ? styles.active : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
            Overview
          </button>
          <button
            className={`${styles.navItem} ${activeTab === "users" ? styles.active : ""}`}
            onClick={() => setActiveTab("users")}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
            User Manager
          </button>
          <button
            className={`${styles.navItem} ${activeTab === "verification" ? styles.active : ""}`}
            onClick={() => setActiveTab("verification")}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            Verification
            {pendingRecruiters.length > 0 && (
              <span className={styles.badge}>{pendingRecruiters.length}</span>
            )}
          </button>
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

      {/* Main Content */}
      <main className={styles.mainContent}>
        {/* Notifications */}
        {error && (
          <div className={styles.notification + ' ' + styles.error}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="15" y1="9" x2="9" y2="15"></line>
              <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
            <span>{error}</span>
            <button onClick={() => setError("")}>×</button>
          </div>
        )}
        {successMessage && (
          <div className={styles.notification + ' ' + styles.success}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <span>{successMessage}</span>
            <button onClick={() => setSuccessMessage("")}>×</button>
          </div>
        )}

        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div className={styles.tabContent}>
            <div className={styles.pageHeader}>
              <h1>Dashboard Overview</h1>
              <p>Monitor platform activity and manage users</p>
            </div>
            
            <div className={styles.statsGrid}>
              {statsLoading ? (
                <>
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                  <StatCardSkeleton />
                </>
              ) : stats && (
                <>
                  <div className={styles.statCard}>
                    <div className={styles.statIcon} data-color="purple">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                        <circle cx="9" cy="7" r="4"></circle>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                        <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                      </svg>
                    </div>
                    <div className={styles.statInfo}>
                      <span className={styles.statLabel}>Total Users</span>
                      <span className={styles.statValue}>{stats.users.total}</span>
                      <span className={styles.statChange}>+{stats.users.new_this_week} this week</span>
                    </div>
                  </div>
                  
                  <div className={styles.statCard}>
                    <div className={styles.statIcon} data-color="blue">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                      </svg>
                    </div>
                    <div className={styles.statInfo}>
                      <span className={styles.statLabel}>Candidates</span>
                      <span className={styles.statValue}>{stats.users.candidates}</span>
                    </div>
                  </div>
                  
                  <div className={styles.statCard}>
                    <div className={styles.statIcon} data-color="green">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
                      </svg>
                    </div>
                    <div className={styles.statInfo}>
                      <span className={styles.statLabel}>Recruiters</span>
                      <span className={styles.statValue}>{stats.recruiters.verified}</span>
                      <span className={styles.statChange}>{stats.recruiters.pending_verification} pending</span>
                    </div>
                  </div>
                  
                  <div className={styles.statCard}>
                    <div className={styles.statIcon} data-color="orange">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                      </svg>
                    </div>
                    <div className={styles.statInfo}>
                      <span className={styles.statLabel}>Active Jobs</span>
                      <span className={styles.statValue}>{stats.jobs.active}</span>
                      <span className={styles.statChange}>{stats.jobs.total} total</span>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Quick Actions */}
            {pendingRecruiters.length > 0 && (
              <div className={styles.quickAction}>
                <div className={styles.quickActionIcon}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                  </svg>
                </div>
                <div className={styles.quickActionContent}>
                  <h3>Pending Verifications</h3>
                  <p>{pendingRecruiters.length} recruiter{pendingRecruiters.length !== 1 ? 's' : ''} waiting for approval</p>
                </div>
                <button 
                  className={styles.quickActionButton}
                  onClick={() => setActiveTab("verification")}
                >
                  Review Now
                </button>
              </div>
            )}
          </div>
        )}

        {/* Users Tab */}
        {activeTab === "users" && (
          <div className={styles.tabContent}>
            <div className={styles.pageHeader}>
              <h1>User Manager</h1>
              <p>Search and manage platform users</p>
            </div>
            
            {/* Filters */}
            <div className={styles.filters}>
              <div className={styles.searchWrapper}>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8"></circle>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
                <input
                  type="text"
                  placeholder="Search by name, email, or company..."
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setCurrentPage(1);
                  }}
                  className={styles.searchInput}
                />
                {searchTerm && (
                  <button 
                    className={styles.clearSearch}
                    onClick={() => setSearchTerm("")}
                  >
                    ×
                  </button>
                )}
              </div>
              
              <select
                value={userTypeFilter}
                onChange={(e) => {
                  setUserTypeFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className={styles.filterSelect}
              >
                <option value="">All Types</option>
                <option value="candidate">Candidates</option>
                <option value="recruiter">Recruiters</option>
                <option value="admin">Admins</option>
              </select>
              
              <select
                value={verificationFilter}
                onChange={(e) => {
                  setVerificationFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className={styles.filterSelect}
              >
                <option value="">All Status</option>
                <option value="true">Verified</option>
                <option value="false">Pending</option>
              </select>
            </div>

            {/* Users Table */}
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Joined</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {usersLoading ? (
                    <>
                      <TableRowSkeleton />
                      <TableRowSkeleton />
                      <TableRowSkeleton />
                      <TableRowSkeleton />
                      <TableRowSkeleton />
                    </>
                  ) : users.length === 0 ? (
                    <tr>
                      <td colSpan="5" className={styles.emptyRow}>
                        <p>No users found</p>
                      </td>
                    </tr>
                  ) : (
                    users.map((user) => (
                      <tr key={user.id}>
                        <td>
                          <div className={styles.userCell}>
                            <div className={styles.avatar} data-type={user.user_type}>
                              {user.name.charAt(0).toUpperCase()}
                            </div>
                            <div className={styles.userInfo}>
                              <span className={styles.userName}>{user.name}</span>
                              <span className={styles.userEmail}>{user.email}</span>
                              {user.company_name && (
                                <span className={styles.userCompany}>{user.company_name}</span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className={`${styles.typeBadge} ${styles[user.user_type]}`}>
                            {user.user_type}
                          </span>
                        </td>
                        <td>
                          {user.user_type === "recruiter" ? (
                            <span className={`${styles.statusBadge} ${user.is_verified ? styles.verified : styles.pending}`}>
                              {user.is_verified ? "Verified" : "Pending"}
                            </span>
                          ) : (
                            <span className={`${styles.statusBadge} ${styles.active}`}>
                              Active
                            </span>
                          )}
                        </td>
                        <td className={styles.dateCell}>{formatDate(user.created_at)}</td>
                        <td>
                          <div className={styles.actions}>
                            {user.user_type === "recruiter" && !user.is_verified && (
                              <button
                                className={styles.actionBtn}
                                onClick={() => handleVerifyRecruiter(user.id)}
                                disabled={actionLoading === user.id}
                                title="Verify recruiter"
                              >
                                {actionLoading === user.id ? (
                                  <span className={styles.btnSpinner}></span>
                                ) : (
                                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                  </svg>
                                )}
                              </button>
                            )}
                            {/* Only show permissions button for candidates and admins, not recruiters */}
                            {user.user_type !== "recruiter" && (
                              <button
                                className={styles.actionBtn}
                                onClick={() => openPermissionsModal(user)}
                                title="Manage permissions"
                              >
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <circle cx="12" cy="12" r="3"></circle>
                                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                                </svg>
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className={styles.pagination}>
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1 || usersLoading}
                  className={styles.paginationBtn}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="15 18 9 12 15 6"></polyline>
                  </svg>
                  Previous
                </button>
                <span className={styles.paginationInfo}>
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages || usersLoading}
                  className={styles.paginationBtn}
                >
                  Next
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="9 18 15 12 9 6"></polyline>
                  </svg>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Verification Tab */}
        {activeTab === "verification" && (
          <div className={styles.tabContent}>
            <div className={styles.pageHeader}>
              <h1>Verification Queue</h1>
              <p>Review and approve recruiter accounts</p>
            </div>

            {pendingLoading ? (
              <div className={styles.loadingSection}>
                <div className={styles.loadingSpinner}></div>
                <p>Loading pending recruiters...</p>
              </div>
            ) : pendingRecruiters.length === 0 ? (
              <div className={styles.emptyState}>
                <div className={styles.emptyIcon}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                  </svg>
                </div>
                <h3>All caught up!</h3>
                <p>No recruiters are waiting for verification.</p>
              </div>
            ) : (
              <div className={styles.verificationList}>
                {pendingRecruiters.map((recruiter) => (
                  <div key={recruiter.id} className={styles.verificationCardExpanded}>
                    {/* Header Section */}
                    <div className={styles.cardHeaderExpanded}>
                      <div className={styles.recruiterAvatar}>
                        {recruiter.name.charAt(0).toUpperCase()}
                      </div>
                      <div className={styles.recruiterMeta}>
                        <h3>{recruiter.name}</h3>
                        <span className={styles.recruiterEmail}>{recruiter.email}</span>
                        <div className={styles.recruiterBadges}>
                          <span className={styles.pendingTag}>Pending Review</span>
                          <span className={styles.authBadge}>
                            {recruiter.auth_provider === 'google' ? (
                              <>
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
                                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                                </svg>
                                Google
                              </>
                            ) : (
                              <>
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12">
                                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                                  <polyline points="22,6 12,13 2,6"></polyline>
                                </svg>
                                Email
                              </>
                            )}
                          </span>
                          {recruiter.email_verified && (
                            <span className={styles.verifiedEmailBadge}>
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12">
                                <polyline points="20 6 9 17 4 12"></polyline>
                              </svg>
                              Email Verified
                            </span>
                          )}
                        </div>
                      </div>
                      <div className={styles.appliedDate}>
                        Applied {formatDate(recruiter.created_at)}
                      </div>
                    </div>
                    
                    {/* Company Information Section */}
                    <div className={styles.cardBodyExpanded}>
                      <div className={styles.infoSection}>
                        <h4>
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                            <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
                          </svg>
                          Company Information
                        </h4>
                        <div className={styles.infoGrid}>
                          <div className={styles.infoItem}>
                            <label>Company Name</label>
                            <span>{recruiter.company_name || "Not specified"}</span>
                          </div>
                          <div className={styles.infoItem}>
                            <label>Industry</label>
                            <span>{recruiter.company_industry || "Not specified"}</span>
                          </div>
                          <div className={styles.infoItem}>
                            <label>Company Size</label>
                            <span>{recruiter.company_size || "Not specified"}</span>
                          </div>
                          <div className={styles.infoItem}>
                            <label>Location</label>
                            <span>{recruiter.company_location || "Not specified"}</span>
                          </div>
                          {recruiter.company_website && (
                            <div className={styles.infoItem}>
                              <label>Website</label>
                              <a href={recruiter.company_website.startsWith('http') ? recruiter.company_website : `https://${recruiter.company_website}`} target="_blank" rel="noopener noreferrer">
                                {recruiter.company_website.replace(/^https?:\/\//, '')}
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12">
                                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                                  <polyline points="15 3 21 3 21 9"></polyline>
                                  <line x1="10" y1="14" x2="21" y2="3"></line>
                                </svg>
                              </a>
                            </div>
                          )}
                          {recruiter.linkedin_profile && (
                            <div className={styles.infoItem}>
                              <label>LinkedIn</label>
                              <a href={recruiter.linkedin_profile.startsWith('http') ? recruiter.linkedin_profile : `https://${recruiter.linkedin_profile}`} target="_blank" rel="noopener noreferrer">
                                {recruiter.linkedin_profile.replace(/^https?:\/\/(www\.)?linkedin\.com\//, '')}
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12">
                                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                                  <polyline points="15 3 21 3 21 9"></polyline>
                                  <line x1="10" y1="14" x2="21" y2="3"></line>
                                </svg>
                              </a>
                            </div>
                          )}
                        </div>
                      </div>
                      
                      {/* Company Description */}
                      {recruiter.company_description && (
                        <div className={styles.infoSection}>
                          <h4>
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                              <polyline points="14 2 14 8 20 8"></polyline>
                              <line x1="16" y1="13" x2="8" y2="13"></line>
                              <line x1="16" y1="17" x2="8" y2="17"></line>
                            </svg>
                            About the Company
                          </h4>
                          <p className={styles.descriptionText}>{recruiter.company_description}</p>
                        </div>
                      )}
                      
                      {/* Reason for Joining */}
                      {recruiter.reason_for_joining && (
                        <div className={styles.infoSection}>
                          <h4>
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <circle cx="12" cy="12" r="10"></circle>
                              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                              <line x1="12" y1="17" x2="12.01" y2="17"></line>
                            </svg>
                            Why They're Joining SmartHire
                          </h4>
                          <p className={styles.descriptionText}>{recruiter.reason_for_joining}</p>
                        </div>
                      )}
                    </div>
                    
                    {/* Actions Footer */}
                    <div className={styles.cardFooterExpanded}>
                      <button
                        className={styles.rejectBtn}
                        onClick={() => handleRejectRecruiter(recruiter.id)}
                        disabled={actionLoading === recruiter.id}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="15" y1="9" x2="9" y2="15"></line>
                          <line x1="9" y1="9" x2="15" y2="15"></line>
                        </svg>
                        {actionLoading === recruiter.id ? 'Processing...' : 'Reject Application'}
                      </button>
                      <button
                        className={styles.approveBtn}
                        onClick={() => handleVerifyRecruiter(recruiter.id)}
                        disabled={actionLoading === recruiter.id}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                          <polyline points="22 4 12 14.01 9 11.01"></polyline>
                        </svg>
                        {actionLoading === recruiter.id ? 'Processing...' : 'Approve & Verify'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Permissions Modal */}
      {showPermissionsModal && selectedUser && (
        <div className={styles.modalOverlay} onClick={() => !permissionsSaving && setShowPermissionsModal(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div>
                <h2>Manage Permissions</h2>
                <p>Configure access for {selectedUser.name}</p>
              </div>
              <button 
                className={styles.modalClose} 
                onClick={() => !permissionsSaving && setShowPermissionsModal(false)}
                disabled={permissionsSaving}
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>
            
            <div className={styles.modalBody}>
              {selectedUser.user_type === 'candidate' && selectedPermissions.length === 0 && (
                <div className={styles.promotionNotice}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                  </svg>
                  <span>Granting any permission will promote this user to admin</span>
                </div>
              )}
              
              <div className={styles.permissionsList}>
                {availablePermissions.map((perm) => (
                  <label 
                    key={perm.key} 
                    className={`${styles.permissionItem} ${selectedPermissions.includes(perm.key) ? styles.selected : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedPermissions.includes(perm.key)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          if (perm.key === '*') {
                            setSelectedPermissions(['*']);
                          } else {
                            setSelectedPermissions([...selectedPermissions.filter(p => p !== '*'), perm.key]);
                          }
                        } else {
                          setSelectedPermissions(selectedPermissions.filter(p => p !== perm.key));
                        }
                      }}
                      disabled={permissionsSaving || (perm.key !== '*' && selectedPermissions.includes('*'))}
                    />
                    <div className={styles.permissionContent}>
                      <span className={styles.permissionLabel}>{perm.label}</span>
                      <span className={styles.permissionDesc}>{perm.description}</span>
                    </div>
                    <span className={styles.permissionKey}>{perm.key}</span>
                  </label>
                ))}
              </div>
            </div>
            
            <div className={styles.modalFooter}>
              <button 
                className={styles.cancelBtn} 
                onClick={() => setShowPermissionsModal(false)}
                disabled={permissionsSaving}
              >
                Cancel
              </button>
              <button 
                className={styles.saveBtn} 
                onClick={handleUpdatePermissions}
                disabled={permissionsSaving}
              >
                {permissionsSaving ? (
                  <>
                    <span className={styles.btnSpinner}></span>
                    Saving...
                  </>
                ) : (
                  'Save Permissions'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;

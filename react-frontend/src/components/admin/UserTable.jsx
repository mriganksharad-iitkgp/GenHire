import React from "react";
import styles from "./AdminShared.module.css";

const UserTable = ({
  users,
  loading,
  onRowClick,
  onDelete,
  showDelete = true,
  showType = true,
  currentUserId,
  emptyMessage = "No users found",
}) => {
  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getStatusBadge = (user) => {
    if (user.user_type === "recruiter") {
      return (
        <span className={`${styles.badge} ${user.is_verified ? styles.verified : styles.pending}`}>
          {user.is_verified ? "Verified" : "Pending"}
        </span>
      );
    }
    return <span className={`${styles.badge} ${styles.active}`}>Active</span>;
  };

  if (loading) {
    return (
      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>User</th>
              {showType && <th>Type</th>}
              <th>Status</th>
              <th>Joined</th>
              {showDelete && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {[...Array(5)].map((_, i) => (
              <tr key={i}>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.875rem" }}>
                    <div style={{ width: 40, height: 40, borderRadius: 10, background: "#e2e8f0" }}></div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                      <div style={{ width: 120, height: 14, background: "#e2e8f0", borderRadius: 4 }}></div>
                      <div style={{ width: 180, height: 12, background: "#e2e8f0", borderRadius: 4 }}></div>
                    </div>
                  </div>
                </td>
                {showType && <td><div style={{ width: 60, height: 24, background: "#e2e8f0", borderRadius: 6 }}></div></td>}
                <td><div style={{ width: 60, height: 24, background: "#e2e8f0", borderRadius: 6 }}></div></td>
                <td><div style={{ width: 80, height: 14, background: "#e2e8f0", borderRadius: 4 }}></div></td>
                {showDelete && <td><div style={{ width: 32, height: 32, background: "#e2e8f0", borderRadius: 8 }}></div></td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (!users || users.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyStateIcon}>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
            <circle cx="9" cy="7" r="4"></circle>
            <line x1="23" y1="11" x2="17" y2="11"></line>
          </svg>
        </div>
        <h3 className={styles.emptyStateTitle}>{emptyMessage}</h3>
        <p className={styles.emptyStateText}>Try adjusting your search or filters</p>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <table className={`${styles.table} ${onRowClick ? styles.tableClickable : ""}`}>
        <thead>
          <tr>
            <th>User</th>
            {showType && <th>Type</th>}
            <th>Status</th>
            <th>Joined</th>
            {showDelete && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr 
              key={user.id} 
              onClick={() => onRowClick && onRowClick(user)}
              style={{ cursor: onRowClick ? "pointer" : "default" }}
            >
              <td>
                <div style={{ display: "flex", alignItems: "center", gap: "0.875rem" }}>
                  <div className={`${styles.userAvatar} ${styles[user.user_type]}`}>
                    {user.name?.charAt(0).toUpperCase() || "U"}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.125rem" }}>
                    <span style={{ fontWeight: 600, color: "var(--admin-text)", fontSize: "0.9rem" }}>
                      {user.name}
                    </span>
                    <span style={{ color: "var(--admin-text-secondary)", fontSize: "0.8rem" }}>
                      {user.email}
                    </span>
                    {user.company_name && (
                      <span style={{ color: "var(--admin-text-secondary)", fontSize: "0.75rem", fontStyle: "italic" }}>
                        {user.company_name}
                      </span>
                    )}
                  </div>
                </div>
              </td>
              {showType && (
                <td>
                  <span className={`${styles.badge} ${styles[user.user_type]}`}>
                    {user.user_type}
                  </span>
                </td>
              )}
              <td>{getStatusBadge(user)}</td>
              <td style={{ color: "var(--admin-text-secondary)", fontSize: "0.85rem" }}>
                {formatDate(user.created_at)}
              </td>
              {showDelete && (
                <td onClick={(e) => e.stopPropagation()}>
                  {user.id !== currentUserId && (
                    <button
                      className={`${styles.btnIcon} danger`}
                      onClick={() => onDelete && onDelete(user)}
                      title="Delete user"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default UserTable;

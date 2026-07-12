import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import UserTable from "features/admin/components/UserTable";
import ConfirmModal from "features/admin/components/ConfirmModal";
import styles from "./AdminPages.module.css";
import * as adminApi from "features/admin/api/adminApi";

// Custom debounce hook
const useDebounce = (value, delay) => {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
};

const ManageAdmins = () => {
  const navigate = useNavigate();
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const debouncedSearch = useDebounce(searchTerm, 400);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [currentUserId, setCurrentUserId] = useState(null);
  
  // Delete modal state
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, user: null });
  const [deleteLoading, setDeleteLoading] = useState(false);
  
  // Notifications
  const [notification, setNotification] = useState({ show: false, message: "", type: "success" });

  const showNotification = useCallback((message, type = "success") => {
    setNotification({ show: true, message, type });
    setTimeout(() => setNotification({ show: false, message: "", type: "success" }), 4000);
  }, []);

  const fetchAdmins = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getUsers({
        user_type: "admin",
        search: debouncedSearch,
        page: currentPage,
        limit: 15,
      });
      setAdmins(data.users || []);
      setTotalPages(data.pagination?.total_pages || 1);
    } catch (error) {
      console.error("Error fetching admins:", error);
      showNotification(error.message || "Failed to fetch admins", "error");
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, currentPage, showNotification]);

  useEffect(() => {
    const user = adminApi.getCurrentAdmin();
    setCurrentUserId(user.id || user._id);
    fetchAdmins();
  }, [navigate, fetchAdmins]);

  const handleDelete = async () => {
    if (!deleteModal.user) return;
    setDeleteLoading(true);
    try {
      await adminApi.deleteUser(deleteModal.user.id);
      showNotification(`${deleteModal.user.name} has been deleted`);
      setDeleteModal({ isOpen: false, user: null });
      fetchAdmins();
    } catch (error) {
      showNotification(error.message || "Failed to delete admin", "error");
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <>
      <div className={styles.pageContainer}>
        {/* Notification */}
        {notification.show && (
          <div className={`${styles.notification} ${styles[notification.type]}`}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {notification.type === "success" ? (
                <>
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </>
              ) : (
                <>
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="15" y1="9" x2="9" y2="15"></line>
                  <line x1="9" y1="9" x2="15" y2="15"></line>
                </>
              )}
            </svg>
            <span>{notification.message}</span>
            <button onClick={() => setNotification({ show: false, message: "", type: "success" })}>×</button>
          </div>
        )}

        <div className={styles.pageHeader}>
          <h1>Manage Admins</h1>
          <p>View and manage administrator accounts</p>
        </div>

        {/* Info Notice */}
        <div className={styles.alertCard} style={{ marginBottom: "1.5rem", background: "linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%)", borderColor: "#a5b4fc" }}>
          <div className={styles.alertIcon} style={{ background: "#6366f1", color: "#fff" }}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
          </div>
          <div className={styles.alertContent}>
            <h3 style={{ color: "#3730a3" }}>Admin Privileges</h3>
            <p style={{ color: "#4338ca" }}>All admins have full access to manage users, jobs, and platform settings. You cannot delete your own account.</p>
          </div>
        </div>

        {/* Filters */}
        <div className={styles.filtersBar}>
          <div className={styles.searchWrapper}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              placeholder="Search by name or email..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className={styles.searchInput}
            />
            {searchTerm && (
              <button className={styles.clearSearch} onClick={() => setSearchTerm("")}>
                ×
              </button>
            )}
          </div>
        </div>

        {/* Admins Table */}
        <UserTable
          users={admins}
          loading={loading}
          onDelete={(user) => setDeleteModal({ isOpen: true, user })}
          showType={false}
          currentUserId={currentUserId}
          emptyMessage="No admins found"
        />

        {/* Pagination */}
        {totalPages > 1 && (
          <div className={styles.pagination}>
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1 || loading}
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
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages || loading}
              className={styles.paginationBtn}
            >
              Next
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </button>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        <ConfirmModal
          isOpen={deleteModal.isOpen}
          onClose={() => setDeleteModal({ isOpen: false, user: null })}
          onConfirm={handleDelete}
          title="Delete Admin"
          message={`Are you sure you want to delete ${deleteModal.user?.name}? This action cannot be undone.`}
          confirmText="Delete"
          isLoading={deleteLoading}
        />
      </div>
    </>
  );
};

export default ManageAdmins;

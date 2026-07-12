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

const ManageCandidates = () => {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const debouncedSearch = useDebounce(searchTerm, 400);
  const [statusFilter, setStatusFilter] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  
  // Delete modal state
  const [deleteModal, setDeleteModal] = useState({ isOpen: false, user: null });
  const [deleteLoading, setDeleteLoading] = useState(false);
  
  // Notifications
  const [notification, setNotification] = useState({ show: false, message: "", type: "success" });

  const showNotification = useCallback((message, type = "success") => {
    setNotification({ show: true, message, type });
    setTimeout(() => setNotification({ show: false, message: "", type: "success" }), 4000);
  }, []);

  const fetchCandidates = useCallback(async () => {
    setLoading(true);
    try {
      const filters = {
        user_type: "candidate",
        search: debouncedSearch,
        page: currentPage,
        limit: 15,
      };
      if (statusFilter) {
        filters.is_verified = statusFilter;
      }
      const data = await adminApi.getUsers(filters);
      setCandidates(data.users || []);
      setTotalPages(data.pagination?.total_pages || 1);
      setTotalCount(data.pagination?.total || 0);
    } catch (error) {
      console.error("Error fetching candidates:", error);
      showNotification(error.message || "Failed to fetch candidates", "error");
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, statusFilter, currentPage, showNotification]);

  useEffect(() => {
    fetchCandidates();
  }, [navigate, fetchCandidates]);

  const handleRowClick = (user) => {
    navigate(`/admin/candidates/${user.id}`);
  };

  const handleDelete = async () => {
    if (!deleteModal.user) return;
    setDeleteLoading(true);
    try {
      await adminApi.deleteUser(deleteModal.user.id);
      showNotification(`${deleteModal.user.name} has been deleted`);
      setDeleteModal({ isOpen: false, user: null });
      fetchCandidates();
    } catch (error) {
      showNotification(error.message || "Failed to delete candidate", "error");
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
          <h1>Manage Candidates</h1>
          <p>View and manage all candidate accounts and their data</p>
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
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setCurrentPage(1);
            }}
            className={styles.filterSelect}
          >
            <option value="">All Status</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>

        {/* Candidates Table */}
        <UserTable
          users={candidates}
          loading={loading}
          onRowClick={handleRowClick}
          onDelete={(user) => setDeleteModal({ isOpen: true, user })}
          showType={false}
          showPlan
          emptyMessage="No candidates found"
        />

        {/* Pagination */}
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
            Page {currentPage} of {totalPages} ({totalCount} total)
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

        {/* Delete Confirmation Modal */}
        <ConfirmModal
          isOpen={deleteModal.isOpen}
          onClose={() => setDeleteModal({ isOpen: false, user: null })}
          onConfirm={handleDelete}
          title="Delete Candidate"
          message={`Are you sure you want to delete ${deleteModal.user?.name}? This will also delete all their applications and interview data. This action cannot be undone.`}
          confirmText="Delete"
          isLoading={deleteLoading}
        />
      </div>
    </>
  );
};

export default ManageCandidates;

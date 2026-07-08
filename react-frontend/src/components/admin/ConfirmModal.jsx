import React from "react";
import Modal from "shared/components/ui/Modal";
import styles from "./AdminShared.module.css";

/**
 * Admin-themed confirm dialog: the shared Modal shell with the admin panel's
 * styling. Same props as shared/components/ui/ConfirmDialog plus `children`
 * for extra body content.
 */
const ConfirmModal = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = "Confirm",
  cancelText = "Cancel",
  confirmVariant = "danger",
  isLoading = false,
  children,
}) => (
  <Modal
    isOpen={isOpen}
    onClose={onClose}
    overlayClassName={styles.modalOverlay}
    contentClassName={styles.modal}
  >
    <div className={styles.modalHeader}>
      <div>
        <h2 className={styles.modalTitle}>{title}</h2>
      </div>
      <button className={styles.modalClose} onClick={onClose} disabled={isLoading}>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>

    <div className={styles.modalBody}>
      <p style={{ margin: 0, color: "var(--admin-text-secondary)" }}>{message}</p>
      {children}
    </div>

    <div className={styles.modalFooter}>
      <button
        className={`${styles.btn} ${styles.btnSecondary}`}
        onClick={onClose}
        disabled={isLoading}
      >
        {cancelText}
      </button>
      <button
        className={`${styles.btn} ${confirmVariant === "danger" ? styles.btnDanger : styles.btnPrimary}`}
        onClick={onConfirm}
        disabled={isLoading}
      >
        {isLoading ? (
          <>
            <span className={styles.spinner}></span>
            Processing...
          </>
        ) : (
          confirmText
        )}
      </button>
    </div>
  </Modal>
);

export default ConfirmModal;

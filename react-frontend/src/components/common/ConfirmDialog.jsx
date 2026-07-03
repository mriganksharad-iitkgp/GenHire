import React from 'react';
import styles from './ConfirmDialog.module.css';

/**
 * Shared confirm dialog — replaces native window.confirm() across
 * recruiter/candidate-facing pages so destructive actions get a styled,
 * on-brand prompt instead of a jarring browser dialog. Same prop shape as
 * the admin panel's ConfirmModal (components/admin/ConfirmModal.jsx) for
 * familiarity, but self-contained (no admin-only CSS variables) so it's
 * safe to use anywhere.
 */
const ConfirmDialog = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  confirmVariant = 'danger', // 'danger' | 'primary'
  isLoading = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h2>{title}</h2>
          <button
            className={styles.closeButton}
            onClick={onClose}
            disabled={isLoading}
            aria-label="Close dialog"
          >
            &times;
          </button>
        </div>

        <div className={styles.modalBody}>
          <p>{message}</p>
        </div>

        <div className={styles.modalActions}>
          <button className={styles.cancelButton} onClick={onClose} disabled={isLoading}>
            {cancelText}
          </button>
          <button
            className={confirmVariant === 'danger' ? styles.dangerButton : styles.primaryButton}
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? 'Processing...' : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;

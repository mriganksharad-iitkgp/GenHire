import React, { useId } from 'react';
import Modal from './Modal';
import styles from './ConfirmDialog.module.css';

/**
 * Shared confirm dialog — replaces native window.confirm() across
 * recruiter/candidate-facing pages so destructive actions get a styled,
 * on-brand prompt instead of a jarring browser dialog. The admin panel's
 * ConfirmModal is the same shell with the admin theme's CSS.
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
  const headingId = useId();
  const messageId = useId();
  return (
  <Modal
    isOpen={isOpen}
    onClose={onClose}
    overlayClassName={styles.modalOverlay}
    contentClassName={styles.modalContent}
    ariaLabelledBy={headingId}
    ariaDescribedBy={messageId}
    closeOnEsc={!isLoading}
    closeOnOverlayClick={!isLoading}
  >
    <div className={styles.modalHeader}>
      <h2 id={headingId}>{title}</h2>
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
      <p id={messageId}>{message}</p>
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
  </Modal>
  );
};

export default ConfirmDialog;

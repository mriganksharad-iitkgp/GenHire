import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './DeleteAccountModal.module.css';
import { getToken, clearSession } from 'shared/utils/session';

const DeleteAccountModal = ({ isOpen, onClose, onLogout }) => {
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleDelete = async () => {
    setIsDeleting(true);
    setError(null);
    try {
      const token = getToken();
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/me`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to delete account');
      }

      // Successfully deleted, now clear auth and redirect
      if (onLogout) {
        // Clear token from session storage
        clearSession();
        navigate('/');
        window.location.reload();
      }
    } catch (err) {
      setError(err.message);
      setIsDeleting(false);
    }
  };

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent}>
        <div className={styles.modalHeader}>
          <h2>Delete Account</h2>
          <button className={styles.closeButton} onClick={onClose} disabled={isDeleting}>&times;</button>
        </div>
        
        <div className={styles.modalBody}>
          <div className={styles.warningBox}>
            <strong>Warning:</strong> Deleting your account will permanently remove all your progress, applications, jobs, and any remaining credits.
            <br/><br/>
            You will NOT receive a new 100-credit signup bonus if you create a new account in the future. This action cannot be undone.
          </div>

          {error && <div className={styles.errorMessage}>{error}</div>}
          
          <p>Are you absolutely sure you want to delete your account?</p>
        </div>

        <div className={styles.modalActions}>
          <button 
            className={styles.cancelButton} 
            onClick={onClose}
            disabled={isDeleting}
          >
            Cancel
          </button>
          <button 
            className={styles.deleteButton} 
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting...' : 'Yes, Delete My Account'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteAccountModal;

import React, { useState, useEffect } from 'react';
import styles from './Toast.module.css';

const Toast = ({ message, type = 'info', duration = 3000, onClose }) => {
  const [visible, setVisible] = useState(true);

  // Reset toast visibility when message changes
  useEffect(() => {
    setVisible(true);
    const timer = setTimeout(() => {
      setVisible(false);
      // Wait for fade out animation then close
      setTimeout(() => onClose && onClose(), 300);
    }, duration);

    return () => clearTimeout(timer);
  }, [message, duration, onClose]);

  const getIcon = () => {
    switch (type) {
      case 'success': return 'fa-check-circle';
      case 'error': return 'fa-times-circle';
      case 'warning': return 'fa-exclamation-triangle';
      default: return 'fa-info-circle';
    }
  };

  return (
    <div className={`${styles.toast} ${styles[type]} ${visible ? styles.visible : styles.hidden}`}>
      <i className={`fa ${getIcon()}`}></i>
      <span>{message}</span>
      <button
        className={styles.closeButton}
        onClick={() => {
          setVisible(false);
          setTimeout(() => onClose && onClose(), 200);
        }}
      >
        <i className="fa fa-times"></i>
      </button>
    </div>
  );
};

export default Toast;

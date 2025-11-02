import React from 'react';
import styles from './Loading.module.css';

const Loading = ({ 
  size = 'medium', 
  fullScreen = false,
  text = 'Loading...',
  color = 'primary'
}) => {
  if (fullScreen) {
    return (
      <div className={styles.fullScreenContainer}>
        <div className={`${styles.spinner} ${styles[size]} ${styles[color]}`}>
          <div className={styles.spinnerRing}></div>
          <div className={styles.spinnerRing}></div>
          <div className={styles.spinnerRing}></div>
          <div className={styles.spinnerRing}></div>
        </div>
        {text && <p className={styles.loadingText}>{text}</p>}
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={`${styles.spinner} ${styles[size]} ${styles[color]}`}>
        <div className={styles.spinnerRing}></div>
        <div className={styles.spinnerRing}></div>
        <div className={styles.spinnerRing}></div>
        <div className={styles.spinnerRing}></div>
      </div>
      {text && <p className={styles.loadingText}>{text}</p>}
    </div>
  );
};

// Skeleton Loader Component
export const Skeleton = ({ width = '100%', height = '20px', borderRadius = '4px', className = '' }) => {
  return (
    <div 
      className={`${styles.skeleton} ${className}`}
      style={{ width, height, borderRadius }}
    />
  );
};

// Card Skeleton
export const SkeletonCard = () => {
  return (
    <div className={styles.skeletonCard}>
      <div className={styles.skeletonHeader}>
        <Skeleton width="60px" height="60px" borderRadius="8px" />
        <div className={styles.skeletonContent}>
          <Skeleton width="70%" height="20px" />
          <Skeleton width="40%" height="16px" />
        </div>
      </div>
      <Skeleton width="100%" height="100px" />
      <div className={styles.skeletonFooter}>
        <Skeleton width="80px" height="32px" borderRadius="8px" />
        <Skeleton width="80px" height="32px" borderRadius="8px" />
      </div>
    </div>
  );
};

// Inline Spinner (for buttons)
export const InlineSpinner = ({ size = 'small' }) => {
  return (
    <div className={`${styles.inlineSpinner} ${styles[size]}`}>
      <div className={styles.spinnerDot}></div>
      <div className={styles.spinnerDot}></div>
      <div className={styles.spinnerDot}></div>
    </div>
  );
};

export default Loading;

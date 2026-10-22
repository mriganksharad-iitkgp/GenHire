import React from 'react';
import styles from './GenHireBrand.module.css';

export default function GenHireBrand({ label }) {
  return <span className={styles.brand}><span className={styles.mark} aria-hidden="true">G<span /></span><span className={styles.wordmark}>GenHire{label && <span className={styles.label}>{label}</span>}</span></span>;
}

import React from "react";
import { Link } from "react-router-dom";
import styles from "./AuthStory.module.css";
export default function AuthBrand({ className = "" }) {
  return <Link to="/" aria-label="GenHire home" className={`${styles.brand} ${className}`}>
    <span className={styles.brandMark}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M20 7h-9M14 17H5" /><circle cx="17" cy="17" r="3" /><circle cx="7" cy="7" r="3" /></svg></span>GenHire
  </Link>;
}

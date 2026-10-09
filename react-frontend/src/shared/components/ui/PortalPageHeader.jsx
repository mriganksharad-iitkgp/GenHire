import React from "react";
import styles from "./PortalPageHeader.module.css";

export default function PortalPageHeader({ title, subtitle, eyebrow = "Your workspace", icon = "fa-th-large", actions }) {
  return <header className={styles.header}>
    <div className={styles.intro}>
      <span className={styles.eyebrow}><i className={`fa ${icon}`} aria-hidden="true" />{eyebrow}</span>
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </div>
    {actions && <div className={styles.actions}>{actions}</div>}
    <span className={styles.decoration} aria-hidden="true" />
  </header>;
}

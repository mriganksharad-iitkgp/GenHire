import React, { memo } from "react";
import styles from "./SkeletonCard.module.css";

function SkeletonCard({ variant = "job" }) {
  if (variant === "practice") {
    return (
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={`${styles.shimmer} ${styles.avatarSm}`} />
          <div className={styles.headerText}>
            <div className={`${styles.shimmer} ${styles.title}`} />
            <div className={`${styles.shimmer} ${styles.subtitleNarrow}`} />
          </div>
          <div className={`${styles.shimmer} ${styles.badge}`} />
        </div>
        <div className={styles.body}>
          <div className={`${styles.shimmer} ${styles.line}`} style={{ width: "75%" }} />
          <div className={`${styles.shimmer} ${styles.line}`} style={{ width: "55%" }} />
        </div>
        <div className={styles.footer}>
          <div className={`${styles.shimmer} ${styles.scorePill}`} />
          <div className={`${styles.shimmer} ${styles.scorePill}`} />
          <div className={`${styles.shimmer} ${styles.btnSm}`} />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div className={`${styles.shimmer} ${styles.avatar}`} />
        <div className={styles.headerText}>
          <div className={`${styles.shimmer} ${styles.title}`} />
          <div className={`${styles.shimmer} ${styles.subtitle}`} />
        </div>
        <div className={`${styles.shimmer} ${styles.badge}`} />
      </div>
      <div className={styles.body}>
        <div className={`${styles.shimmer} ${styles.line}`} style={{ width: "85%" }} />
        <div className={`${styles.shimmer} ${styles.line}`} style={{ width: "70%" }} />
        <div className={`${styles.shimmer} ${styles.line}`} style={{ width: "55%" }} />
      </div>
      <div className={styles.tags}>
        <div className={`${styles.shimmer} ${styles.tag}`} />
        <div className={`${styles.shimmer} ${styles.tag}`} />
        <div className={`${styles.shimmer} ${styles.tag}`} />
      </div>
      <div className={styles.footer}>
        <div className={`${styles.shimmer} ${styles.metaItem}`} />
        <div className={`${styles.shimmer} ${styles.metaItem}`} />
        <div className={`${styles.shimmer} ${styles.btn}`} />
      </div>
    </div>
  );
}

export default memo(SkeletonCard);

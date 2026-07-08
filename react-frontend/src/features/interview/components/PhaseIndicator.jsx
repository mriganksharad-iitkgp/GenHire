import React, { memo } from "react";
import styles from "./PhaseIndicator.module.css";

const STEPS = [
  { label: "Ready Check" },
  { label: "Face Verify" },
  { label: "Eye Tracking" },
  { label: "Interview" },
];

function PhaseIndicator({ currentStep }) {
  return (
    <div className={styles.root}>
      {STEPS.map((step, i) => {
        const done = i < currentStep;
        const active = i === currentStep;
        return (
          <React.Fragment key={i}>
            <div className={`${styles.step} ${done ? styles.done : active ? styles.active : styles.pending}`}>
              <div className={styles.circle}>
                {done ? "✓" : i + 1}
              </div>
              <span className={styles.label}>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`${styles.connector} ${done ? styles.connectorDone : ""}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export default memo(PhaseIndicator);

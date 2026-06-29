import React, { memo, useState } from "react";
import styles from "./PreInterviewChecklist.module.css";

const ITEMS = [
  { id: "quiet",   text: "I'm in a quiet, well-lit environment with no background noise" },
  { id: "face",    text: "My face is clearly visible on camera — no sunglasses, hats, or face coverings" },
  { id: "alone",   text: "I'm alone in the room; no other people are visible or audible" },
  { id: "time",    text: "I have 15–20 uninterrupted minutes available right now" },
  { id: "devices", text: "My phone is silenced and I've closed all unnecessary browser tabs" },
];

function PreInterviewChecklist({ onConfirm }) {
  const [checked, setChecked] = useState({});

  const toggle = (id) =>
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }));

  const doneCount = ITEMS.filter((it) => checked[it.id]).length;
  const allChecked = doneCount === ITEMS.length;

  return (
    <div className={styles.card}>
      <p className={styles.subtitle}>
        Confirm each item below before your camera and eye-tracking setup begins.
      </p>
      <ul className={styles.list}>
        {ITEMS.map((item) => (
          <li
            key={item.id}
            className={`${styles.item} ${checked[item.id] ? styles.itemChecked : ""}`}
            onClick={() => toggle(item.id)}
            role="checkbox"
            aria-checked={!!checked[item.id]}
            tabIndex={0}
            onKeyDown={(e) => e.key === " " && toggle(item.id)}
          >
            <span className={styles.checkbox} aria-hidden>
              {checked[item.id] ? "✓" : ""}
            </span>
            <span className={styles.itemText}>{item.text}</span>
          </li>
        ))}
      </ul>
      <button
        className={`${styles.btn} ${allChecked ? styles.btnReady : ""}`}
        onClick={onConfirm}
        disabled={!allChecked}
      >
        {allChecked
          ? "Continue to Camera Setup →"
          : `${doneCount} of ${ITEMS.length} confirmed`}
      </button>
      {!allChecked && (
        <p className={styles.hint}>Check all items to unlock the next step</p>
      )}
    </div>
  );
}

export default memo(PreInterviewChecklist);

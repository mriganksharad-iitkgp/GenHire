import React from "react";
import styles from "../../pages/Profile.module.css";

export default function BioForm({ bio, onChange, onSubmit }) {
  return (
    <section className={styles.bioSection}>
      <h2>Bio Data</h2>
      <form onSubmit={onSubmit}>
        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label>Full Name</label>
            <input type="text" value={bio.name} onChange={(e) => onChange({ ...bio, name: e.target.value })} />
          </div>
          <div className={styles.formGroup}>
            <label>Email</label>
            <input type="email" value={bio.email} onChange={(e) => onChange({ ...bio, email: e.target.value })} />
          </div>
        </div>

        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label>Phone</label>
            <input type="tel" value={bio.phone} onChange={(e) => onChange({ ...bio, phone: e.target.value })} />
          </div>
          <div className={styles.formGroup}>
            <label>Location</label>
            <input type="text" value={bio.location} onChange={(e) => onChange({ ...bio, location: e.target.value })} />
          </div>
        </div>

        <div className={styles.formGroup}>
          <label>Professional Title</label>
          <input type="text" value={bio.title} onChange={(e) => onChange({ ...bio, title: e.target.value })} />
        </div>

        <div className={styles.formGroup}>
          <label>About Me</label>
          <textarea rows="4" value={bio.about} onChange={(e) => onChange({ ...bio, about: e.target.value })}></textarea>
        </div>

        <div className={styles.formGroup}>
          <label>Skills (comma-separated)</label>
          <input
            type="text"
            value={bio.skills.join(", ")}
            onChange={(e) => onChange({ ...bio, skills: e.target.value.split(",").map((s) => s.trim()) })}
          />
        </div>

        <button type="submit" className={styles.updateButton}>
          Update Profile
        </button>
      </form>
    </section>
  );
}

import React from "react";
import styles from "features/candidate/pages/Profile.module.css";

export default function BioForm({ bio, onChange, onSubmit, saving = false }) {
  return (
    <section className={styles.bioSection}>
      <h2>Personal details</h2>
      <p className={styles.sectionDescription}>Tell recruiters about your experience and the skills you bring.</p>
      <form onSubmit={onSubmit} aria-busy={saving}>
        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label htmlFor="profile-name">Full Name</label>
            <input type="text" id="profile-name" value={bio.name} onChange={(e) => onChange({ ...bio, name: e.target.value })} />
          </div>
          <div className={styles.formGroup}>
            <label htmlFor="profile-email">Email</label>
            <input type="email" id="profile-email" value={bio.email} onChange={(e) => onChange({ ...bio, email: e.target.value })} />
          </div>
        </div>

        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label htmlFor="profile-phone">Phone</label>
            <input type="tel" id="profile-phone" value={bio.phone} onChange={(e) => onChange({ ...bio, phone: e.target.value })} />
          </div>
          <div className={styles.formGroup}>
            <label htmlFor="profile-location">Location</label>
            <input type="text" id="profile-location" value={bio.location} onChange={(e) => onChange({ ...bio, location: e.target.value })} />
          </div>
        </div>

        <div className={styles.formGroup}>
          <label htmlFor="profile-title">Professional Title</label>
          <input type="text" id="profile-title" value={bio.title} onChange={(e) => onChange({ ...bio, title: e.target.value })} />
        </div>

        <div className={styles.formGroup}>
          <label htmlFor="profile-about">About Me</label>
          <textarea rows="4" id="profile-about" value={bio.about} onChange={(e) => onChange({ ...bio, about: e.target.value })}></textarea>
        </div>

        <div className={styles.formGroup}>
          <label htmlFor="profile-skills">Skills (comma-separated)</label>
          <input
            type="text"
            id="profile-skills" value={bio.skills.join(", ")}
            onChange={(e) => onChange({ ...bio, skills: e.target.value.split(",").map((s) => s.trim()) })}
          />
        </div>

        <button type="submit" className={styles.updateButton} disabled={saving}>
          {saving ? "Saving..." : "Update Profile"}
        </button>
      </form>
    </section>
  );
}

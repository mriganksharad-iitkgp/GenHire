import React from 'react';
import styles from '../../pages/RecruiterDashboard.module.css';

const ProfileForm = ({ companyProfile, isEditing, onChange, onSave, onCancel }) => (
  <div className={styles.profileForm}>
    <div className={styles.formRow}>
      <div className={styles.formGroup}>
        <label>Company Name</label>
        <input 
          type="text"
          value={companyProfile.companyName}
          onChange={(e) => onChange({...companyProfile, companyName: e.target.value})}
          disabled={!isEditing}
          className={!isEditing ? styles.disabledField : ''}
        />
      </div>
      <div className={styles.formGroup}>
        <label>Industry</label>
        <input 
          type="text"
          value={companyProfile.industry}
          onChange={(e) => onChange({...companyProfile, industry: e.target.value})}
          disabled={!isEditing}
          className={!isEditing ? styles.disabledField : ''}
        />
      </div>
    </div>

    <div className={styles.formRow}>
      <div className={styles.formGroup}>
        <label>Location</label>
        <input 
          type="text"
          value={companyProfile.location}
          onChange={(e) => onChange({...companyProfile, location: e.target.value})}
          disabled={!isEditing}
          className={!isEditing ? styles.disabledField : ''}
        />
      </div>
      <div className={styles.formGroup}>
        <label>Company Size</label>
        <select 
          value={companyProfile.size}
          onChange={(e) => onChange({...companyProfile, size: e.target.value})}
          disabled={!isEditing}
          className={!isEditing ? styles.disabledField : ''}
        >
          <option value="1-10 employees">1-10 employees</option>
          <option value="11-50 employees">11-50 employees</option>
          <option value="51-100 employees">51-100 employees</option>
          <option value="100-500 employees">100-500 employees</option>
          <option value="500+ employees">500+ employees</option>
        </select>
      </div>
    </div>

    <div className={styles.formGroup}>
      <label>Website</label>
      <input 
        type="url"
        value={companyProfile.website}
        onChange={(e) => onChange({...companyProfile, website: e.target.value})}
        disabled={!isEditing}
        className={!isEditing ? styles.disabledField : ''}
      />
    </div>

    <div className={styles.formGroup}>
      <label>Company Description</label>
      <textarea 
        value={companyProfile.description}
        onChange={(e) => onChange({...companyProfile, description: e.target.value})}
        rows="4"
        disabled={!isEditing}
        className={!isEditing ? styles.disabledField : ''}
      />
    </div>

    <div className={styles.formActions}>
      {isEditing ? (
        <>
          <button className={styles.primaryButton} onClick={onSave}>
            <i className="fa fa-save"></i> Save Changes
          </button>
          <button className={styles.secondaryButton} onClick={onCancel}>
            <i className="fa fa-times"></i> Cancel
          </button>
        </>
      ) : (
        <p style={{ color: '#666', margin: 0 }}>
          <i className="fa fa-info-circle"></i> Click "Edit Profile" to modify company information
        </p>
      )}
    </div>
  </div>
);

export default ProfileForm;

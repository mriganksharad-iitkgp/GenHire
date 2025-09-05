import React, { useState } from "react";
import styles from "../../pages/Profile.module.css";
import CVDetailsForm from "./CVDetailsForm";

export default function SidebarProfile({
  photoUrl,
  isUploadingPhoto,
  onPhotoSelected,
  cvFileName,
  cvPath,
  onViewCV,
  onCvFileChange,
  onUploadCv,
  uploadingCV,
  cvDetails,
  onSaveCvDetails,
  children,
}) {
  const [showCvDetailsForm, setShowCvDetailsForm] = useState(false);
  return (
    <div className={styles.sidebar}>
      <div className={styles.profilePicSection}>
        <div className={styles.profilePic}>
          <img src={photoUrl || "../android-chrome-192x192.png"} alt="Profile" />
        </div>
        <label className={styles.changePhotoBtn}>
          {isUploadingPhoto ? "Uploading..." : "Change Photo"}
          <input
            type="file"
            accept="image/*"
            onChange={onPhotoSelected}
            className={styles.hiddenInput}
            disabled={isUploadingPhoto}
          />
        </label>
      </div>

      <div className={styles.fileUploadBox}>
        <h3>CV Information</h3>
        
        {/* CV Upload Section */}
        <div className={styles.cvSection}>
          <h4><i className="fa fa-upload"></i> Upload CV File</h4>
          <form onSubmit={onUploadCv}>
            <div className={styles.fileCard}>
              <label className={styles.fileInputLabel}>
                <i className="fa fa-file-text" aria-hidden="true"></i>
                <span>Resume/CV</span>
                <input type="file" accept=".pdf,.docx" onChange={onCvFileChange} className={styles.hiddenInput} />
                <div className={styles.fileInfo}>{cvFileName || "No file selected"}</div>
              </label>
              {cvPath && (
                <div className={styles.fileInfo}>
                  <button type="button" onClick={onViewCV} className={styles.viewCVButton}>
                    View Uploaded CV
                  </button>
                </div>
              )}
            </div>
            <button type="submit" className={styles.uploadButton} disabled={uploadingCV}>
              {uploadingCV ? (
                "Uploading..."
              ) : (
                <>
                  <i className="fa fa-upload" aria-hidden="true"></i>
                  Upload CV
                </>
              )}
            </button>
          </form>
        </div>

        {/* CV Details Entry Section */}
        <div className={styles.cvSection}>
          <h4><i className="fa fa-edit"></i> CV Details Entry</h4>
          <p className={styles.sectionDescription}>
            Enter your details manually for AI-powered interview questions
          </p>
          <div className={styles.cvDetailsStatus}>
            {cvDetails ? (
              <div className={styles.detailsComplete}>
                <i className="fa fa-check-circle"></i>
                <span>CV details completed</span>
              </div>
            ) : (
              <div className={styles.detailsIncomplete}>
                <i className="fa fa-exclamation-circle"></i>
                <span>CV details not entered</span>
              </div>
            )}
          </div>
          <button 
            type="button" 
            onClick={() => setShowCvDetailsForm(true)} 
            className={styles.detailsButton}
          >
            <i className="fa fa-edit" aria-hidden="true"></i>
            {cvDetails ? "Edit CV Details" : "Enter CV Details"}
          </button>
        </div>
      </div>
      
      {showCvDetailsForm && (
        <CVDetailsForm
          existingData={cvDetails}
          onSave={async (formData) => {
            await onSaveCvDetails(formData);
            setShowCvDetailsForm(false);
          }}
          onClose={() => setShowCvDetailsForm(false)}
        />
      )}
  {children}
    </div>
  );
}

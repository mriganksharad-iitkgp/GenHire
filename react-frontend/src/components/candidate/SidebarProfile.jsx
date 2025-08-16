import React from "react";
import styles from "../../pages/Profile.module.css";

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
  children,
}) {
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
        <h3>CV Upload</h3>
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
  {children}
    </div>
  );
}

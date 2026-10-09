import React, { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import DeleteAccountModal from "shared/components/account/DeleteAccountModal";
import Toast from "shared/components/ui/Toast";
import PortalPageHeader from "shared/components/ui/PortalPageHeader";
import styles from "./Profile.module.css";
import SidebarProfile from "features/candidate/components/SidebarProfile";
import BioForm from "features/candidate/components/BioForm";
import IdentityCardUpload from "features/candidate/components/IdentityCardUpload";
import useCandidateProfile from "features/candidate/hooks/useCandidateProfile";
import useCandidateApplications from "features/candidate/hooks/useCandidateApplications";
import useCVPreview from "features/candidate/hooks/useCVPreview";

export default function Profile() {
  const [cvFile, setCvFile] = useState(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const showToast = useCallback((message, type = "info") => setToast({ message, type }), []);
  const { bio, setBio, profilePhotoUrl, cvPath, cvDetails, uploadingCV, uploadingPhoto, save, uploadCvFile, uploadProfilePhoto, saveCvDetails, loading, error:profileError, reload, saving } = useCandidateProfile(showToast);
  const { applications, loading:loadingApps, error:appsError } = useCandidateApplications(showToast);
  const { viewCV, preview } = useCVPreview();
	// Handle CV upload
	const handleCVUpload = async (e) => {
		e.preventDefault();
		if (!cvFile) {
			showToast("Please select a CV file.", "error");
			return;
		}
		const ok = await uploadCvFile(cvFile);
		if (ok) {
			setCvFile(null);
		}
	};

	// Handle photo upload
	const handlePhotoUpload = async (file) => {
		if (!file) return;
		await uploadProfilePhoto(file);
	};

	// Handle profile data update
	const handleProfileUpdate = async (e) => {
		e.preventDefault();
		const ok = await save();
		if (!ok) return;
	};

	// Handle CV details save
	const handleSaveCvDetails = async (formData) => {
		try {
			const success = await saveCvDetails(formData);
			if (success) {
				showToast('CV details saved successfully!', 'success');
			}
            return success;
		} catch (error) {
			console.error('Error saving CV details:', error);
			showToast('Failed to save CV details. Please try again.', 'error');
		}
	};


  const counts = [
    ["Total applications", applications.length],
    ["Awaiting review", applications.filter(app => app.statusKey === "pending").length],
    ["Shortlisted", applications.filter(app => app.statusKey === "shortlisted").length],
    ["Interviewed", applications.filter(app => app.statusKey === "interviewed").length],
    ["Screening cleared", applications.filter(app => app.statusKey === "screening_cleared").length],
    ["Not cleared", applications.filter(app => app.statusKey === "rejected").length],
  ];
  return <div className={styles.profileContainer}>
    <div className={styles.pageContent}>
      <PortalPageHeader title="My Profile" eyebrow="Your career profile" icon="fa-user" subtitle="Keep your personal details, CVs and identity information ready for your next opportunity." actions={<Link to="/applications">My Applications <i className="fa fa-arrow-right" aria-hidden="true" /></Link>} />
      <div className={styles.content}>
				<SidebarProfile
					photoUrl={profilePhotoUrl}
					isUploadingPhoto={uploadingPhoto}
					onPhotoSelected={(e) => {
						const file = e.target.files?.[0];
						if (file) handlePhotoUpload(file);
					}}
					cvFileName={cvFile ? cvFile.name : undefined}
					cvPath={cvPath}
					onViewCV={viewCV}
					onCvFileChange={(e) => setCvFile(e.target.files?.[0] || null)}
					onUploadCv={handleCVUpload}
					uploadingCV={uploadingCV}
					cvDetails={cvDetails}
					onSaveCvDetails={handleSaveCvDetails}
					showToast={showToast}
					onDeleteAccount={() => setIsDeleteModalOpen(true)}
 />
        <div className={styles.mainContent}>
          <section className={styles.statsCard} aria-label="Application statistics">
            <div className={styles.cardHeading}><h2>Application overview</h2><Link to="/applications">View applications</Link></div>
            {appsError ? <p role="status">Application statistics are currently unavailable.</p> : loadingApps && !applications.length ? <p role="status">Loading application statistics...</p> : <div className={styles.statsContainer}>{counts.map(([label, count]) => <div className={styles.statItem} key={label}><span className={styles.statNumber}>{count}</span><span className={styles.statLabel}>{label}</span></div>)}</div>}
          </section>
          {profileError ? <div role="alert" className={styles.loadingState}><p>{profileError}</p><button className={styles.primaryButton} onClick={reload}>Retry</button></div> : loading ? <p role="status" className={styles.loadingState}>Loading your personal details...</p> : <BioForm bio={bio} onChange={setBio} onSubmit={handleProfileUpdate} saving={saving} />}
          <IdentityCardUpload showToast={showToast} />
        </div>
      </div>
    </div>
    {preview}
    <DeleteAccountModal isOpen={isDeleteModalOpen} onClose={() => setIsDeleteModalOpen(false)} />
    {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
  </div>;
}

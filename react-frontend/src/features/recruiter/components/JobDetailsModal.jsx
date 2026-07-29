import React from "react";
import styles from "./JobDetailsModal.module.css";
import { companyLabel } from "shared/constants/company";

const JobDetailsModal = ({ isOpen, onClose, job, onEdit }) => {
	if (!isOpen || !job) return null;

	const getStatusInfo = (status) => {
		const statusMap = {
			draft: { color: '#6b7280', label: 'Draft', description: 'Job is being prepared' },
			active: { color: '#10b981', label: 'Active', description: 'Job is live and accepting applications' },
			paused: { color: '#f59e0b', label: 'Paused', description: 'Job is temporarily stopped' },
			closed: { color: '#ef4444', label: 'Closed', description: 'Job is closed, no longer accepting applications' }
		};
		const normalizedStatus = String(status || 'draft').toLowerCase();
		return statusMap[normalizedStatus] || statusMap.draft;
	};

	const formatDate = (dateString) => {
		if (!dateString) return 'Not specified';
		try {
			return new Date(dateString).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata',
				year: 'numeric',
				month: 'long',
				day: 'numeric'
			});
		} catch {
			return dateString;
		}
	};

	const statusInfo = getStatusInfo(job.status);

	return (
		<div className={styles.modalOverlay} onClick={onClose}>
			<div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
				{/* Gradient Header */}
				<div className={styles.modalHeader}>
					<div className={styles.headerContent}>
						<div className={styles.titleSection}>
							<h2><i className="fa fa-briefcase"></i> Job Details</h2>
							<span className={styles.subtitle}>Complete job information and statistics</span>
						</div>
						<div className={styles.headerActions}>
							<button 
								className={styles.editButton}
								onClick={() => onEdit && onEdit(job)}
								title="Edit this job"
							>
								<i className="fa fa-edit"></i>
							</button>
							<button className={styles.closeButton} onClick={onClose}>
								<i className="fa fa-times"></i>
							</button>
						</div>
					</div>
				</div>

				<div className={styles.modalBody}>
					{/* Job Title and Status */}
					<div className={styles.jobTitleSection}>
						<div className={styles.titleInfo}>
							<h1 className={styles.jobTitle}>{job.title}</h1>
							<div className={styles.companyInfo}>
								<span className={styles.companyName}>
									<i className="fa fa-building"></i>
									{companyLabel(job.company)}
								</span>
							</div>
						</div>
						<div className={styles.statusSection}>
							<div 
								className={styles.statusBadge}
								style={{ backgroundColor: statusInfo.color }}
							>
								<i className="fa fa-circle"></i>
								{statusInfo.label}
							</div>
							<small className={styles.statusDescription}>
								{statusInfo.description}
							</small>
						</div>
					</div>

					{/* Key Information Grid */}
					<div className={styles.keyInfoGrid}>
						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-sitemap"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Department</span>
								<span className={styles.infoValue}>{job.department}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-map-marker"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Location</span>
								<span className={styles.infoValue}>{job.location}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-clock-o"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Job Type</span>
								<span className={styles.infoValue}>{job.type}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-user-o"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Experience</span>
								<span className={styles.infoValue}>{job.experience}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-money"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Salary Range</span>
								<span className={styles.infoValue}>{job.salary}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-calendar"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Posted Date</span>
								<span className={styles.infoValue}>{formatDate(job.created_at)}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-calendar-check-o"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Application Deadline</span>
								<span className={styles.infoValue}>{formatDate(job.deadline)}</span>
							</div>
						</div>

						<div className={styles.infoCard}>
							<div className={styles.infoIcon}>
								<i className="fa fa-refresh"></i>
							</div>
							<div className={styles.infoContent}>
								<span className={styles.infoLabel}>Last Updated</span>
								<span className={styles.infoValue}>{formatDate(job.updated_at)}</span>
							</div>
						</div>
					</div>

					{/* Application Statistics */}
					<div className={styles.section}>
						<h3 className={styles.sectionTitle}>
							<i className="fa fa-bar-chart"></i>
							Application Statistics
						</h3>
						<div className={styles.statsGrid}>
							<div className={styles.statCard}>
								<div className={styles.statIcon}>
									<i className="fa fa-users"></i>
								</div>
								<div className={styles.statContent}>
									<div className={styles.statNumber}>{job.applicants || 0}</div>
									<div className={styles.statLabel}>Total Applicants</div>
								</div>
							</div>

							<div className={styles.statCard}>
								<div className={styles.statIcon}>
									<i className="fa fa-hourglass-half"></i>
								</div>
								<div className={styles.statContent}>
									<div className={styles.statNumber}>{job.pending || 0}</div>
									<div className={styles.statLabel}>Pending Review</div>
								</div>
							</div>

							<div className={styles.statCard}>
								<div className={styles.statIcon}>
									<i className="fa fa-comments"></i>
								</div>
								<div className={styles.statContent}>
									<div className={styles.statNumber}>{job.interviewed || 0}</div>
									<div className={styles.statLabel}>Interviewed</div>
								</div>
							</div>

							<div className={styles.statCard}>
								<div className={styles.statIcon}>
									<i className="fa fa-check-circle"></i>
								</div>
								<div className={styles.statContent}>
									<div className={styles.statNumber}>{job.screening_cleared ?? job.selected ?? 0}</div>
									<div className={styles.statLabel}>Screening Cleared</div>
								</div>
							</div>

							<div className={styles.statCard}>
								<div className={styles.statIcon}>
									<i className="fa fa-times-circle"></i>
								</div>
								<div className={styles.statContent}>
									<div className={styles.statNumber}>{job.rejected || 0}</div>
									<div className={styles.statLabel}>Rejected</div>
								</div>
							</div>
						</div>
					</div>

					{/* Job Description */}
					<div className={styles.section}>
						<h3 className={styles.sectionTitle}>
							<i className="fa fa-file-text-o"></i>
							Job Description
						</h3>
						<div className={styles.contentCard}>
							<p className={styles.description}>{job.description || 'No description provided.'}</p>
						</div>
					</div>

					{/* Skills Section */}
					{job.skills && job.skills.length > 0 && (
						<div className={styles.section}>
							<h3 className={styles.sectionTitle}>
								<i className="fa fa-cogs"></i>
								Required Skills
								<span className={styles.skillCount}>({job.skills.length})</span>
							</h3>
							<div className={styles.contentCard}>
								<div className={styles.skillsContainer}>
									{job.skills.map((skill, index) => (
										<span key={index} className={styles.skillTag}>
											<i className="fa fa-star"></i>
											{skill}
										</span>
									))}
								</div>
							</div>
						</div>
					)}

					{/* Responsibilities */}
					{job.responsibilities && job.responsibilities.length > 0 && (
						<div className={styles.section}>
							<h3 className={styles.sectionTitle}>
								<i className="fa fa-tasks"></i>
								Key Responsibilities
							</h3>
							<div className={styles.contentCard}>
								<ul className={styles.listItems}>
									{job.responsibilities.map((responsibility, index) => (
										<li key={index} className={styles.listItem}>
											<i className="fa fa-check"></i>
											{responsibility}
										</li>
									))}
								</ul>
							</div>
						</div>
					)}

					{/* Requirements */}
					{job.requirements && job.requirements.length > 0 && (
						<div className={styles.section}>
							<h3 className={styles.sectionTitle}>
								<i className="fa fa-graduation-cap"></i>
								Qualifications & Requirements
							</h3>
							<div className={styles.contentCard}>
								<ul className={styles.listItems}>
									{job.requirements.map((requirement, index) => (
										<li key={index} className={styles.listItem}>
											<i className="fa fa-circle"></i>
											{requirement}
										</li>
									))}
								</ul>
							</div>
						</div>
					)}

					{/* Benefits */}
					{job.benefits && job.benefits.length > 0 && (
						<div className={styles.section}>
							<h3 className={styles.sectionTitle}>
								<i className="fa fa-gift"></i>
								Benefits & Perks
							</h3>
							<div className={styles.contentCard}>
								<ul className={styles.listItems}>
									{job.benefits.map((benefit, index) => (
										<li key={index} className={styles.listItem}>
											<i className="fa fa-plus"></i>
											{benefit}
										</li>
									))}
								</ul>
							</div>
						</div>
					)}
				</div>

				{/* Enhanced Footer */}
				<div className={styles.modalFooter}>
					<div className={styles.footerContent}>
						<div className={styles.footerInfo}>
							<span className={styles.footerText}>
								<i className="fa fa-info-circle"></i>
								Last updated {formatDate(job.updated_at)}
							</span>
						</div>
						<div className={styles.footerActions}>
							<button className={styles.secondaryButton} onClick={onClose}>
								<i className="fa fa-arrow-left"></i>
								Back to Jobs
							</button>
							<button 
								className={styles.primaryButton}
								onClick={() => onEdit && onEdit(job)}
							>
								<i className="fa fa-edit"></i>
								Edit Job
							</button>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export default JobDetailsModal;

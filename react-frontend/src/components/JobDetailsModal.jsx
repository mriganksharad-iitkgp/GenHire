import React from "react";
import styles from "./JobDetailsModal.module.css";

const JobDetailsModal = ({ isOpen, onClose, job, onEdit }) => {
	if (!isOpen || !job) return null;

	const getStatusColor = (status) => {
		switch (status) {
			case "Active": return "#27ae60";
			case "Draft": return "#f39c12";
			case "Paused": return "#e74c3c";
			case "Closed": return "#95a5a6";
			default: return "#4a90e2";
		}
	};

	return (
		<div className={styles.modalOverlay} onClick={onClose}>
			<div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
				<div className={styles.modalHeader}>
					<h2>Job Details</h2>
					<button className={styles.closeButton} onClick={onClose}>
						<i className="fa fa-times"></i>
					</button>
				</div>

				<div className={styles.modalBody}>
					<div className={styles.jobTitleSection}>
						<h3>{job.title}</h3>
						<span 
							className={styles.statusBadge}
							style={{ backgroundColor: getStatusColor(job.status) }}
						>
							{job.status}
						</span>
					</div>

					<div className={styles.detailsGrid}>
						<div className={styles.detailItem}>
							<label><i className="fa fa-building"></i> Department</label>
							<span>{job.department}</span>
						</div>
						<div className={styles.detailItem}>
							<label><i className="fa fa-map-marker"></i> Location</label>
							<span>{job.location}</span>
						</div>
						<div className={styles.detailItem}>
							<label><i className="fa fa-clock-o"></i> Type</label>
							<span>{job.type}</span>
						</div>
						<div className={styles.detailItem}>
							<label><i className="fa fa-user"></i> Experience</label>
							<span>{job.experience}</span>
						</div>
						<div className={styles.detailItem}>
							<label><i className="fa fa-money"></i> Salary</label>
							<span>{job.salary}</span>
						</div>
						<div className={styles.detailItem}>
							<label><i className="fa fa-calendar"></i> Posted Date</label>
							<span>{job.postedDate}</span>
						</div>
						<div className={styles.detailItem}>
							<label><i className="fa fa-calendar-check-o"></i> Deadline</label>
							<span>{job.deadline}</span>
						</div>
					</div>

					<div className={styles.section}>
						<h4>Job Description</h4>
						<p>{job.description}</p>
					</div>

					<div className={styles.section}>
						<h4>Required Skills</h4>
						<div className={styles.skillsContainer}>
							{job.skills?.map((skill, index) => (
								<span key={index} className={styles.skillTag}>
									{skill}
								</span>
							))}
						</div>
					</div>

					<div className={styles.section}>
						<h4>Application Statistics</h4>
						<div className={styles.statsGrid}>
							<div className={styles.statCard}>
								<div className={styles.statNumber}>{job.applicants}</div>
								<div className={styles.statLabel}>Total Applicants</div>
							</div>
							<div className={styles.statCard}>
								<div className={styles.statNumber}>{job.interviewed}</div>
								<div className={styles.statLabel}>Interviewed</div>
							</div>
							<div className={styles.statCard}>
								<div className={styles.statNumber}>{job.selected}</div>
								<div className={styles.statLabel}>Selected</div>
							</div>
							<div className={styles.statCard}>
								<div className={styles.statNumber}>{job.rejected}</div>
								<div className={styles.statLabel}>Rejected</div>
							</div>
						</div>
					</div>
				</div>

				<div className={styles.modalFooter}>
					<button className={styles.secondaryButton} onClick={onClose}>
						Close
					</button>
					<button 
						className={styles.primaryButton}
						onClick={() => onEdit && onEdit(job)}
					>
						<i className="fa fa-edit"></i> Edit Job
					</button>
				</div>
			</div>
		</div>
	);
};

export default JobDetailsModal;

import React, { useState, useEffect } from "react";
import styles from "./JobEditModal.module.css";

const JobEditModal = ({ isOpen, onClose, job, onJobUpdate }) => {
	const [formData, setFormData] = useState({
		title: "",
		department: "",
		location: "",
		type: "Full-time",
		experience: "",
		salary: "",
		deadline: "",
		status: "Active",
		description: "",
		skills: [],
		responsibilities: [],
		requirements: [],
		benefits: []
	});

	const [skillInput, setSkillInput] = useState("");

	useEffect(() => {
		if (job) {
			setFormData({
				title: job.title || "",
				department: job.department || "",
				location: job.location || "",
				type: job.type || "Full-time",
				experience: job.experience || "",
				salary: job.salary || "",
				deadline: job.deadline || "",
				status: job.status || "Active",
				description: job.description || "",
				skills: job.skills || [],
				responsibilities: job.responsibilities || [],
				requirements: job.requirements || [],
				benefits: job.benefits || []
			});
		}
	}, [job]);

	if (!isOpen || !job) return null;

	const handleInputChange = (e) => {
		const { name, value } = e.target;
		setFormData(prev => ({
			...prev,
			[name]: value
		}));
	};

	const handleAddSkill = () => {
		if (skillInput.trim() && !formData.skills.includes(skillInput.trim())) {
			setFormData(prev => ({
				...prev,
				skills: [...prev.skills, skillInput.trim()]
			}));
			setSkillInput("");
		}
	};

	const handleRemoveSkill = (skillToRemove) => {
		setFormData(prev => ({
			...prev,
			skills: prev.skills.filter(skill => skill !== skillToRemove)
		}));
	};

	const handleSubmit = (e) => {
		e.preventDefault();
		
		// Validate required fields
		if (!formData.title || !formData.department || !formData.location) {
			alert("Please fill in all required fields");
			return;
		}

		// Update the job
		const normalize = (v) => Array.isArray(v) ? v : String(v || '').replace(/\r/g,'').split('\n').map(s => s.trim()).filter(Boolean);
		const updatedJob = {
			...job,
			...formData,
			responsibilities: normalize(formData.responsibilities),
			requirements: normalize(formData.requirements),
			benefits: normalize(formData.benefits),
		};

		onJobUpdate(updatedJob);
		onClose();
	};

	const handleKeyPress = (e) => {
		if (e.key === "Enter" && e.target.name === "skillInput") {
			e.preventDefault();
			handleAddSkill();
		}
		if (e.key === "Escape") {
			onClose();
		}
	};

	return (
		<div className={styles.modalOverlay} onClick={onClose}>
			<div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
				<div className={styles.modalHeader}>
					<h2>Edit Job Posting</h2>
					<button className={styles.closeButton} onClick={onClose}>
						<i className="fa fa-times"></i>
					</button>
				</div>

				<form onSubmit={handleSubmit} className={styles.modalBody}>
					<div className={styles.formRow}>
						<div className={styles.formGroup}>
							<label htmlFor="title">Job Title *</label>
							<input
								type="text"
								id="title"
								name="title"
								value={formData.title}
								onChange={handleInputChange}
								onKeyPress={handleKeyPress}
								required
							/>
						</div>
						<div className={styles.formGroup}>
							<label htmlFor="department">Department *</label>
							<input
								type="text"
								id="department"
								name="department"
								value={formData.department}
								onChange={handleInputChange}
								onKeyPress={handleKeyPress}
								required
							/>
						</div>
					</div>

					<div className={styles.formRow}>
						<div className={styles.formGroup}>
							<label htmlFor="location">Location *</label>
							<input
								type="text"
								id="location"
								name="location"
								value={formData.location}
								onChange={handleInputChange}
								onKeyPress={handleKeyPress}
								required
							/>
						</div>
						<div className={styles.formGroup}>
							<label htmlFor="type">Employment Type</label>
							<select
								id="type"
								name="type"
								value={formData.type}
								onChange={handleInputChange}
							>
								<option value="Full-time">Full-time</option>
								<option value="Part-time">Part-time</option>
								<option value="Contract">Contract</option>
								<option value="Internship">Internship</option>
							</select>
						</div>
					</div>

					<div className={styles.formRow}>
						<div className={styles.formGroup}>
							<label htmlFor="experience">Experience Required</label>
							<input
								type="text"
								id="experience"
								name="experience"
								value={formData.experience}
								onChange={handleInputChange}
								onKeyPress={handleKeyPress}
								placeholder="e.g., 3-5 years"
							/>
						</div>
						<div className={styles.formGroup}>
							<label htmlFor="salary">Salary Range</label>
							<input
								type="text"
								id="salary"
								name="salary"
								value={formData.salary}
								onChange={handleInputChange}
								onKeyPress={handleKeyPress}
								placeholder="e.g., $80,000 - $120,000"
							/>
						</div>
					</div>

					<div className={styles.formRow}>
						<div className={styles.formGroup}>
							<label htmlFor="deadline">Application Deadline</label>
							<input
								type="date"
								id="deadline"
								name="deadline"
								value={formData.deadline}
								onChange={handleInputChange}
							/>
						</div>
						<div className={styles.formGroup}>
							<label htmlFor="status">Status</label>
							<select
								id="status"
								name="status"
								value={formData.status}
								onChange={handleInputChange}
							>
								<option value="Active">Active</option>
								<option value="Draft">Draft</option>
								<option value="Paused">Paused</option>
								<option value="Closed">Closed</option>
							</select>
						</div>
					</div>

					<div className={styles.formGroup}>
						<label htmlFor="description">Job Description</label>
						<textarea
							id="description"
							name="description"
							rows="6"
							value={formData.description}
							onChange={handleInputChange}
							placeholder="Describe the role, responsibilities, and requirements..."
						></textarea>
					</div>

					<div className={styles.formGroup}>
						<label htmlFor="responsibilities">Key Responsibilities</label>
						<textarea
							id="responsibilities"
							name="responsibilities"
							rows="4"
							value={Array.isArray(formData.responsibilities) ? formData.responsibilities.join('\n') : formData.responsibilities}
							onChange={handleInputChange}
							placeholder="One per line"
						></textarea>
					</div>

					<div className={styles.formGroup}>
						<label htmlFor="requirements">Requirements</label>
						<textarea
							id="requirements"
							name="requirements"
							rows="4"
							value={Array.isArray(formData.requirements) ? formData.requirements.join('\n') : formData.requirements}
							onChange={handleInputChange}
							placeholder="One per line"
						></textarea>
					</div>

					<div className={styles.formGroup}>
						<label htmlFor="benefits">Benefits</label>
						<textarea
							id="benefits"
							name="benefits"
							rows="3"
							value={Array.isArray(formData.benefits) ? formData.benefits.join('\n') : formData.benefits}
							onChange={handleInputChange}
							placeholder="One per line"
						></textarea>
					</div>

					<div className={styles.formGroup}>
						<label htmlFor="skills">Required Skills</label>
						<div className={styles.skillsInput}>
							<input
								type="text"
								name="skillInput"
								value={skillInput}
								onChange={(e) => setSkillInput(e.target.value)}
								onKeyPress={handleKeyPress}
								placeholder="Add a skill and press Enter"
							/>
							<button 
								type="button" 
								onClick={handleAddSkill}
								className={styles.addSkillButton}
							>
								Add
							</button>
						</div>
						<div className={styles.skillsContainer}>
							{formData.skills.map((skill, index) => (
								<span key={index} className={styles.skillTag}>
									{skill}
									<button 
										type="button"
										onClick={() => handleRemoveSkill(skill)}
										className={styles.removeSkillButton}
									>
										×
									</button>
								</span>
							))}
						</div>
					</div>

					<div className={styles.modalFooter}>
						<button type="button" className={styles.secondaryButton} onClick={onClose}>
							Cancel
						</button>
						<button type="submit" className={styles.primaryButton}>
							<i className="fa fa-save"></i> Update Job
						</button>
					</div>
				</form>
			</div>
		</div>
	);
};

export default JobEditModal;

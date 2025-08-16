import React, { useState, useEffect } from 'react';
import styles from './JobCreationModal.module.css';

const JobCreationModal = ({ isOpen, onClose, onJobCreate }) => {
  const [jobData, setJobData] = useState({
    title: '',
    department: '',
    location: '',
    type: 'Full-time',
    experience: '',
    salary: '',
    deadline: '',
    skills: '',
    description: '',
  responsibilities: '',
  requirements: '',
  benefits: ''
  });

  const [isSubmitting, setIsSubmitting] = useState(false);

  // Handle Escape key to close modal
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        handleCancel();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      // Prevent background scrolling
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setJobData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Basic validation
    if (!jobData.title.trim() || !jobData.department.trim() || !jobData.location.trim()) {
      alert('Please fill in all required fields');
      return;
    }

    setIsSubmitting(true);

    // Simulate API call
    setTimeout(() => {
  const newJob = {
        id: Date.now(), // In real app, this would come from backend
        ...jobData,
        status: 'Draft',
        postedDate: new Date().toISOString().split('T')[0],
        applicants: 0,
        interviewed: 0,
        selected: 0,
        rejected: 0,
        pending: 0,
  skills: jobData.skills.split(',').map(skill => skill.trim()).filter(skill => skill)
      };

      onJobCreate(newJob);
      setIsSubmitting(false);
      
      // Reset form
      setJobData({
        title: '',
        department: '',
        location: '',
        type: 'Full-time',
        experience: '',
        salary: '',
        deadline: '',
        skills: '',
        description: '',
        responsibilities: '',
        requirements: '',
        benefits: ''
      });
      
      onClose();
    }, 1000);
  };

  const handleCancel = () => {
    // Reset form
    setJobData({
      title: '',
      department: '',
      location: '',
      type: 'Full-time',
      experience: '',
      salary: '',
      deadline: '',
      skills: '',
      description: '',
      responsibilities: '',
      requirements: '',
      benefits: ''
    });
    onClose();
  };

  if (!isOpen) return null;

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      handleCancel();
    }
  };

  return (
    <div className={styles.modalOverlay} onClick={handleOverlayClick}>
      <div className={styles.modalContent}>
        <div className={styles.modalHeader}>
          <h2>Create New Job Posting</h2>
          <button className={styles.closeButton} onClick={handleCancel}>
            <i className="fa fa-times"></i>
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.jobForm}>
          <div className={styles.formGrid}>
            <div className={styles.formGroup}>
              <label>Job Title *</label>
              <input
                type="text"
                name="title"
                value={jobData.title}
                onChange={handleInputChange}
                required
                placeholder="e.g. Senior Software Engineer"
              />
            </div>

            <div className={styles.formGroup}>
              <label>Department *</label>
              <input
                type="text"
                name="department"
                value={jobData.department}
                onChange={handleInputChange}
                required
                placeholder="e.g. Engineering"
              />
            </div>

            <div className={styles.formGroup}>
              <label>Location *</label>
              <input
                type="text"
                name="location"
                value={jobData.location}
                onChange={handleInputChange}
                required
                placeholder="e.g. San Francisco, CA (Remote)"
              />
            </div>

            <div className={styles.formGroup}>
              <label>Job Type *</label>
              <select
                name="type"
                value={jobData.type}
                onChange={handleInputChange}
                required
              >
                <option value="Full-time">Full-time</option>
                <option value="Part-time">Part-time</option>
                <option value="Contract">Contract</option>
                <option value="Internship">Internship</option>
              </select>
            </div>

            <div className={styles.formGroup}>
              <label>Experience Required *</label>
              <input
                type="text"
                name="experience"
                value={jobData.experience}
                onChange={handleInputChange}
                required
                placeholder="e.g. 3+ years"
              />
            </div>

            <div className={styles.formGroup}>
              <label>Salary Range *</label>
              <input
                type="text"
                name="salary"
                value={jobData.salary}
                onChange={handleInputChange}
                required
                placeholder="e.g. $80,000 - $120,000"
              />
            </div>

            <div className={styles.formGroup}>
              <label>Application Deadline *</label>
              <input
                type="date"
                name="deadline"
                value={jobData.deadline}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label>Required Skills *</label>
              <input
                type="text"
                name="skills"
                value={jobData.skills}
                onChange={handleInputChange}
                required
                placeholder="e.g. React, Node.js, MongoDB (comma-separated)"
              />
            </div>
          </div>

          <div className={styles.formGroup}>
            <label>Job Description *</label>
            <textarea
              name="description"
              value={jobData.description}
              onChange={handleInputChange}
              required
              rows="4"
              placeholder="Brief description of the role and company..."
            />
          </div>

          <div className={styles.formGroup}>
            <label>Key Responsibilities</label>
            <textarea
              name="responsibilities"
              value={jobData.responsibilities}
              onChange={handleInputChange}
              rows="4"
              placeholder="List key responsibilities (one per line)"
            />
          </div>

          <div className={styles.formGroup}>
            <label>Requirements</label>
            <textarea
              name="requirements"
              value={jobData.requirements}
              onChange={handleInputChange}
              rows="4"
              placeholder="List requirements and qualifications (one per line)"
            />
          </div>

          <div className={styles.formGroup}>
            <label>Benefits</label>
            <textarea
              name="benefits"
              value={jobData.benefits}
              onChange={handleInputChange}
              rows="3"
              placeholder="List benefits/perks (one per line)"
            />
          </div>

          <div className={styles.formActions}>
            <button
              type="button"
              className={styles.cancelButton}
              onClick={handleCancel}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.submitButton}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <i className="fa fa-spinner fa-spin"></i> Creating...
                </>
              ) : (
                <>
                  <i className="fa fa-plus"></i> Create Job
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default JobCreationModal;

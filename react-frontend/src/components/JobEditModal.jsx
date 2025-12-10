import React, { useState, useEffect, useRef } from 'react';
import styles from './JobEditModal.module.css';

// Predefined data for auto-suggestions
const COMMON_SKILLS = [
  // Technical Skills
  'JavaScript', 'Python', 'Java', 'C++', 'TypeScript', 'Go', 'Rust', 'Swift',
  'React', 'Vue.js', 'Angular', 'Node.js', 'Express', 'Django', 'Flask', 'Spring',
  'MongoDB', 'PostgreSQL', 'MySQL', 'Redis', 'Elasticsearch', 'GraphQL', 'REST API',
  'AWS', 'Azure', 'Google Cloud', 'Docker', 'Kubernetes', 'Jenkins', 'Git', 'CI/CD',
  'Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch', 'Pandas', 'NumPy',
  'Data Analysis', 'SQL', 'Power BI', 'Tableau', 'Excel', 'Statistics',
  // Design Skills
  'Figma', 'Sketch', 'Adobe Creative Suite', 'Photoshop', 'Illustrator', 'InDesign',
  'User Research', 'Prototyping', 'Wireframing', 'Design Systems', 'UI/UX Design',
  // Business Skills
  'Product Management', 'Project Management', 'Agile', 'Scrum', 'Kanban',
  'Market Research', 'Business Analysis', 'Strategy', 'Leadership', 'Communication',
  'Data-driven Decision Making', 'Customer Success', 'Sales', 'Marketing'
];

const DEPARTMENTS = [
  'Engineering', 'Product', 'Design', 'Data & Analytics', 'Marketing', 'Sales',
  'Customer Success', 'Operations', 'Finance', 'Human Resources', 'Legal',
  'Security', 'DevOps', 'Quality Assurance', 'Research & Development'
];

const LOCATIONS = [
  'Remote', 'Bangalore, Karnataka', 'Mumbai, Maharashtra', 'Delhi, NCR', 'Hyderabad, Telangana',
  'Chennai, Tamil Nadu', 'Pune, Maharashtra', 'Kolkata, West Bengal', 'Ahmedabad, Gujarat', 'Gurgaon, Haryana',
  'Noida, Uttar Pradesh', 'Kochi, Kerala', 'Indore, Madhya Pradesh', 'Jaipur, Rajasthan',
  'Remote (India)', 'Remote (Global)', 'Hybrid - Bangalore', 'Hybrid - Mumbai', 'Hybrid - Delhi'
];

const EXPERIENCE_LEVELS = [
  'Entry Level (0-1 years)', '1-2 years', '2-4 years', '3-5 years', 
  '4-6 years', '5-7 years', '6-8 years', '7+ years', '10+ years'
];

const SALARY_RANGES = [
  '₹3,00,000 - ₹5,00,000', '₹5,00,000 - ₹8,00,000', '₹8,00,000 - ₹12,00,000', '₹12,00,000 - ₹18,00,000',
  '₹18,00,000 - ₹25,00,000', '₹25,00,000 - ₹35,00,000', '₹35,00,000 - ₹50,00,000', '₹50,00,000 - ₹75,00,000',
  '₹75,00,000 - ₹1,00,00,000', '₹1,00,00,000 - ₹1,50,00,000', '₹1,50,00,000 - ₹2,00,00,000', '₹2,00,00,000+'
];

// Job status workflow with one-way progression
const JOB_STATUSES = [
  { value: 'draft', label: 'Draft', description: 'Job is being prepared', color: '#6b7280' },
  { value: 'active', label: 'Active', description: 'Job is live and accepting applications', color: '#10b981' },
  { value: 'paused', label: 'Paused', description: 'Job is temporarily stopped', color: '#f59e0b' },
  { value: 'closed', label: 'Closed', description: 'Job is closed, no longer accepting applications', color: '#ef4444' }
];

const JobEditModal = ({ isOpen, onClose, onJobUpdate, jobData: initialJobData }) => {
  // Helper function to convert list fields to array
  const toArray = (val) => {
    if (!val) return [];
    if (Array.isArray(val)) return val;
    if (typeof val === 'string') {
      return val.split('\n').filter(item => item.trim());
    }
    return [];
  };

  // Helper function to convert array to string for text areas
  const toString = (val) => {
    if (!val) return '';
    if (Array.isArray(val)) return val.join('\n');
    return String(val);
  };

  // Get available status options based on current status
  const getAvailableStatuses = (currentStatus) => {
    const statusHierarchy = { 'draft': 0, 'active': 1, 'paused': 2, 'closed': 3 };
    const currentLevel = statusHierarchy[currentStatus] || 0;
    return JOB_STATUSES.filter(status => statusHierarchy[status.value] >= currentLevel);
  };

  const [jobData, setJobData] = useState({
    title: '',
    department: '',
    location: '',
    type: 'Full-time',
    experience: '',
    salary: '',
    deadline: '',
    skills: [],
    description: '',
    responsibilities: '',
    requirements: '',
    benefits: '',
    status: 'draft',
    minimum_cv_score: 50
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [skillInput, setSkillInput] = useState('');
  const [filteredSuggestions, setFilteredSuggestions] = useState([]);
  
  const dropdownRefs = {
    department: useRef(null),
    location: useRef(null),
    experience: useRef(null),
    salary: useRef(null),
    skills: useRef(null),
    status: useRef(null)
  };

  // Initialize job data when modal opens or initialJobData changes
  useEffect(() => {
    if (isOpen && initialJobData) {
      setJobData({
        title: initialJobData.title || '',
        department: initialJobData.department || '',
        location: initialJobData.location || '',
        type: initialJobData.type || 'Full-time',
        experience: initialJobData.experience || '',
        salary: initialJobData.salary || '',
        deadline: initialJobData.deadline || '',
        skills: toArray(initialJobData.skills),
        description: initialJobData.description || '',
        responsibilities: toString(initialJobData.responsibilities),
        requirements: toString(initialJobData.requirements),
        benefits: toString(initialJobData.benefits),
        status: initialJobData.status || 'draft',
        minimum_cv_score: initialJobData?.minimum_cv_score || 50
      });
    }
  }, [isOpen, initialJobData]);

  // Auto-suggestion filtering
  useEffect(() => {
    if (skillInput.trim()) {
      const filtered = COMMON_SKILLS.filter(skill =>
        skill.toLowerCase().includes(skillInput.toLowerCase()) &&
        !jobData.skills.includes(skill)
      ).slice(0, 8);
      setFilteredSuggestions(filtered);
    } else {
      setFilteredSuggestions([]);
    }
  }, [skillInput, jobData.skills]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      const isClickInsideAnyDropdown = Object.values(dropdownRefs).some(
        ref => ref.current && ref.current.contains(event.target)
      );
      if (!isClickInsideAnyDropdown) {
        setActiveDropdown(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Handle skill addition
  const addSkill = (skill) => {
    if (skill && !jobData.skills.includes(skill)) {
      setJobData(prev => ({
        ...prev,
        skills: [...prev.skills, skill]
      }));
      setSkillInput('');
      setFilteredSuggestions([]);
    }
  };

  // Handle skill removal
  const removeSkill = (skillToRemove) => {
    setJobData(prev => ({
      ...prev,
      skills: prev.skills.filter(skill => skill !== skillToRemove)
    }));
  };

  // Handle skill input key press
  const handleSkillKeyPress = (e) => {
    if (e.key === 'Enter' && skillInput.trim()) {
      e.preventDefault();
      addSkill(skillInput.trim());
    } else if (e.key === 'Backspace' && !skillInput && jobData.skills.length > 0) {
      removeSkill(jobData.skills[jobData.skills.length - 1]);
    }
  };

  // Handle Escape key to close modal
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        handleCancel();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!jobData.title.trim()) {
      alert('Please enter a job title');
      return;
    }

    setIsSubmitting(true);
    
    try {
      await onJobUpdate({
        _id: initialJobData?._id || initialJobData?.id, // Include the job ID
        ...jobData,
        skills: jobData.skills,
        responsibilities: jobData.responsibilities.split('\n').filter(item => item.trim()),
        requirements: jobData.requirements.split('\n').filter(item => item.trim()),
        benefits: jobData.benefits.split('\n').filter(item => item.trim()),
        status: jobData.status
      });
      
      onClose();
    } catch (error) {
      console.error('Error updating job:', error);
      alert('Failed to update job. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle input changes
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setJobData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Handle cancel
  const handleCancel = () => {
    if (window.confirm('Are you sure you want to cancel? All unsaved changes will be lost.')) {
      onClose();
    }
  };

  // Get dropdown suggestions
  const getDropdownSuggestions = (type) => {
    switch (type) {
      case 'department':
        return DEPARTMENTS;
      case 'location':
        return LOCATIONS;
      case 'experience':
        return EXPERIENCE_LEVELS;
      case 'salary':
        return SALARY_RANGES;
      case 'status':
        return getAvailableStatuses(jobData.status);
      default:
        return [];
    }
  };

  // Handle dropdown selection
  const handleDropdownSelect = (type, value) => {
    setJobData(prev => ({
      ...prev,
      [type]: value
    }));
    setActiveDropdown(null);
  };

  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalContent}>
        <div className={styles.modalHeader}>
          <h2>✏️ Edit Job Details</h2>
          <button onClick={handleCancel} className={styles.closeButton}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.jobForm}>
          {/* Form Grid */}
          <div className={styles.formGrid}>
            {/* Job Title */}
            <div className={styles.formGroup}>
              <label>
                Job Title
              </label>
              <input
                type="text"
                name="title"
                value={jobData.title}
                onChange={handleInputChange}
                placeholder="e.g., Senior Software Engineer"
                className={styles.smartInput}
                required
              />
            </div>

            {/* Department */}
            <div className={styles.formGroup} ref={dropdownRefs.department}>
              <label>
                Department
              </label>
              <div className={styles.inputWithDropdown}>
                <input
                  type="text"
                  name="department"
                  value={jobData.department}
                  onChange={handleInputChange}
                  onFocus={() => setActiveDropdown('department')}
                  placeholder="e.g., Engineering, Product, Design"
                  className={styles.smartInput}
                />
                <button
                  type="button"
                  onClick={() => setActiveDropdown(activeDropdown === 'department' ? null : 'department')}
                  className={styles.dropdownToggle}
                >
                  ▼
                </button>
                {activeDropdown === 'department' && (
                  <div className={styles.suggestionDropdown}>
                    {getDropdownSuggestions('department').map((option, index) => (
                      <div
                        key={index}
                        className={styles.suggestionItem}
                        onClick={() => handleDropdownSelect('department', option)}
                      >
                        {option}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Location */}
            <div className={styles.formGroup} ref={dropdownRefs.location}>
              <label>
                Location
              </label>
              <div className={styles.inputWithDropdown}>
                <input
                  type="text"
                  name="location"
                  value={jobData.location}
                  onChange={handleInputChange}
                  onFocus={() => setActiveDropdown('location')}
                  placeholder="e.g., Remote, San Francisco, New York"
                  className={styles.smartInput}
                />
                <button
                  type="button"
                  onClick={() => setActiveDropdown(activeDropdown === 'location' ? null : 'location')}
                  className={styles.dropdownToggle}
                >
                  ▼
                </button>
                {activeDropdown === 'location' && (
                  <div className={styles.suggestionDropdown}>
                    {getDropdownSuggestions('location').map((option, index) => (
                      <div
                        key={index}
                        className={styles.suggestionItem}
                        onClick={() => handleDropdownSelect('location', option)}
                      >
                        {option}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Job Type */}
            <div className={styles.formGroup}>
              <label>Job Type</label>
              <select
                name="type"
                value={jobData.type}
                onChange={handleInputChange}
                className={styles.smartInput}
              >
                <option value="Full-time">Full-time</option>
                <option value="Part-time">Part-time</option>
                <option value="Contract">Contract</option>
                <option value="Internship">Internship</option>
              </select>
            </div>

            {/* Experience */}
            <div className={styles.formGroup} ref={dropdownRefs.experience}>
              <label>
                Experience Level
              </label>
              <div className={styles.inputWithDropdown}>
                <input
                  type="text"
                  name="experience"
                  value={jobData.experience}
                  onChange={handleInputChange}
                  onFocus={() => setActiveDropdown('experience')}
                  placeholder="e.g., 2-4 years, Entry level"
                  className={styles.smartInput}
                />
                <button
                  type="button"
                  onClick={() => setActiveDropdown(activeDropdown === 'experience' ? null : 'experience')}
                  className={styles.dropdownToggle}
                >
                  ▼
                </button>
                {activeDropdown === 'experience' && (
                  <div className={styles.suggestionDropdown}>
                    {getDropdownSuggestions('experience').map((option, index) => (
                      <div
                        key={index}
                        className={styles.suggestionItem}
                        onClick={() => handleDropdownSelect('experience', option)}
                      >
                        {option}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Salary */}
            <div className={styles.formGroup} ref={dropdownRefs.salary}>
              <label>
                Salary Range
              </label>
              <div className={styles.inputWithDropdown}>
                <input
                  type="text"
                  name="salary"
                  value={jobData.salary}
                  onChange={handleInputChange}
                  onFocus={() => setActiveDropdown('salary')}
                  placeholder="e.g., $80,000 - $120,000"
                  className={styles.smartInput}
                />
                <button
                  type="button"
                  onClick={() => setActiveDropdown(activeDropdown === 'salary' ? null : 'salary')}
                  className={styles.dropdownToggle}
                >
                  ▼
                </button>
                {activeDropdown === 'salary' && (
                  <div className={styles.suggestionDropdown}>
                    {getDropdownSuggestions('salary').map((option, index) => (
                      <div
                        key={index}
                        className={styles.suggestionItem}
                        onClick={() => handleDropdownSelect('salary', option)}
                      >
                        {option}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Job Status */}
            <div className={styles.formGroup} ref={dropdownRefs.status}>
              <label>
                Job Status
              </label>
              <div className={styles.statusContainer}>
                <select
                  name="status"
                  value={jobData.status}
                  onChange={handleInputChange}
                  className={`${styles.smartInput} ${styles.statusSelect}`}
                  style={{
                    borderLeft: `4px solid ${JOB_STATUSES.find(s => s.value === jobData.status)?.color || '#6b7280'}`,
                  }}
                >
                  {getAvailableStatuses(jobData.status).map((status) => (
                    <option key={status.value} value={status.value}>
                      {status.label} - {status.description}
                    </option>
                  ))}
                </select>
                <div className={styles.statusInfo}>
                  <small style={{ color: JOB_STATUSES.find(s => s.value === jobData.status)?.color }}>
                    {JOB_STATUSES.find(s => s.value === jobData.status)?.description}
                  </small>
                </div>
              </div>
            </div>

            {/* Minimum CV Score */}
            <div className={styles.formGroup}>
              <label>
                Minimum CV Score
              </label>
              <input
                type="number"
                name="minimum_cv_score"
                value={jobData.minimum_cv_score}
                onChange={handleInputChange}
                min="0"
                max="100"
                step="1"
                className={styles.smartInput}
              />
              <div className={styles.helpText}>
                Applications with CV scores ≥ this threshold will be automatically shortlisted. Changes affect new applications only.
              </div>
            </div>

          </div>

          {/* Skills Section */}
          <div className={styles.formGroup} ref={dropdownRefs.skills}>
            <label>
              Required Skills
            </label>
            <div className={styles.skillsContainer}>
              <div className={styles.skillTags}>
                {jobData.skills.map((skill, index) => (
                  <span key={index} className={styles.skillTag}>
                    {skill}
                    <button
                      type="button"
                      onClick={() => removeSkill(skill)}
                      className={styles.removeSkill}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <input
                type="text"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={handleSkillKeyPress}
                placeholder="Type to add skills..."
                className={styles.skillInput}
              />
              {filteredSuggestions.length > 0 && (
                <div className={styles.suggestionDropdown}>
                  {filteredSuggestions.map((skill, index) => (
                    <div
                      key={index}
                      className={styles.suggestionItem}
                      onClick={() => addSkill(skill)}
                    >
                      {skill}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Description */}
          <div className={styles.formGroup}>
            <label>
              Job Description
            </label>
            <textarea
              name="description"
              value={jobData.description}
              onChange={handleInputChange}
              placeholder="Describe the role, team, and what makes this opportunity exciting..."
              className={styles.smartTextarea}
              rows="4"
            />
          </div>

          {/* Responsibilities */}
          <div className={styles.formGroup}>
            <label>
              Key Responsibilities
            </label>
            <textarea
              name="responsibilities"
              value={jobData.responsibilities}
              onChange={handleInputChange}
              placeholder="Enter each responsibility on a new line..."
              className={styles.smartTextarea}
              rows="4"
            />
          </div>

          {/* Requirements */}
          <div className={styles.formGroup}>
            <label>
              Requirements
            </label>
            <textarea
              name="requirements"
              value={jobData.requirements}
              onChange={handleInputChange}
              placeholder="Enter each requirement on a new line..."
              className={styles.smartTextarea}
              rows="4"
            />
          </div>

          {/* Benefits */}
          <div className={styles.formGroup}>
            <label>
              Benefits & Perks
            </label>
            <textarea
              name="benefits"
              value={jobData.benefits}
              onChange={handleInputChange}
              placeholder="Enter each benefit on a new line..."
              className={styles.smartTextarea}
              rows="3"
            />
          </div>

          {/* Form Actions */}
          <div className={styles.formActions}>
            <button
              type="button"
              onClick={handleCancel}
              className={styles.cancelButton}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.updateButton}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <span className={styles.spinner}></span>
                  Updating...
                </>
              ) : (
                <>
                   Update Job
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default JobEditModal;
import { PROCTORING_OPTIONS } from "shared/constants/proctoringOptions";
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { generateJobWithAI } from 'shared/api/endpoints';
import { INDIA_LOCATION_OPTIONS } from 'shared/constants/jobTaxonomy';
import styles from './JobForm.module.css';

// Predefined data for auto-suggestions
const JOB_TEMPLATES = {
  'Software Engineer': {
    department: 'Engineering',
    skills: ['JavaScript', 'React', 'Node.js', 'MongoDB', 'Git'],
    experience: '2-4 years',
    salary: '₹12,00,000 - ₹18,00,000',
    description: 'We are seeking a talented Software Engineer to join our dynamic development team. You will be responsible for building scalable web applications and contributing to our product development lifecycle.',
    responsibilities: [
      'Develop and maintain web applications using modern technologies',
      'Collaborate with cross-functional teams to design and implement new features',
      'Write clean, maintainable, and well-documented code',
      'Participate in code reviews and maintain coding standards',
      'Debug and resolve technical issues'
    ],
    requirements: [
      'Bachelor\'s degree in Computer Science or related field',
      'Proficiency in JavaScript and modern frameworks',
      'Experience with database systems and API development',
      'Strong problem-solving and analytical skills',
      'Excellent communication and teamwork abilities'
    ],
    benefits: [
      'Competitive salary and equity options',
      'Health, dental, and vision insurance',
      'Flexible working hours and remote work options',
      'Professional development opportunities',
      'Modern office environment with latest tools'
    ]
  },
  'Data Scientist': {
    department: 'Data & Analytics',
    skills: ['Python', 'SQL', 'Machine Learning', 'TensorFlow', 'Pandas', 'Jupyter'],
    experience: '3-5 years',
    salary: '₹18,00,000 - ₹25,00,000',
    description: 'Join our data science team to extract insights from large datasets and build predictive models that drive business decisions.',
    responsibilities: [
      'Analyze large datasets to identify trends and patterns',
      'Build and deploy machine learning models',
      'Create data visualizations and reports for stakeholders',
      'Collaborate with engineering teams to implement ML solutions',
      'Stay updated with latest ML techniques and tools'
    ],
    requirements: [
      'Master\'s degree in Data Science, Statistics, or related field',
      'Strong programming skills in Python and SQL',
      'Experience with ML frameworks and statistical analysis',
      'Knowledge of data visualization tools',
      'Strong analytical and problem-solving skills'
    ],
    benefits: [
      'Competitive compensation package',
      'Access to cutting-edge ML tools and platforms',
      'Conference and training budget',
      'Collaborative research environment',
      'Opportunity to work on high-impact projects'
    ]
  },
  'Product Manager': {
    department: 'Product',
    skills: ['Product Strategy', 'Agile', 'Analytics', 'User Research', 'Roadmap Planning'],
    experience: '4-6 years',
    salary: '₹25,00,000 - ₹35,00,000',
    description: 'Lead product development initiatives and work cross-functionally to deliver exceptional user experiences.',
    responsibilities: [
      'Define product roadmap and strategy',
      'Conduct market research and competitive analysis',
      'Collaborate with engineering and design teams',
      'Analyze product metrics and user feedback',
      'Manage product launches and feature rollouts'
    ],
    requirements: [
      'Bachelor\'s degree in Business, Engineering, or related field',
      'Proven experience in product management',
      'Strong analytical and data-driven approach',
      'Excellent communication and leadership skills',
      'Experience with agile development methodologies'
    ],
    benefits: [
      'Competitive salary and bonus structure',
      'Stock options and equity participation',
      'Professional development and mentorship',
      'Flexible work arrangements',
      'Impact on product direction and strategy'
    ]
  },
  'UX Designer': {
    department: 'Design',
    skills: ['Figma', 'Sketch', 'User Research', 'Prototyping', 'Design Systems'],
    experience: '2-4 years',
    salary: '₹8,00,000 - ₹15,00,000',
    description: 'Design intuitive and engaging user experiences for our digital products.',
    responsibilities: [
      'Create wireframes, prototypes, and high-fidelity designs',
      'Conduct user research and usability testing',
      'Collaborate with product and engineering teams',
      'Maintain and evolve design systems',
      'Present design concepts to stakeholders'
    ],
    requirements: [
      'Bachelor\'s degree in Design, HCI, or related field',
      'Proficiency in design tools like Figma or Sketch',
      'Strong portfolio demonstrating UX design skills',
      'Understanding of user-centered design principles',
      'Excellent visual design and communication skills'
    ],
    benefits: [
      'Creative and collaborative work environment',
      'Latest design tools and software',
      'Design conference attendance',
      'Mentorship from senior designers',
      'Opportunity to shape product design'
    ]
  }
};

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

const LOCATIONS = INDIA_LOCATION_OPTIONS;

const EXPERIENCE_LEVELS = [
  'Entry Level (0-1 years)', '1-2 years', '2-4 years', '3-5 years', 
  '4-6 years', '5-7 years', '6-8 years', '7+ years', '10+ years'
];

const SALARY_RANGES = [
  '₹3,00,000 - ₹5,00,000', '₹5,00,000 - ₹8,00,000', '₹8,00,000 - ₹12,00,000', '₹12,00,000 - ₹18,00,000',
  '₹18,00,000 - ₹25,00,000', '₹25,00,000 - ₹35,00,000', '₹35,00,000 - ₹50,00,000', '₹50,00,000 - ₹75,00,000',
  '₹75,00,000 - ₹1,00,00,000', '₹1,00,00,000 - ₹1,50,00,000', '₹1,50,00,000 - ₹2,00,00,000', '₹2,00,00,000+'
];

const DEFAULT_PROCTORING_CONFIG = {
  voice_detection: true,
  object_detection: true,
  eyeball_tracking: true,
  gaze_heatmap: true,
  ai_detection: false,
  dual_camera: false,
};

const JobCreationModal = ({ isOpen, onClose, onJobCreate, showToast }) => {
  const notify = (message, type = 'error') =>
    showToast ? showToast(message, type) : alert(message);

  const [jobData, setJobData] = useState({
    title: '',
    department: '',
    location: '',
    type: 'Full-time',
    experience: '',
    salary: '',
    description: '',
    skills: [],
    responsibilities: '',
    requirements: '',
    benefits: '',
    deadline: '',
    status: 'draft',
    minimum_cv_score: 50,  // Default minimum CV score
    proctoring_config: DEFAULT_PROCTORING_CONFIG
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [skillInput, setSkillInput] = useState('');
  const [filteredSuggestions, setFilteredSuggestions] = useState([]);
  const [showTemplates, setShowTemplates] = useState(false);
  const [jdFile, setJdFile] = useState(null);
  const [aiPrompt, setAiPrompt] = useState('');
  const [isAiGenerating, setIsAiGenerating] = useState(false);
  const [aiError, setAiError] = useState('');
  
  const departmentDropdownRef = useRef(null);
  const locationDropdownRef = useRef(null);
  const experienceDropdownRef = useRef(null);
  const salaryDropdownRef = useRef(null);
  const skillsDropdownRef = useRef(null);
  const dropdownRefs = useMemo(() => ({
    department: departmentDropdownRef,
    location: locationDropdownRef,
    experience: experienceDropdownRef,
    salary: salaryDropdownRef,
    skills: skillsDropdownRef
  }), []);

  const resetForm = useCallback(() => {
    setJobData({
      title: '',
      department: '',
      location: '',
      type: 'Full-time',
      experience: '',
      salary: '',
      deadline: getDefaultDeadline(),
      skills: [],
      description: '',
      responsibilities: '',
      requirements: '',
      benefits: '',
      status: 'draft',
      minimum_cv_score: 50,
      proctoring_config: DEFAULT_PROCTORING_CONFIG
    });
    setSkillInput('');
    setFilteredSuggestions([]);
    setActiveDropdown(null);
    setShowTemplates(false);
    setJdFile(null);
    setAiPrompt('');
    setAiError('');
  }, []);

  const handleCancel = useCallback(() => {
    resetForm();
    onClose();
  }, [resetForm, onClose]);

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
  }, [dropdownRefs]);

  // Handle AI generation — from a text prompt, an uploaded JD file (parsed
  // and structured by AI), or both.
  const handleAiGenerate = async () => {
    if (!aiPrompt.trim() && !jdFile) return;
    setIsAiGenerating(true);
    setAiError('');
    try {
      const response = await generateJobWithAI(aiPrompt.trim(), jdFile);
      const ai = response.job_data;
      setJobData({
        title: ai.title || '',
        department: ai.department || '',
        location: String(ai.location || '').trim() || 'Remote (India)',
        type: ai.type || 'Full-time',
        experience: ai.experience || '',
        salary: ai.salary || '',
        deadline: getDefaultDeadline(),
        skills: Array.isArray(ai.skills) ? ai.skills : [],
        description: ai.description || '',
        responsibilities: Array.isArray(ai.responsibilities) ? ai.responsibilities.join('\n') : '',
        requirements: Array.isArray(ai.requirements) ? ai.requirements.join('\n') : '',
        benefits: Array.isArray(ai.benefits) ? ai.benefits.join('\n') : '',
        status: 'draft',
        minimum_cv_score: ai.minimum_cv_score || 50,
        gaze_proctoring: Boolean(jobData.proctoring_config?.gaze_heatmap),
        proctoring_config: {
          ...DEFAULT_PROCTORING_CONFIG,
          ...(jobData.proctoring_config || {})
        }
      });
      setAiPrompt('');
    } catch (err) {
      const refund = err?.data?.credit_refund;
      const refunded = Boolean(refund?.success);
      setAiError(
        `${err.message || 'Failed to generate. Please try again.'}${
          refunded ? ' Credits were refunded to your wallet.' : ''
        }`,
      );
    } finally {
      setIsAiGenerating(false);
    }
  };

  // Handle template selection
  const applyTemplate = (templateName) => {
    const template = JOB_TEMPLATES[templateName];
    if (template) {
      setJobData(prev => ({
        ...prev,
        title: templateName,
        department: template.department,
        location: prev.location || 'Remote',
        type: 'Full-time',
        experience: template.experience,
        salary: template.salary,
        deadline: prev.deadline || '',
        skills: template.skills,
        description: template.description,
        responsibilities: template.responsibilities.join('\n'),
        requirements: template.requirements.join('\n'),
        benefits: template.benefits.join('\n'),
        proctoring_config: {
          ...DEFAULT_PROCTORING_CONFIG,
          ...(prev.proctoring_config || {})
        }
      }));
      setShowTemplates(false);
    }
  };

  // Generate draft content based on title
  const handleTitleChange = (e) => {
    const title = e.target.value;
    handleInputChange(e);
    
    // Check if title matches a template
    const matchingTemplate = Object.keys(JOB_TEMPLATES).find(template =>
      template.toLowerCase().includes(title.toLowerCase()) && title.length > 3
    );
    
    if (matchingTemplate && !jobData.department) {
      const template = JOB_TEMPLATES[matchingTemplate];
      setJobData(prev => ({
        ...prev,
        title,
        department: template.department,
        experience: template.experience,
        salary: template.salary
      }));
    }
  };

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

  // Generate deadline suggestion (30 days from now)
  const getDefaultDeadline = () => {
    const date = new Date();
    date.setDate(date.getDate() + 30);
    return date.toISOString().split('T')[0];
  };

  // Suggestions deadline if empty
  useEffect(() => {
    if (isOpen && !jobData.deadline) {
      setJobData(prev => ({
        ...prev,
        deadline: getDefaultDeadline()
      }));
    }
  }, [isOpen, jobData.deadline]);

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
  }, [isOpen, handleCancel]);

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setJobData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Enhanced validation
    const requiredFields = ['title', 'department', 'location', 'experience', 'salary', 'description'];
    const missingFields = requiredFields.filter(field => !jobData[field].trim());
    
    if (missingFields.length > 0) {
      notify(`Please fill in the following required fields: ${missingFields.join(', ')}`);
      return;
    }

    if (jobData.skills.length === 0) {
      notify('Please add at least one required skill');
      return;
    }

    setIsSubmitting(true);
    try {
      const success = await onJobCreate({ ...jobData, gaze_proctoring: Boolean(jobData.proctoring_config?.gaze_heatmap) }, jdFile);
      if (success) {
        resetForm();
        onClose();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJdFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const isPdf = file.type === 'application/pdf';
      const isTxt = file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt');
      if (!isPdf && !isTxt) {
        notify('Please upload a PDF or TXT file');
        e.target.value = null;
        return;
      }
      if (file.size > 10 * 1024 * 1024) { // 10MB limit
        notify('File size must be less than 10MB');
        e.target.value = null;
        return;
      }
      setJdFile(file);
      setAiError('');
    }
  };

  const removeJdFile = () => {
    setJdFile(null);
    const fileInput = document.getElementById('jd-file-input');
    if (fileInput) fileInput.value = '';
  };

  // Dropdown component for suggestions
  const SuggestionDropdown = ({ items, onSelect, isVisible, maxHeight = '200px' }) => {
    if (!isVisible || items.length === 0) return null;
    
    return (
      <div className={styles.suggestionDropdown} style={{ maxHeight }}>
        {items.map((item, index) => (
          <div
            key={index}
            className={styles.suggestionItem}
            onClick={() => onSelect(item)}
          >
            {item}
          </div>
        ))}
      </div>
    );
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
          <h2>Create job</h2>
          <button type="button" className={styles.closeButton} onClick={handleCancel} aria-label="Close create job dialog">
            <i className="fa fa-times"></i>
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.jobForm}>
          {/* Quick Templates Section */}
          <div className={styles.templateSection}>
            <div className={styles.templateHeader}>
              <h3><i className="fa fa-bolt"></i> Job templates</h3>
              <button
                type="button"
                className={styles.toggleTemplates}
                onClick={() => setShowTemplates(!showTemplates)}
              >
                {showTemplates ? 'Hide Templates' : 'Show Templates'}
                <i className={`fa fa-chevron-${showTemplates ? 'up' : 'down'}`}></i>
              </button>
            </div>
            
            {showTemplates && (
              <div className={styles.templateGrid}>
                {Object.keys(JOB_TEMPLATES).map(templateName => (
                  <div
                    key={templateName}
                    className={styles.templateCard}
                    onClick={() => applyTemplate(templateName)}
                  >
                    <div className={styles.templateIcon}>
                      <i className={`fa ${
                        templateName.includes('Engineer') ? 'fa-code' : 
                        templateName.includes('Data') ? 'fa-database' : 
                        templateName.includes('Product') ? 'fa-cube' : 'fa-paint-brush'
                      }`}></i>
                    </div>
                    <div className={styles.templateContent}>
                      <h4>{templateName}</h4>
                      <p>{JOB_TEMPLATES[templateName].department}</p>
                      <span className={styles.templateSalary}>{JOB_TEMPLATES[templateName].salary}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* AI Job Description Generator */}
          <div className={styles.aiSection}>
            <div className={styles.aiHeader}>
              <h3><i className="fa fa-magic"></i> Draft a job description</h3>
              <span className={styles.aiBadge}>AI assistance</span>
            </div>
            <p className={styles.aiSubtext}>
              Describe the role or upload a job description to generate a draft. Review the details before publishing; your note can provide additional instructions.
            </p>
            <div className={styles.aiInputRow}>
              <input
                type="text"
                className={styles.aiInput}
                value={aiPrompt}
                onChange={(e) => { setAiPrompt(e.target.value); setAiError(''); }}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAiGenerate(); } }}
                placeholder='e.g. "Senior React Developer with 5 years experience in Bangalore" or "Entry level data analyst"'
                disabled={isAiGenerating}
              />
              <button
                type="button"
                className={styles.aiGenerateButton}
                onClick={handleAiGenerate}
                disabled={isAiGenerating || (!aiPrompt.trim() && !jdFile)}
              >
                {isAiGenerating ? (
                  <><i className="fa fa-spinner fa-spin"></i> Generating...</>
                ) : (
                  <><i className="fa fa-magic"></i> Generate JD</>
                )}
              </button>
            </div>

            {/* JD file upload — parsed by AI to auto-fill the form, and
                stored in cloud storage so candidates can download the exact
                document once the job is created. */}
            <div className={styles.fileUploadSection} style={{ marginTop: '14px' }}>
              {!jdFile ? (
                <div className={styles.fileUploadBox}>
                  <input
                    type="file"
                    accept=".pdf,.txt"
                    onChange={handleJdFileChange}
                    className={styles.fileInput}
                    id="jd-file-input"
                    disabled={isAiGenerating}
                  />
                  <label htmlFor="jd-file-input" className={styles.fileInputLabel}>
                    <i className="fa fa-cloud-upload"></i>
                    <span>Or upload a JD file (PDF/TXT) to auto-fill from</span>
                    <small>Click to browse or drag & drop (Max 10MB)</small>
                  </label>
                </div>
              ) : (
                <div className={styles.uploadedFile}>
                  <div className={styles.fileInfo}>
                    <i className="fa fa-file-pdf-o"></i>
                    <div className={styles.fileDetails}>
                      <span className={styles.fileName}>{jdFile.name}</span>
                      <span className={styles.fileSize}>
                        {(jdFile.size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className={styles.removeFileButton}
                    onClick={removeJdFile}
                    disabled={isAiGenerating}
                  >
                    <i className="fa fa-times"></i>
                  </button>
                </div>
              )}
              <div className={styles.helpText}>
                This file is stored with the job posting so candidates can download the original document, in addition to being parsed by AI to fill the form.
              </div>
            </div>

            {aiError && <p className={styles.aiError}><i className="fa fa-exclamation-circle"></i> {aiError}</p>}
          </div>

          <div className={styles.formGrid}>
            {/* Job Title with Suggestions */}
            <div className={styles.formGroup}>
              <label>Job Title *</label>
              <input
                type="text"
                name="title"
                value={jobData.title}
                onChange={handleTitleChange}
                required
                placeholder="e.g. Senior Software Engineer"
                className={styles.smartInput}
              />
              <div className={styles.helpText}>
                Try typing: "Software Engineer", "Data Scientist", "Product Manager", or "UX Designer"
              </div>
            </div>

            {/* Department with Dropdown */}
            <div className={styles.formGroup} ref={dropdownRefs.department}>
              <label>Department *</label>
              <div className={styles.inputWithDropdown}>
                <input
                  type="text"
                  name="department"
                  value={jobData.department}
                  onChange={handleInputChange}
                  onFocus={() => setActiveDropdown('department')}
                  required
                  placeholder="e.g. Engineering"
                  autoComplete="off"
                />
                <button
                  type="button"
                  className={styles.dropdownToggle}
                  onClick={() => setActiveDropdown(activeDropdown === 'department' ? null : 'department')}
                >
                  <i className="fa fa-chevron-down"></i>
                </button>
                <SuggestionDropdown
                  items={DEPARTMENTS.filter(dept => 
                    dept.toLowerCase().includes(jobData.department.toLowerCase())
                  )}
                  onSelect={(dept) => {
                    handleInputChange({ target: { name: 'department', value: dept } });
                    setActiveDropdown(null);
                  }}
                  isVisible={activeDropdown === 'department'}
                />
              </div>
            </div>

            {/* Location with Suggestions */}
            <div className={styles.formGroup} ref={dropdownRefs.location}>
              <label>Location *</label>
              <div className={styles.inputWithDropdown}>
                <input
                  type="text"
                  name="location"
                  value={jobData.location}
                  onChange={handleInputChange}
                  onFocus={() => setActiveDropdown('location')}
                  required
                  placeholder="e.g., Bangalore, Karnataka (Remote)"
                  autoComplete="off"
                />
                <button
                  type="button"
                  className={styles.dropdownToggle}
                  onClick={() => setActiveDropdown(activeDropdown === 'location' ? null : 'location')}
                >
                  <i className="fa fa-chevron-down"></i>
                </button>
                <SuggestionDropdown
                  items={LOCATIONS.filter(loc => 
                    loc.toLowerCase().includes(jobData.location.toLowerCase())
                  )}
                  onSelect={(location) => {
                    handleInputChange({ target: { name: 'location', value: location } });
                    setActiveDropdown(null);
                  }}
                  isVisible={activeDropdown === 'location'}
                />
              </div>
            </div>

            {/* Job Type Enhanced */}
            <div className={styles.formGroup}>
              <label>Job Type *</label>
              <select
                name="type"
                value={jobData.type}
                onChange={handleInputChange}
                required
                className={styles.enhancedSelect}
              >
                <option value="Full-time">Full-time</option>
                <option value="Part-time">⏰ Part-time</option>
                <option value="Contract"> Contract</option>
                <option value="Internship"> Internship</option>
                <option value="Freelance">🆓 Freelance</option>
                <option value="Remote"> Remote</option>
              </select>
            </div>

            {/* Experience with Suggestions */}
            <div className={styles.formGroup} ref={dropdownRefs.experience}>
              <label>Experience Required *</label>
              <div className={styles.inputWithDropdown}>
                <input
                  type="text"
                  name="experience"
                  value={jobData.experience}
                  onChange={handleInputChange}
                  onFocus={() => setActiveDropdown('experience')}
                  required
                  placeholder="e.g. 3+ years"
                  autoComplete="off"
                />
                <button
                  type="button"
                  className={styles.dropdownToggle}
                  onClick={() => setActiveDropdown(activeDropdown === 'experience' ? null : 'experience')}
                >
                  <i className="fa fa-chevron-down"></i>
                </button>
                <SuggestionDropdown
                  items={EXPERIENCE_LEVELS.filter(exp => 
                    exp.toLowerCase().includes(jobData.experience.toLowerCase())
                  )}
                  onSelect={(experience) => {
                    handleInputChange({ target: { name: 'experience', value: experience } });
                    setActiveDropdown(null);
                  }}
                  isVisible={activeDropdown === 'experience'}
                />
              </div>
            </div>

            {/* Salary with Suggestions */}
            <div className={styles.formGroup} ref={dropdownRefs.salary}>
              <label>Salary Range *</label>
              <div className={styles.inputWithDropdown}>
                <input
                  type="text"
                  name="salary"
                  value={jobData.salary}
                  onChange={handleInputChange}
                  onFocus={() => setActiveDropdown('salary')}
                  required
                  placeholder="e.g., ₹12,00,000 - ₹18,00,000"
                  autoComplete="off"
                />
                <button
                  type="button"
                  className={styles.dropdownToggle}
                  onClick={() => setActiveDropdown(activeDropdown === 'salary' ? null : 'salary')}
                >
                  <i className="fa fa-chevron-down"></i>
                </button>
                <SuggestionDropdown
                  items={SALARY_RANGES.filter(salary => 
                    salary.toLowerCase().includes(jobData.salary.toLowerCase())
                  )}
                  onSelect={(salary) => {
                    handleInputChange({ target: { name: 'salary', value: salary } });
                    setActiveDropdown(null);
                  }}
                  isVisible={activeDropdown === 'salary'}
                />
              </div>
            </div>

            {/* Application Deadline with Suggestions Default */}
            <div className={styles.formGroup}>
              <label>Application Deadline * <span className={styles.autoFilled}> Suggested date</span></label>
              <input
                type="date"
                name="deadline"
                value={jobData.deadline}
                onChange={handleInputChange}
                required
                min={new Date().toISOString().split('T')[0]}
              />
              <div className={styles.helpText}>
                 Default: 30 days from today
              </div>
            </div>

            {/* Job Status */}
            <div className={styles.formGroup}>
              <label>Job Status * <span className={styles.smartIndicator}> Status</span></label>
              <select
                name="status"
                value={jobData.status}
                onChange={handleInputChange}
                required
                className={styles.enhancedSelect}
              >
                <option value="draft"> Draft - Job is being prepared</option>
                <option value="active"> Active - Ready to accept applications</option>
              </select>
              <div className={styles.helpText}>
                 Draft: Preview before publishing | Active: Live and accepting applications
              </div>
            </div>

            {/* Minimum CV Score */}
            <div className={styles.formGroup}>
              <label>Minimum CV Score * <span className={styles.smartIndicator}> Screening threshold</span></label>
              <input
                type="number"
                name="minimum_cv_score"
                value={jobData.minimum_cv_score}
                onChange={handleInputChange}
                required
                min="0"
                max="100"
                step="1"
                className={styles.enhancedInput}
              />
              <div className={styles.helpText}>
                Applications with CV scores ≥ this threshold will be automatically shortlisted. Below this score = auto-rejected. Default: 50
              </div>
            </div>

            {/* Interview monitoring */}
            <div className={styles.formGroup} style={{gridColumn: '1 / -1'}}>
              <label> Interview monitoring</label>
              <div className={styles.proctoringSection}>
                <div className={styles.creditWarning}>
                  <i className="fa fa-exclamation-triangle"></i>
                  Real interview billing: 30 credits per candidate when proctoring is off, 50 credits when proctoring is on.
                </div>
                {PROCTORING_OPTIONS.map(opt => (
                  <div key={opt.key} className={styles.proctoringToggle}>
                    <div className={styles.proctoringInfo}>
                      <span className={styles.proctoringIcon}><i className={`fa ${opt.icon}`} aria-hidden="true" /></span>
                      <div>
                        <strong>{opt.label}</strong>
                        <p>{opt.desc}</p>
                      </div>
                    </div>
                    <label className={styles.toggleSwitch}>
                      <input
                        aria-label={opt.label}
                        type="checkbox"
                        checked={jobData.proctoring_config?.[opt.key] ?? DEFAULT_PROCTORING_CONFIG[opt.key]}
                        onChange={(e) => setJobData(prev => ({
                          ...prev,
                          proctoring_config: {
                            ...DEFAULT_PROCTORING_CONFIG,
                            ...(prev.proctoring_config || {}),
                            [opt.key]: e.target.checked
                          }
                        }))}
                      />
                      <span className={styles.slider}></span>
                    </label>
                  </div>
                ))}
              </div>
              <div className={styles.helpText}>
                AI drafting costs 10 credits. Manual creation is free. Disabled monitoring checks are labelled in reports.
              </div>
            </div>

            {/* Skills with Tag System */}
            <div className={styles.formGroup} ref={dropdownRefs.skills}>
              <label>Required Skills * <span className={styles.smartIndicator}> Skills</span></label>
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
                  <input
                    type="text"
                    value={skillInput}
                    onChange={(e) => setSkillInput(e.target.value)}
                    onKeyDown={handleSkillKeyPress}
                    onFocus={() => setActiveDropdown('skills')}
                    placeholder={jobData.skills.length === 0 ? "e.g. React, Node.js, MongoDB" : "Add more skills..."}
                    className={styles.skillInput}
                  />
                </div>
                <SuggestionDropdown
                  items={filteredSuggestions}
                  onSelect={addSkill}
                  isVisible={activeDropdown === 'skills' && filteredSuggestions.length > 0}
                  maxHeight="150px"
                />
              </div>
              <div className={styles.helpText}>
                 Type to search skills, press Enter to add, or click suggestions
              </div>
              <div className={styles.popularSkills}>
                <span>Popular: </span>
                {['JavaScript', 'Python', 'React', 'Node.js', 'MongoDB'].map(skill => (
                  <button
                    key={skill}
                    type="button"
                    onClick={() => addSkill(skill)}
                    className={styles.popularSkillButton}
                    disabled={jobData.skills.includes(skill)}
                  >
                    {skill}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Enhanced Text Areas */}
          <div className={styles.textAreasSection}>
            <div className={styles.formGroup}>
              <label>
                Job Description * 
                <span className={styles.smartIndicator}> Suggestions</span>
                {jobData.title && (
                  <button
                    type="button"
                    className={styles.generateButton}
                    onClick={() => {
                      const template = Object.values(JOB_TEMPLATES).find(t => 
                        t.department === jobData.department
                      );
                      if (template && !jobData.description) {
                        handleInputChange({ 
                          target: { name: 'description', value: template.description } 
                        });
                      }
                    }}
                    disabled={!jobData.title || !jobData.department || jobData.description}
                  >
                     Generate draft
                  </button>
                )}
              </label>
              <textarea
                name="description"
                value={jobData.description}
                onChange={handleInputChange}
                required
                rows="4"
                placeholder="Describe the role, company culture, and what makes this position exciting..."
                className={styles.enhancedTextarea}
              />
              <div className={styles.helpText}>
                Tip: Include company mission, role impact, and growth opportunities
              </div>
            </div>

            <div className={styles.formGroup}>
              <label>
                Key Responsibilities
                <span className={styles.optional}>(Optional)</span>
                {jobData.title && (
                  <button
                    type="button"
                    className={styles.generateButton}
                    onClick={() => {
                      const template = Object.values(JOB_TEMPLATES).find(t => 
                        t.department === jobData.department
                      );
                      if (template && !jobData.responsibilities) {
                        handleInputChange({ 
                          target: { name: 'responsibilities', value: template.responsibilities.join('\n') } 
                        });
                      }
                    }}
                    disabled={!jobData.title || !jobData.department || jobData.responsibilities}
                  >
                     Generate draft
                  </button>
                )}
              </label>
              <textarea
                name="responsibilities"
                value={jobData.responsibilities}
                onChange={handleInputChange}
                rows="5"
                placeholder="List key responsibilities (one per line):
• Develop and maintain web applications
• Collaborate with cross-functional teams
• Write clean, maintainable code
• Participate in code reviews"
                className={styles.enhancedTextarea}
              />
              <div className={styles.helpText}>
                 Format: Use bullet points or line breaks for better readability
              </div>
            </div>

            <div className={styles.formGroup}>
              <label>
                Requirements & Qualifications
                <span className={styles.optional}>(Optional)</span>
                {jobData.title && (
                  <button
                    type="button"
                    className={styles.generateButton}
                    onClick={() => {
                      const template = Object.values(JOB_TEMPLATES).find(t => 
                        t.department === jobData.department
                      );
                      if (template && !jobData.requirements) {
                        handleInputChange({ 
                          target: { name: 'requirements', value: template.requirements.join('\n') } 
                        });
                      }
                    }}
                    disabled={!jobData.title || !jobData.department || jobData.requirements}
                  >
                     Generate draft
                  </button>
                )}
              </label>
              <textarea
                name="requirements"
                value={jobData.requirements}
                onChange={handleInputChange}
                rows="5"
                placeholder="List requirements and qualifications:
• Bachelor's degree in relevant field
• X+ years of experience in...
• Proficiency in specific technologies
• Strong communication skills"
                className={styles.enhancedTextarea}
              />
              <div className={styles.helpText}>
                 Include the technical and communication skills required for this role.
              </div>
            </div>

            <div className={styles.formGroup}>
              <label>
                Benefits & Perks
                <span className={styles.optional}>(Optional)</span>
                {jobData.title && (
                  <button
                    type="button"
                    className={styles.generateButton}
                    onClick={() => {
                      const template = Object.values(JOB_TEMPLATES).find(t => 
                        t.department === jobData.department
                      );
                      if (template && !jobData.benefits) {
                        handleInputChange({ 
                          target: { name: 'benefits', value: template.benefits.join('\n') } 
                        });
                      }
                    }}
                    disabled={!jobData.title || !jobData.department || jobData.benefits}
                  >
                     Generate draft
                  </button>
                )}
              </label>
              <textarea
                name="benefits"
                value={jobData.benefits}
                onChange={handleInputChange}
                rows="4"
                placeholder="List benefits and perks:
• Competitive salary and equity
• Health, dental, vision insurance
• Flexible working hours
• Professional development budget
• Modern office environment"
                className={styles.enhancedTextarea}
              />
              <div className={styles.helpText}>
                 Highlight unique perks that make your company stand out
              </div>
            </div>
          </div>

          {/* Form Progress Indicator */}
          <div className={styles.formProgress}>
            <div className={styles.progressLabel}>Form Completion:</div>
            <div className={styles.progressBar}>
              <div 
                className={styles.progressFill}
                style={{
                  width: `${Math.round((
                    (jobData.title ? 1 : 0) +
                    (jobData.department ? 1 : 0) +
                    (jobData.location ? 1 : 0) +
                    (jobData.experience ? 1 : 0) +
                    (jobData.salary ? 1 : 0) +
                    (jobData.skills.length > 0 ? 1 : 0) +
                    (jobData.description ? 1 : 0)
                  ) / 7 * 100)}%`
                }}
              ></div>
            </div>
            <span className={styles.progressText}>
              {Math.round((
                (jobData.title ? 1 : 0) +
                (jobData.department ? 1 : 0) +
                (jobData.location ? 1 : 0) +
                (jobData.experience ? 1 : 0) +
                (jobData.salary ? 1 : 0) +
                (jobData.skills.length > 0 ? 1 : 0) +
                (jobData.description ? 1 : 0)
              ) / 7 * 100)}% Complete
            </span>
          </div>

          <div className={styles.formActions}>
            <div className={styles.actionButtons}>
              <button
                type="button"
                className={styles.cancelButton}
                onClick={handleCancel}
                disabled={isSubmitting}
              >
                <i className="fa fa-times"></i> Cancel
              </button>
              
              <button
                type="submit"
                className={styles.submitButton}
                disabled={isSubmitting || !jobData.title || !jobData.department || !jobData.location || jobData.skills.length === 0}
              >
                {isSubmitting ? (
                  <>
                    <i className="fa fa-spinner fa-spin"></i> Creating Job...
                  </>
                ) : (
                  <>
                    <i className="fa fa-rocket"></i> Create Job
                  </>
                )}
              </button>
            </div>
            
            <div className={styles.formFooter}>
              <div className={styles.quickStats}>
                <span className={styles.stat}>
                  <i className="fa fa-list"></i>
                  {Object.values(jobData).filter(val => 
                    Array.isArray(val) ? val.length > 0 : val && val.toString().trim()
                  ).length}/7 Fields Completed
                </span>
                <span className={styles.stat}>
                  <i className="fa fa-tag"></i>
                  {jobData.skills.length} Skills Added
                </span>
                <span className={styles.stat}>
                  <i className="fa fa-clock"></i>
                  Est. 2-3 min to complete
                </span>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default JobCreationModal;

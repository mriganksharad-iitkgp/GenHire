import React, { useState, useEffect, useRef } from 'react';
import styles from './JobCreationModal.module.css';

// Predefined data for auto-suggestions
const JOB_TEMPLATES = {
  'Software Engineer': {
    department: 'Engineering',
    skills: ['JavaScript', 'React', 'Node.js', 'MongoDB', 'Git'],
    experience: '2-4 years',
    salary: '$70,000 - $100,000',
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
    salary: '$80,000 - $120,000',
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
    salary: '$90,000 - $130,000',
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
    salary: '$60,000 - $90,000',
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

const LOCATIONS = [
  'Remote', 'San Francisco, CA', 'New York, NY', 'Austin, TX', 'Seattle, WA',
  'Boston, MA', 'Chicago, IL', 'Los Angeles, CA', 'Denver, CO', 'Atlanta, GA',
  'Remote (US)', 'Remote (Global)', 'Hybrid - San Francisco', 'Hybrid - New York'
];

const EXPERIENCE_LEVELS = [
  'Entry Level (0-1 years)', '1-2 years', '2-4 years', '3-5 years', 
  '4-6 years', '5-7 years', '6-8 years', '7+ years', '10+ years'
];

const SALARY_RANGES = [
  '$40,000 - $60,000', '$50,000 - $70,000', '$60,000 - $80,000', '$70,000 - $90,000',
  '$80,000 - $100,000', '$90,000 - $110,000', '$100,000 - $120,000', '$110,000 - $130,000',
  '$120,000 - $140,000', '$130,000 - $150,000', '$140,000 - $160,000', '$150,000 - $180,000',
  '$160,000 - $200,000', '$180,000 - $220,000', '$200,000 - $250,000'
];

const JobCreationModal = ({ isOpen, onClose, onJobCreate }) => {
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
    status: 'draft'  // Default to draft status
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [skillInput, setSkillInput] = useState('');
  const [filteredSuggestions, setFilteredSuggestions] = useState([]);
  const [showTemplates, setShowTemplates] = useState(false);
  
  const dropdownRefs = {
    department: useRef(null),
    location: useRef(null),
    experience: useRef(null),
    salary: useRef(null),
    skills: useRef(null)
  };

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

  // Handle template selection
  const applyTemplate = (templateName) => {
    const template = JOB_TEMPLATES[templateName];
    if (template) {
      setJobData({
        title: templateName,
        department: template.department,
        location: jobData.location || 'Remote',
        type: 'Full-time',
        experience: template.experience,
        salary: template.salary,
        deadline: '',
        skills: template.skills,
        description: template.description,
        responsibilities: template.responsibilities.join('\n'),
        requirements: template.requirements.join('\n'),
        benefits: template.benefits.join('\n')
      });
      setShowTemplates(false);
    }
  };

  // Auto-generate content based on title
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

  // Auto-fill deadline if empty
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
    
    // Enhanced validation
    const requiredFields = ['title', 'department', 'location', 'experience', 'salary', 'description'];
    const missingFields = requiredFields.filter(field => !jobData[field].trim());
    
    if (missingFields.length > 0) {
      alert(`Please fill in the following required fields: ${missingFields.join(', ')}`);
      return;
    }
    
    if (jobData.skills.length === 0) {
      alert('Please add at least one required skill');
      return;
    }

    setIsSubmitting(true);

    // Simulate API call
    setTimeout(() => {
      const newJob = {
        id: Date.now(),
        ...jobData,
        status: jobData.status, // Use the selected status
        postedDate: new Date().toISOString().split('T')[0],
        applicants: 0,
        interviewed: 0,
        selected: 0,
        rejected: 0,
        pending: 0,
        skills: jobData.skills // Already an array
      };

      onJobCreate(newJob);
      setIsSubmitting(false);
      
      // Reset form
      resetForm();
      onClose();
    }, 1000);
  };

  const resetForm = () => {
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
      status: 'draft' // Reset to draft status
    });
    setSkillInput('');
    setFilteredSuggestions([]);
    setActiveDropdown(null);
    setShowTemplates(false);
  };

  const handleCancel = () => {
    resetForm();
    onClose();
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
          <h2>Create New Job Posting</h2>
          <button className={styles.closeButton} onClick={handleCancel}>
            <i className="fa fa-times"></i>
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.jobForm}>
          {/* Quick Templates Section */}
          <div className={styles.templateSection}>
            <div className={styles.templateHeader}>
              <h3>🚀 Quick Start Templates</h3>
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
                      {templateName.includes('Engineer') ? '💻' : 
                       templateName.includes('Data') ? '📊' : 
                       templateName.includes('Product') ? '📱' : '🎨'}
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

          <div className={styles.formGrid}>
            {/* Job Title with Smart Suggestions */}
            <div className={styles.formGroup}>
              <label>Job Title * <span className={styles.smartIndicator}>🧠 Smart</span></label>
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
                💡 Try typing: "Software Engineer", "Data Scientist", "Product Manager", or "UX Designer"
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
                  placeholder="e.g. San Francisco, CA (Remote)"
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
                <option value="Full-time">💼 Full-time</option>
                <option value="Part-time">⏰ Part-time</option>
                <option value="Contract">📝 Contract</option>
                <option value="Internship">🎓 Internship</option>
                <option value="Freelance">🆓 Freelance</option>
                <option value="Remote">🌍 Remote</option>
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

            {/* Salary with Smart Suggestions */}
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
                  placeholder="e.g. $80,000 - $120,000"
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

            {/* Application Deadline with Smart Default */}
            <div className={styles.formGroup}>
              <label>Application Deadline * <span className={styles.autoFilled}>✨ Auto-filled</span></label>
              <input
                type="date"
                name="deadline"
                value={jobData.deadline}
                onChange={handleInputChange}
                required
                min={new Date().toISOString().split('T')[0]}
              />
              <div className={styles.helpText}>
                📅 Default: 30 days from today
              </div>
            </div>

            {/* Job Status */}
            <div className={styles.formGroup}>
              <label>Job Status * <span className={styles.smartIndicator}>🟢 Workflow</span></label>
              <select
                name="status"
                value={jobData.status}
                onChange={handleInputChange}
                required
                className={styles.enhancedSelect}
              >
                <option value="draft">📝 Draft - Job is being prepared</option>
                <option value="active">✅ Active - Ready to accept applications</option>
              </select>
              <div className={styles.helpText}>
                💡 Draft: Preview before publishing | Active: Live and accepting applications
              </div>
            </div>

            {/* Skills with Tag System */}
            <div className={styles.formGroup} ref={dropdownRefs.skills}>
              <label>Required Skills * <span className={styles.smartIndicator}>🏷️ Tags</span></label>
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
                💡 Type to search skills, press Enter to add, or click suggestions
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
                <span className={styles.smartIndicator}>🧠 Smart</span>
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
                    ✨ Auto-generate
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
                💡 Tip: Include company mission, role impact, and growth opportunities
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
                    ✨ Auto-generate
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
                📄 Format: Use bullet points or line breaks for better readability
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
                    ✨ Auto-generate
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
                🎯 Include both technical and soft skills requirements
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
                    ✨ Auto-generate
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
                🎆 Highlight unique perks that make your company stand out
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
                type="button"
                className={styles.draftButton}
                onClick={() => {
                  // Save as draft logic
                  const draftJob = {
                    ...jobData,
                    status: 'Draft',
                    savedAt: new Date().toISOString()
                  };
                  localStorage.setItem('jobDraft', JSON.stringify(draftJob));
                  alert('Draft saved successfully!');
                }}
                disabled={isSubmitting || !jobData.title}
                title="Save current progress as draft"
              >
                <i className="fa fa-save"></i> Save Draft
              </button>
              
              <button
                type="button"
                className={styles.previewButton}
                onClick={() => {
                  // Simple preview alert - in real app, would show preview modal
                  const preview = `
Job Title: ${jobData.title || 'Not specified'}
Department: ${jobData.department || 'Not specified'}
Location: ${jobData.location || 'Not specified'}
Experience: ${jobData.experience || 'Not specified'}
Salary: ${jobData.salary || 'Not specified'}
Skills: ${jobData.skills.join(', ') || 'None specified'}
Description: ${jobData.description ? jobData.description.substring(0, 100) + '...' : 'Not specified'}`;
                  alert('Job Preview:' + preview);
                }}
                disabled={!jobData.title}
                title="Preview job posting"
              >
                <i className="fa fa-eye"></i> Preview
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
                    <i className="fa fa-rocket"></i> Create & Publish Job
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

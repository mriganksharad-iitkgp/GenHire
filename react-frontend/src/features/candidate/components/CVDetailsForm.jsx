import React, { useState, useEffect } from 'react';
import styles from './CVDetailsForm.module.css';
import Toast from 'shared/components/ui/Toast';

const CVDetailsForm = ({ onSave, existingData = null, onClose }) => {
  const [toast, setToast] = useState(null);
  const [formData, setFormData] = useState({
    salaryExpectations: {
      currentSalary: '',
      expectedSalary: '',
      currency: 'USD',
      negotiable: false,
      salaryType: 'annual' // annual, monthly, hourly
    },
    positionsHeld: [
      {
        title: '',
        organization: '',
        duration: '',
        responsibilities: '',
        achievements: '',
        teamSize: '',
        reportingTo: '',
        location: ''
      }
    ],
    education: [
      {
        degree: '',
        institution: '',
        year: '',
        grade: '',
        field: ''
      }
    ],
    experience: [
      {
        company: '',
        position: '',
        duration: '',
        description: '',
        location: ''
      }
    ],
    skills: {
      technical: [],
      soft: []
    },
    projects: [
      {
        title: '',
        description: '',
        technologies: '',
        duration: '',
        link: ''
      }
    ],
    achievements: [
      {
        title: '',
        description: '',
        date: '',
        organization: '',
        level: ''
      }
    ],
    competitions: [
      {
        name: '',
        position: '',
        date: '',
        organizer: '',
        description: ''
      }
    ],
    certifications: [
      {
        name: '',
        issuer: '',
        date: '',
        credentialId: '',
        validUntil: ''
      }
    ],
    internships: [
      {
        company: '',
        position: '',
        duration: '',
        description: '',
        location: ''
      }
    ],
    coursework: [
      {
        course: '',
        institution: '',
        duration: '',
        certification: ''
      }
    ],
    languages: [
      {
        language: '',
        proficiency: '',
        certification: ''
      }
    ],
    extracurricular: [
      {
        activity: '',
        role: '',
        duration: '',
        description: ''
      }
    ]
  });

  const [activeSection, setActiveSection] = useState('education');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (existingData) {
      setFormData(prevFormData => ({ ...prevFormData, ...existingData }));
    }
  }, [existingData]);

  // Prevent body scrolling when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, []);

  const addNewItem = (section) => {
    const newItem = getEmptyItem(section);
    setFormData(prev => ({
      ...prev,
      [section]: [...prev[section], newItem]
    }));
  };

  const removeItem = (section, index) => {
    setFormData(prev => ({
      ...prev,
      [section]: prev[section].filter((_, i) => i !== index)
    }));
  };

  const updateItem = (section, index, field, value) => {
    setFormData(prev => ({
      ...prev,
      [section]: prev[section].map((item, i) => 
        i === index ? { ...item, [field]: value } : item
      )
    }));
  };

  const updateSkills = (type, value) => {
    const skillsArray = value.split(',').map(skill => skill.trim()).filter(skill => skill);
    setFormData(prev => ({
      ...prev,
      skills: {
        ...prev.skills,
        [type]: skillsArray
      }
    }));
  };

  const getEmptyItem = (section) => {
    const templates = {
      education: { degree: '', institution: '', year: '', grade: '', field: '' },
      experience: { company: '', position: '', duration: '', description: '', location: '' },
      projects: { title: '', description: '', technologies: '', duration: '', link: '' },
      achievements: { title: '', description: '', date: '', organization: '', level: '' },
      competitions: { name: '', position: '', date: '', organizer: '', description: '' },
      certifications: { name: '', issuer: '', date: '', credentialId: '', validUntil: '' },
      internships: { company: '', position: '', duration: '', description: '', location: '' },
      coursework: { course: '', institution: '', duration: '', certification: '' },
      languages: { language: '', proficiency: '', certification: '' },
      extracurricular: { activity: '', role: '', duration: '', description: '' },
      positionsHeld: { title: '', organization: '', duration: '', responsibilities: '', achievements: '', teamSize: '', reportingTo: '', location: '' }
    };
    return templates[section] || {};
  };

  const validateRequiredFields = () => {
    const errors = [];
    
    // Education validation
    const hasValidEducation = formData.education.some(edu => 
      edu.degree.trim() && edu.institution.trim() && edu.year.trim()
    );
    if (!hasValidEducation) errors.push('At least one complete education entry is required');
    
    // Skills validation
    if (formData.skills.technical.length === 0) errors.push('Technical Skills are required');
    
    // Projects validation
    const hasValidProject = formData.projects.some(project => 
      project.title.trim() && project.description.trim()
    );
    if (!hasValidProject) errors.push('At least one complete project entry is required');
    
    // Salary Expectations validation
    if (!formData.salaryExpectations.expectedSalary) errors.push('Expected Salary is required');
    
    return errors;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate required fields
    const validationErrors = validateRequiredFields();
    if (validationErrors.length > 0) {
      setToast({
        message: 'Please complete the following required fields: ' + validationErrors.join(', '),
        type: 'error'
      });
      return;
    }
    
    setIsSaving(true);
    try {
      const saved = await onSave(formData);
      if (saved === false) { setToast({message:"Unable to save CV details. Please retry.",type:"error"}); return; }
      setToast({
        message: 'CV details saved successfully!',
        type: 'success'
      });
    } catch (error) {
      console.error('Error saving CV details:', error);
      setToast({
        message: 'Error saving CV details. Please try again.',
        type: 'error'
      });
    } finally {
      setIsSaving(false);
    }
  };

  const sections = [
    { key: 'education', label: 'Education', icon: 'fa-graduation-cap', required: true },
    { key: 'experience', label: 'Work Experience', icon: 'fa-building', required: false },
    { key: 'positionsHeld', label: 'Positions Held', icon: 'fa-user', required: false },
    { key: 'skills', label: 'Skills', icon: 'fa-cogs', required: true },
    { key: 'projects', label: 'Projects', icon: 'fa-code', required: true },
    { key: 'salaryExpectations', label: 'Salary Expectations', icon: 'fa-money', required: true },
    { key: 'achievements', label: 'Achievements', icon: 'fa-trophy', required: false },
    { key: 'competitions', label: 'Competitions', icon: 'fa-star', required: false },
    { key: 'certifications', label: 'Certifications', icon: 'fa-certificate', required: false },
    { key: 'internships', label: 'Internships', icon: 'fa-briefcase', required: false },
    { key: 'languages', label: 'Languages', icon: 'fa-globe', required: false },
    { key: 'coursework', label: 'Coursework', icon: 'fa-book', required: false },
    { key: 'extracurricular', label: 'Extra Curricular', icon: 'fa-users', required: false }
  ];

  const renderEducationSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-graduation-cap"></i> Education</h3>
        <button 
          type="button" 
          onClick={() => addNewItem('education')}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add Education
        </button>
      </div>
      {formData.education.map((edu, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>Education {index + 1}</h4>
            {formData.education.length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem('education', index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Degree/Qualification *</label>
              <input
                type="text"
                value={edu.degree}
                onChange={(e) => updateItem('education', index, 'degree', e.target.value)}
                placeholder="e.g., Bachelor of Technology"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Institution *</label>
              <input
                type="text"
                value={edu.institution}
                onChange={(e) => updateItem('education', index, 'institution', e.target.value)}
                placeholder="e.g., IIT Delhi"
                required
              />
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Field of Study</label>
              <input
                type="text"
                value={edu.field}
                onChange={(e) => updateItem('education', index, 'field', e.target.value)}
                placeholder="e.g., Computer Science"
              />
            </div>
            <div className={styles.formGroup}>
              <label>Year/Duration *</label>
              <input
                type="text"
                value={edu.year}
                onChange={(e) => updateItem('education', index, 'year', e.target.value)}
                placeholder="e.g., 2020-2024"
                required
              />
            </div>
          </div>
          <div className={styles.formGroup}>
            <label>Grade/CGPA</label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="10"
              value={edu.grade}
              onChange={(e) => updateItem('education', index, 'grade', e.target.value)}
              placeholder="e.g., 8.5"
            />
          </div>
        </div>
      ))}
    </div>
  );

  const renderSkillsSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-cogs"></i> Skills</h3>
      </div>
      <div className={styles.skillsContainer}>
        <div className={styles.formGroup}>
          <label>Technical Skills *</label>
          <textarea
            value={formData.skills.technical.join(', ')}
            onChange={(e) => updateSkills('technical', e.target.value)}
            placeholder="e.g., React, Node.js, Python, Java, SQL (separate with commas)"
            rows="3"
            required
          />
          <small>Separate skills with commas</small>
        </div>
        <div className={styles.formGroup}>
          <label>Soft Skills</label>
          <textarea
            value={formData.skills.soft.join(', ')}
            onChange={(e) => updateSkills('soft', e.target.value)}
            placeholder="e.g., Leadership, Communication, Problem Solving (separate with commas)"
            rows="3"
          />
          <small>Separate skills with commas</small>
        </div>
      </div>
    </div>
  );

  const renderProjectsSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-code"></i> Projects</h3>
        <button 
          type="button" 
          onClick={() => addNewItem('projects')}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add Project
        </button>
      </div>
      {formData.projects.map((project, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>Project {index + 1}</h4>
            {formData.projects.length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem('projects', index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Project Title *</label>
              <input
                type="text"
                value={project.title}
                onChange={(e) => updateItem('projects', index, 'title', e.target.value)}
                placeholder="e.g., E-commerce Web Application"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Duration (months)</label>
              <input
                type="number"
                min="1"
                value={project.duration}
                onChange={(e) => updateItem('projects', index, 'duration', e.target.value)}
                placeholder="e.g., 3"
              />
            </div>
          </div>
          <div className={styles.formGroup}>
            <label>Technologies Used</label>
            <input
              type="text"
              value={project.technologies}
              onChange={(e) => updateItem('projects', index, 'technologies', e.target.value)}
              placeholder="e.g., React, Node.js, MongoDB"
            />
          </div>
          <div className={styles.formGroup}>
            <label>Description *</label>
            <textarea
              value={project.description}
              onChange={(e) => updateItem('projects', index, 'description', e.target.value)}
              placeholder="Describe your project, key features, and your role..."
              rows="3"
              required
            />
          </div>
          <div className={styles.formGroup}>
            <label>Project Link</label>
            <input
              type="url"
              value={project.link}
              onChange={(e) => updateItem('projects', index, 'link', e.target.value)}
              placeholder="e.g., https://github.com/username/project"
            />
          </div>
        </div>
      ))}
    </div>
  );

  const renderExperienceSection = (sectionKey, title, icon) => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className={`fa ${icon}`}></i> {title}</h3>
        <button 
          type="button" 
          onClick={() => addNewItem(sectionKey)}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add {title}
        </button>
      </div>
      {formData[sectionKey].map((item, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>{title} {index + 1}</h4>
            {formData[sectionKey].length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem(sectionKey, index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Company/Organization *</label>
              <input
                type="text"
                value={item.company}
                onChange={(e) => updateItem(sectionKey, index, 'company', e.target.value)}
                placeholder="e.g., Google Inc."
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Position *</label>
              <input
                type="text"
                value={item.position}
                onChange={(e) => updateItem(sectionKey, index, 'position', e.target.value)}
                placeholder="e.g., Software Engineer Intern"
                required
              />
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Duration *</label>
              <input
                type="text"
                value={item.duration}
                onChange={(e) => updateItem(sectionKey, index, 'duration', e.target.value)}
                placeholder="e.g., Jun 2023 - Aug 2023"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Location</label>
              <input
                type="text"
                value={item.location}
                onChange={(e) => updateItem(sectionKey, index, 'location', e.target.value)}
                placeholder="e.g., Bangalore, India"
              />
            </div>
          </div>
          <div className={styles.formGroup}>
            <label>Description *</label>
            <textarea
              value={item.description}
              onChange={(e) => updateItem(sectionKey, index, 'description', e.target.value)}
              placeholder="Describe your responsibilities, achievements, and key learnings..."
              rows="3"
              required
            />
          </div>
        </div>
      ))}
    </div>
  );

  const renderCourseworkSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-book"></i> Coursework & Certifications</h3>
        <button 
          type="button" 
          onClick={() => addNewItem('coursework')}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add Course
        </button>
      </div>
      {formData.coursework.map((course, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>Course {index + 1}</h4>
            {formData.coursework.length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem('coursework', index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Course/Certification Name *</label>
              <input
                type="text"
                value={course.course}
                onChange={(e) => updateItem('coursework', index, 'course', e.target.value)}
                placeholder="e.g., AWS Cloud Practitioner"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Institution/Platform *</label>
              <input
                type="text"
                value={course.institution}
                onChange={(e) => updateItem('coursework', index, 'institution', e.target.value)}
                placeholder="e.g., Amazon Web Services"
                required
              />
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Duration/Completion Date</label>
              <input
                type="text"
                value={course.duration}
                onChange={(e) => updateItem('coursework', index, 'duration', e.target.value)}
                placeholder="e.g., March 2024"
              />
            </div>
            <div className={styles.formGroup}>
              <label>Certification ID</label>
              <input
                type="text"
                value={course.certification}
                onChange={(e) => updateItem('coursework', index, 'certification', e.target.value)}
                placeholder="Certificate ID or verification link"
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );

  const renderExtracurricularSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-users"></i> Extracurricular Activities</h3>
        <button 
          type="button" 
          onClick={() => addNewItem('extracurricular')}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add Activity
        </button>
      </div>
      {formData.extracurricular.map((activity, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>Activity {index + 1}</h4>
            {formData.extracurricular.length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem('extracurricular', index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Activity/Organization *</label>
              <input
                type="text"
                value={activity.activity}
                onChange={(e) => updateItem('extracurricular', index, 'activity', e.target.value)}
                placeholder="e.g., Student Council"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Role/Position</label>
              <input
                type="text"
                value={activity.role}
                onChange={(e) => updateItem('extracurricular', index, 'role', e.target.value)}
                placeholder="e.g., President"
              />
            </div>
          </div>
          <div className={styles.formGroup}>
            <label>Duration</label>
            <input
              type="text"
              value={activity.duration}
              onChange={(e) => updateItem('extracurricular', index, 'duration', e.target.value)}
              placeholder="e.g., 2022-2023"
            />
          </div>
          <div className={styles.formGroup}>
            <label>Description</label>
            <textarea
              value={activity.description}
              onChange={(e) => updateItem('extracurricular', index, 'description', e.target.value)}
              placeholder="Describe your involvement, achievements, and impact..."
              rows="3"
            />
          </div>
        </div>
      ))}
    </div>
  );

  const renderAchievementsSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-trophy"></i> Achievements</h3>
        <button 
          type="button" 
          onClick={() => addNewItem('achievements')}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add Achievement
        </button>
      </div>
      {formData.achievements.map((achievement, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>Achievement {index + 1}</h4>
            {formData.achievements.length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem('achievements', index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Achievement Title *</label>
              <input
                type="text"
                value={achievement.title}
                onChange={(e) => updateItem('achievements', index, 'title', e.target.value)}
                placeholder="e.g., Dean's List, Best Student Award"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Organization/Institution</label>
              <input
                type="text"
                value={achievement.organization}
                onChange={(e) => updateItem('achievements', index, 'organization', e.target.value)}
                placeholder="e.g., IIT Delhi, Google"
              />
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Date Received</label>
              <input
                type="text"
                value={achievement.date}
                onChange={(e) => updateItem('achievements', index, 'date', e.target.value)}
                placeholder="e.g., May 2024"
              />
            </div>
            <div className={styles.formGroup}>
              <label>Level</label>
              <select
                value={achievement.level}
                onChange={(e) => updateItem('achievements', index, 'level', e.target.value)}
                className={styles.selectInput}
              >
                <option value="">Select Level</option>
                <option value="International">International</option>
                <option value="National">National</option>
                <option value="State">State</option>
                <option value="Regional">Regional</option>
                <option value="University">University</option>
                <option value="College">College</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>
          <div className={styles.formGroup}>
            <label>Description</label>
            <textarea
              value={achievement.description}
              onChange={(e) => updateItem('achievements', index, 'description', e.target.value)}
              placeholder="Describe the achievement, its significance, and impact..."
              rows="3"
            />
          </div>
        </div>
      ))}
    </div>
  );

  const renderCompetitionsSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-medal"></i> Competitions</h3>
        <button 
          type="button" 
          onClick={() => addNewItem('competitions')}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add Competition
        </button>
      </div>
      {formData.competitions.map((competition, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>Competition {index + 1}</h4>
            {formData.competitions.length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem('competitions', index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Competition Name *</label>
              <input
                type="text"
                value={competition.name}
                onChange={(e) => updateItem('competitions', index, 'name', e.target.value)}
                placeholder="e.g., ACM ICPC, Google Code Jam"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Position/Rank</label>
              <input
                type="text"
                value={competition.position}
                onChange={(e) => updateItem('competitions', index, 'position', e.target.value)}
                placeholder="e.g., 1st Place, Top 10"
              />
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Date</label>
              <input
                type="text"
                value={competition.date}
                onChange={(e) => updateItem('competitions', index, 'date', e.target.value)}
                placeholder="e.g., March 2024"
              />
            </div>
            <div className={styles.formGroup}>
              <label>Organizer</label>
              <input
                type="text"
                value={competition.organizer}
                onChange={(e) => updateItem('competitions', index, 'organizer', e.target.value)}
                placeholder="e.g., ACM, Google, HackerRank"
              />
            </div>
          </div>
          <div className={styles.formGroup}>
            <label>Description</label>
            <textarea
              value={competition.description}
              onChange={(e) => updateItem('competitions', index, 'description', e.target.value)}
              placeholder="Describe the competition, your role, and achievements..."
              rows="3"
            />
          </div>
        </div>
      ))}
    </div>
  );

  const renderCertificationsSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-certificate"></i> Certifications</h3>
        <button 
          type="button" 
          onClick={() => addNewItem('certifications')}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add Certification
        </button>
      </div>
      {formData.certifications.map((cert, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>Certification {index + 1}</h4>
            {formData.certifications.length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem('certifications', index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Certification Name *</label>
              <input
                type="text"
                value={cert.name}
                onChange={(e) => updateItem('certifications', index, 'name', e.target.value)}
                placeholder="e.g., AWS Solutions Architect"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Issuing Organization *</label>
              <input
                type="text"
                value={cert.issuer}
                onChange={(e) => updateItem('certifications', index, 'issuer', e.target.value)}
                placeholder="e.g., Amazon Web Services"
                required
              />
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Issue Date</label>
              <input
                type="text"
                value={cert.date}
                onChange={(e) => updateItem('certifications', index, 'date', e.target.value)}
                placeholder="e.g., March 2024"
              />
            </div>
            <div className={styles.formGroup}>
              <label>Valid Until</label>
              <input
                type="text"
                value={cert.validUntil}
                onChange={(e) => updateItem('certifications', index, 'validUntil', e.target.value)}
                placeholder="e.g., March 2027, No Expiry"
              />
            </div>
          </div>
          <div className={styles.formGroup}>
            <label>Credential ID</label>
            <input
              type="text"
              value={cert.credentialId}
              onChange={(e) => updateItem('certifications', index, 'credentialId', e.target.value)}
              placeholder="Certificate ID or verification link"
            />
          </div>
        </div>
      ))}
    </div>
  );



  const renderSalaryExpectationsSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-money-bill-wave"></i> Salary Expectations</h3>
      </div>
      <div className={styles.itemCard}>
        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label>Current Salary</label>
            <input
              type="number"
              value={formData.salaryExpectations.currentSalary}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                salaryExpectations: { ...prev.salaryExpectations, currentSalary: e.target.value }
              }))}
              placeholder="Enter current salary (if applicable)"
            />
          </div>
          <div className={styles.formGroup}>
            <label>Expected Salary *</label>
            <input
              type="number"
              value={formData.salaryExpectations.expectedSalary}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                salaryExpectations: { ...prev.salaryExpectations, expectedSalary: e.target.value }
              }))}
              placeholder="Enter expected salary"
              required
            />
          </div>
        </div>
        <div className={styles.formRow}>
          <div className={styles.formGroup}>
            <label>Currency *</label>
            <select
              value={formData.salaryExpectations.currency}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                salaryExpectations: { ...prev.salaryExpectations, currency: e.target.value }
              }))}
              className={styles.selectInput}
              required
            >
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
              <option value="INR">INR (₹)</option>
              <option value="CAD">CAD (C$)</option>
              <option value="AUD">AUD (A$)</option>
            </select>
          </div>
          <div className={styles.formGroup}>
            <label>Salary Type *</label>
            <select
              value={formData.salaryExpectations.salaryType}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                salaryExpectations: { ...prev.salaryExpectations, salaryType: e.target.value }
              }))}
              className={styles.selectInput}
              required
            >
              <option value="annual">Annual</option>
              <option value="monthly">Monthly</option>
              <option value="hourly">Hourly</option>
            </select>
          </div>
        </div>
        <div className={styles.formGroup}>
          <label>
            <input
              type="checkbox"
              checked={formData.salaryExpectations.negotiable}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                salaryExpectations: { ...prev.salaryExpectations, negotiable: e.target.checked }
              }))}
            />
            Salary is negotiable
          </label>
        </div>
      </div>
    </div>
  );

  const renderPositionsHeldSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-crown"></i> Positions Held</h3>
        <button 
          type="button" 
          onClick={() => addNewItem('positionsHeld')}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add Position
        </button>
      </div>
      {formData.positionsHeld.map((position, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>Position {index + 1}</h4>
            {formData.positionsHeld.length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem('positionsHeld', index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Position Title *</label>
              <input
                type="text"
                value={position.title}
                onChange={(e) => updateItem('positionsHeld', index, 'title', e.target.value)}
                placeholder="e.g., Team Lead, Project Manager, President"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Organization *</label>
              <input
                type="text"
                value={position.organization}
                onChange={(e) => updateItem('positionsHeld', index, 'organization', e.target.value)}
                placeholder="e.g., Student Council, Tech Club, Company"
                required
              />
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Duration (months) *</label>
              <input
                type="number"
                min="1"
                value={position.duration}
                onChange={(e) => updateItem('positionsHeld', index, 'duration', e.target.value)}
                placeholder="e.g., 12"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Location</label>
              <input
                type="text"
                value={position.location}
                onChange={(e) => updateItem('positionsHeld', index, 'location', e.target.value)}
                placeholder="e.g., New York, NY"
              />
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Team Size</label>
              <input
                type="number"
                min="1"
                value={position.teamSize}
                onChange={(e) => updateItem('positionsHeld', index, 'teamSize', e.target.value)}
                placeholder="e.g., 10"
              />
            </div>
            <div className={styles.formGroup}>
              <label>Reporting To</label>
              <input
                type="text"
                value={position.reportingTo}
                onChange={(e) => updateItem('positionsHeld', index, 'reportingTo', e.target.value)}
                placeholder="e.g., Director, CEO, Faculty Advisor"
              />
            </div>
          </div>
          <div className={styles.formGroup}>
            <label>Key Responsibilities *</label>
            <textarea
              value={position.responsibilities}
              onChange={(e) => updateItem('positionsHeld', index, 'responsibilities', e.target.value)}
              placeholder="Describe your key responsibilities and duties in this position..."
              rows="3"
              required
            />
          </div>
          <div className={styles.formGroup}>
            <label>Key Achievements</label>
            <textarea
              value={position.achievements}
              onChange={(e) => updateItem('positionsHeld', index, 'achievements', e.target.value)}
              placeholder="Highlight your major achievements and impact in this role..."
              rows="3"
            />
          </div>
        </div>
      ))}
    </div>
  );


  const renderLanguagesSection = () => (
    <div className={styles.sectionContent}>
      <div className={styles.sectionHeader}>
        <h3><i className="fa fa-globe"></i> Languages</h3>
        <button 
          type="button" 
          onClick={() => addNewItem('languages')}
          className={styles.addButton}
        >
          <i className="fa fa-plus"></i> Add Language
        </button>
      </div>
      {formData.languages.map((language, index) => (
        <div key={index} className={styles.itemCard}>
          <div className={styles.cardHeader}>
            <h4>Language {index + 1}</h4>
            {formData.languages.length > 1 && (
              <button 
                type="button"
                onClick={() => removeItem('languages', index)}
                className={styles.removeButton}
              >
                <i className="fa fa-trash"></i>
              </button>
            )}
          </div>
          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label>Language *</label>
              <input
                type="text"
                value={language.language}
                onChange={(e) => updateItem('languages', index, 'language', e.target.value)}
                placeholder="e.g., English, Spanish, Mandarin"
                required
              />
            </div>
            <div className={styles.formGroup}>
              <label>Proficiency Level *</label>
              <select
                value={language.proficiency}
                onChange={(e) => updateItem('languages', index, 'proficiency', e.target.value)}
                className={styles.selectInput}
                required
              >
                <option value="">Select Proficiency</option>
                <option value="Native">Native</option>
                <option value="Fluent">Fluent</option>
                <option value="Advanced">Advanced</option>
                <option value="Intermediate">Intermediate</option>
                <option value="Basic">Basic</option>
              </select>
            </div>
          </div>
          <div className={styles.formGroup}>
            <label>Certification/Test Score</label>
            <input
              type="text"
              value={language.certification}
              onChange={(e) => updateItem('languages', index, 'certification', e.target.value)}
              placeholder="e.g., IELTS 8.5, TOEFL 110, DELE B2"
            />
          </div>
        </div>
      ))}
    </div>
  );

  const renderActiveSection = () => {
    switch (activeSection) {
      case 'education':
        return renderEducationSection();
      case 'experience':
        return renderExperienceSection('experience', 'Work Experience', 'fa-building');
      case 'positionsHeld':
        return renderPositionsHeldSection();
      case 'skills':
        return renderSkillsSection();
      case 'projects':
        return renderProjectsSection();
      case 'salaryExpectations':
        return renderSalaryExpectationsSection();
      case 'achievements':
        return renderAchievementsSection();
      case 'competitions':
        return renderCompetitionsSection();
      case 'certifications':
        return renderCertificationsSection();
      case 'internships':
        return renderExperienceSection('internships', 'Internships', 'fa-briefcase');
      case 'languages':
        return renderLanguagesSection();
      case 'coursework':
        return renderCourseworkSection();
      case 'extracurricular':
        return renderExtracurricularSection();
      default:
        return renderEducationSection();
    }
  };

  return (
    <div className={styles.cvDetailsModal}>
      <div className={styles.modalContent}>
        <div className={styles.modalHeader}>
          <h2><i className="fa fa-file-text"></i> CV Details Entry</h2>
          <button type="button" onClick={onClose} className={styles.closeButton} aria-label="Close CV dialog">
            <i className="fa fa-times"></i>
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className={styles.cvForm}>
          <div className={styles.formLayout}>
            <div className={styles.sidebar}>
              <nav className={styles.sectionNav}>
                {sections.map(section => (
                  <button
                    key={section.key}
                    type="button"
                    className={`${styles.navButton} ${activeSection === section.key ? styles.active : ''} ${section.required ? styles.required : ''}`}
                    onClick={() => setActiveSection(section.key)}
                  >
                    <i className={`fa ${section.icon}`}></i>
                    <span>{section.label}</span>
                    {section.required && <span className={styles.requiredMark}>*</span>}
                  </button>
                ))}
              </nav>
            </div>
            
            <div className={styles.content}>
              {renderActiveSection()}
            </div>
          </div>
          
          <div className={styles.modalFooter}>
            <button type="button" onClick={onClose} className={styles.cancelButton}>
              Cancel
            </button>
            <button type="submit" disabled={isSaving} className={styles.saveButton}>
              {isSaving ? (
                <>
                  <i className="fa fa-spinner fa-spin"></i>
                  Saving...
                </>
              ) : (
                <>
                  <i className="fa fa-save"></i>
                  Save CV Details
                </>
              )}
            </button>
          </div>
        </form>
        
        {toast && (
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={() => setToast(null)}
          />
        )}
      </div>
    </div>
  );
};

export default CVDetailsForm;

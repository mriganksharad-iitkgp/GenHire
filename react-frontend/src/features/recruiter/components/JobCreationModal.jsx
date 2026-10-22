import { PROCTORING_OPTIONS } from "shared/constants/proctoringOptions";
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { INDIA_LOCATION_OPTIONS } from 'shared/constants/jobTaxonomy';
import styles from './JobForm.module.css';
import useJobSetup from '../hooks/useJobSetup';
import useJobDraftRecovery from '../hooks/useJobDraftRecovery';
import JobDraftNotice from './JobDraftNotice';
import JobAIDraftBuilder from './JobAIDraftBuilder';
import questionDraftConfiguration from '../utils/questionDraftConfiguration';
import useJobWizardScroll from '../hooks/useJobWizardScroll';
import JobQuestionDrafts from './JobQuestionDrafts';
import attachJobQuestions from '../utils/attachJobQuestions';
import {SetupNotice,PricingNote} from './HiringSetupWizard';
import RoleAssessmentTemplateControls from './RoleAssessmentTemplateControls';
import JobHiringSections,{revealJobSection,revealInvalidJobField} from './JobHiringSections';

import { JOB_TEMPLATES } from '../utils/jobTemplates';
import JobTemplatePicker from './JobTemplatePicker';

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
  const dialogRef = useJobWizardScroll(isOpen);
  const [questionDrafts, setQuestionDrafts] = useState({editor:null,questions:[]});
  const [questionBusy, setQuestionBusy] = useState(false);
  const setup = useJobSetup({ isOpen, jobTitle: jobData.title, onResume: fields => setJobData(current => ({ ...current, ...fields,
    responsibilities: Array.isArray(fields.responsibilities) ? fields.responsibilities.join('\n') : fields.responsibilities ?? current.responsibilities,
    requirements: Array.isArray(fields.requirements) ? fields.requirements.join('\n') : fields.requirements ?? current.requirements,
    benefits: Array.isArray(fields.benefits) ? fields.benefits.join('\n') : fields.benefits ?? current.benefits,
  })) });
  useEffect(()=>{if(setup.configuration?.oa.source)setAuthoringMode(setup.configuration.oa.source==='ai'?'ai':'manual');},[setup.configuration?.oa.source]);
  const saveHiringDraft = async () => {
    try { await setup.save(jobData); } catch (error) { notify(error.message); }
  };
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [skillInput, setSkillInput] = useState('');
  const [filteredSuggestions, setFilteredSuggestions] = useState([]);
  const [jdFile, setJdFile] = useState(null);
  const [aiPrompt, setAiPrompt] = useState('');
  const [isAiGenerating, setIsAiGenerating] = useState(false);
  const [authoringMode,setAuthoringMode] = useState('manual');
  const [generation,setGeneration] = useState(null);
  const [createdJobId, setCreatedJobId] = useState(null);
  
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
    setJdFile(null);
    setAiPrompt('');
    setQuestionDrafts({editor:null,questions:[]}); setCreatedJobId(null); setGeneration(null); setAuthoringMode('manual');
  }, []);

  const recovery=useJobDraftRecovery({isOpen,hold:setup.loading||!!setup.savedDraft,value:{jobFields:jobData,configuration:setup.configuration,questionDrafts,createdJobId,authoringMode,generation,aiPrompt,jdFileName:jdFile?.name||''},onRestore:value=>{
    setCreatedJobId(value.createdJobId||null);setAuthoringMode(value.authoringMode||'manual');setGeneration(value.generation||null);setQuestionDrafts(value.questionDrafts||{editor:null,questions:[]});setJobData(value.jobFields);if(value.configuration)setup.restoreConfiguration(value.configuration);
setAiPrompt(value.aiPrompt||'');
  }});

  const flushRecovery=recovery.flush;
  const handleCancel = useCallback(() => {
    if (questionBusy || isSubmitting) return;
    flushRecovery();
    resetForm();
    onClose();
  }, [resetForm, onClose, flushRecovery, questionBusy, isSubmitting]);

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

  // Default application window: seven days.
  const getDefaultDeadline = () => {
    const date = new Date();
    date.setDate(date.getDate() + 7);
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
      if (e.key === 'Escape' && isOpen && !questionBusy && !isSubmitting) {
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
  }, [isOpen, handleCancel, questionBusy, isSubmitting]);

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setJobData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (questionBusy || isSubmitting || isAiGenerating || (generation?.key&&!['completed','failed'].includes(generation.state))) return;
    if (questionDrafts.editor) { notify('Save or discard the open question before saving this job.'); revealJobSection(dialogRef.current,'oa'); return; }
    
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
      let id = createdJobId;
      if (!id) {
        const reference = await setup.save(jobData);
        const success = await onJobCreate({ ...jobData, ...reference, gaze_proctoring: Boolean(jobData.proctoring_config?.gaze_heatmap) }, jdFile);
        if (!success) return;
        id = success._id || success.id || success.job?._id;
        if (questionDrafts.questions.length && !id) throw new Error('The server did not return the saved job ID. Open Job details to attach your private questions.');
        if (id) { setCreatedJobId(id); recovery.checkpoint({createdJobId:id}); }
      }
      if(setup.configuration?.pipeline.oa_enabled)await attachJobQuestions(id, questionDrafts.questions,questionDrafts.replaceSelection);
      recovery.clear();
      resetForm();
      onClose();
    } catch (error) {
      notify(error.message || 'Could not save the job. Your hiring draft is retained.');
    } finally {
      setIsSubmitting(false);
    }
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
      <div ref={dialogRef} className={styles.modalContent} role="dialog" aria-modal="true" aria-labelledby="create-job-dialog-title">
        <div className={styles.modalHeader}>
          <div><h2 id="create-job-dialog-title">Create job</h2><p className={styles.headerHint}>Job details, assessment and hiring plan. Drafts autosave.</p></div>
          <div className={styles.headerActions}><button type="button" className={styles.aiShortcut} disabled={questionBusy || isSubmitting} onClick={()=>revealJobSection(dialogRef.current,'ai')}>Fill with AI</button></div>
          <button type="button" className={styles.closeButton} disabled={questionBusy || isSubmitting} onClick={handleCancel} aria-label="Close create job dialog">
            <i className="fa fa-times"></i>
          </button>
        </div>

        <nav className={styles.workspaceNav} aria-label="Job workspace sections">{[['details','Details'],['oa','Assessment'],['schedule','Schedule & credits'],['ai','AI drafting']].map(([section,label])=><button key={section} type="button" onClick={()=>revealJobSection(dialogRef.current,section)}>{label}</button>)}</nav>
        <form onSubmit={handleSubmit} onInvalidCapture={revealInvalidJobField} className={styles.jobForm}>
          {createdJobId && <aside role="status" className={styles.selectionNotice}>Job saved. Finish attaching the saved questions below; this will not create another job.<button type="button" disabled={isSubmitting} onClick={handleSubmit}>{isSubmitting?'Attaching...':'Retry attaching questions'}</button></aside>}
          <fieldset disabled={isSubmitting || setup.saving || questionBusy || !!createdJobId} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
          <JobDraftNotice setup={setup} draft={recovery} loading={setup.loading}/>
          <SetupNotice setup={setup} />
          {isAiGenerating&&<p role="status" className={styles.selectionNotice}>AI is preparing your draft. You can close and resume later. Save the job after generation finishes.</p>}
          <div>
          {authoringMode==='manual'&&<JobTemplatePicker onSelect={applyTemplate}/>}

          <div className={styles.formGrid} data-job-section="details">
            {/* Job Title with Suggestions */}
            <div className={styles.formGroup}>
              <label htmlFor="create-job-title">Job Title *</label>
              <input id="create-job-title"
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
              <label htmlFor="create-job-department">Department *</label>
              <div className={styles.inputWithDropdown}>
                <input id="create-job-department"
                  type="text"
                  name="department"
                  className={styles.enhancedInput}
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
              <label htmlFor="create-job-location">Location *</label>
              <div className={styles.inputWithDropdown}>
                <input id="create-job-location"
                  type="text"
                  name="location"
                  className={styles.enhancedInput}
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
              <label htmlFor="create-job-type">Job Type *</label>
              <select id="create-job-type"
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
              <label htmlFor="create-job-experience">Experience Required *</label>
              <div className={styles.inputWithDropdown}>
                <input id="create-job-experience"
                  type="text"
                  name="experience"
                  className={styles.enhancedInput}
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
              <label htmlFor="create-job-salary">Salary Range *</label>
              <div className={styles.inputWithDropdown}>
                <input id="create-job-salary"
                  type="text"
                  name="salary"
                  className={styles.enhancedInput}
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
            <div className={styles.formGroup} hidden={setup.enabled}>
              <label htmlFor="create-job-deadline">Application Deadline * <span className={styles.autoFilled}> Suggested date</span></label>
              <input id="create-job-deadline"
                type="date"
                name="deadline"
                  className={styles.enhancedInput}
                value={jobData.deadline}
                onChange={handleInputChange}
                required={!setup.enabled}
                min={new Date().toISOString().split('T')[0]}
              />
              <div className={styles.helpText}>
                 Default: 7 days from today
              </div>
            </div>

            {/* Job Status */}
            <div className={styles.formGroup}>
              <label htmlFor="create-job-status">Job Status * <span className={styles.smartIndicator}> Status</span></label>
              <select id="create-job-status"
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
              <label htmlFor="create-job-minimum_cv_score">Minimum CV Score * <span className={styles.smartIndicator}> Screening threshold</span></label>
              <input id="create-job-minimum_cv_score"
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
              <details className={styles.formAccordion}><summary>Interview monitoring</summary>
              <div className={styles.proctoringSection}>
                <div className={styles.creditWarning}>
                  <i className="fa fa-exclamation-triangle"></i>
                  <PricingNote setup={setup} />
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
                Disabled monitoring checks are labelled in reports.
              </div></details>
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
          <details className={styles.formAccordion} data-job-section="description"><summary>Job description, responsibilities & benefits</summary><div className={styles.textAreasSection}>
            <div className={styles.formGroup}>
              <label htmlFor="create-job-description">
                Job Description * 
                <span className={styles.smartIndicator}> Suggestions</span>
              </label>
              <textarea id="create-job-description"
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
              <label htmlFor="create-job-responsibilities">
                Key Responsibilities
                <span className={styles.optional}>(Optional)</span>
              </label>
              <textarea id="create-job-responsibilities"
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
              <label htmlFor="create-job-requirements">
                Requirements & Qualifications
                <span className={styles.optional}>(Optional)</span>
              </label>
              <textarea id="create-job-requirements"
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
              <label htmlFor="create-job-benefits">
                Benefits & Perks
                <span className={styles.optional}>(Optional)</span>
              </label>
              <textarea id="create-job-benefits"
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
          </div></details>

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

          </div>
          <JobHiringSections templateControls={<RoleAssessmentTemplateControls onMode={setAuthoringMode} setup={setup} jobTitle={jobData.title} value={questionDrafts} onChange={setQuestionDrafts} onBusy={setQuestionBusy} blocked={questionBusy||isAiGenerating}/>} onAuthoringMode={setAuthoringMode} questionEditor={setup.configuration?.pipeline.oa_enabled ? <JobQuestionDrafts configuration={setup.configuration.oa} value={questionDrafts} onChange={value=>{setQuestionDrafts(value);if(value.questions!==questionDrafts.questions)setup.setConfiguration(current=>questionDraftConfiguration(current,value.questions));}} onBusy={setQuestionBusy} mode={authoringMode}/> : null} setup={setup} onSaveDraft={saveHiringDraft} jobStatus={jobData.status} />
          <details className={styles.formAccordion} data-job-section="ai"><summary>Fill with AI - {setup.catalog?.prices?.ai_jd??'loading'} credits for the complete draft</summary>
          <JobAIDraftBuilder jobTitle={jobData.title} mode={authoringMode} onMode={mode=>{setAuthoringMode(mode);setup.setConfiguration(current=>current?({...current,oa:{...current.oa,source:mode}}):current);}}
            setup={setup} prompt={aiPrompt} onPrompt={setAiPrompt} file={jdFile} onFile={setJdFile} generation={generation}
            onGeneration={value=>{setGeneration(value);recovery.checkpoint({generation:value});}} onBusy={setIsAiGenerating} isOpen={isOpen}
            onReady={result=>{
              const ai=result.job_data;
              const next={...jobData,...ai,status:'draft',deadline:jobData.deadline||getDefaultDeadline(),
                responsibilities:Array.isArray(ai.responsibilities)?ai.responsibilities.join('\n'):ai.responsibilities||'',
                requirements:Array.isArray(ai.requirements)?ai.requirements.join('\n'):ai.requirements||'',benefits:Array.isArray(ai.benefits)?ai.benefits.join('\n'):ai.benefits||''};
              const nextConfiguration={...(setup.configuration||result.configuration),oa:result.configuration.oa};
              setJobData(next);setup.restoreConfiguration(nextConfiguration);setQuestionDrafts({editor:null,questions:result.questions,replaceSelection:true});
              recovery.checkpoint({jobFields:next,configuration:nextConfiguration,generation:{key:generation?.key,state:'completed'},questionDrafts:{editor:null,questions:result.questions,replaceSelection:true},wizardStep:0});
              revealJobSection(dialogRef.current,result.questions.length?'oa':'description');
            }}/>
          </details>
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
                disabled={isSubmitting || isAiGenerating || !setup.catalog || !setup.ready || !jobData.title || !jobData.department || !jobData.location || jobData.skills.length === 0}
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
                  {['title','department','location','type','experience','description','skills'].filter(key => Array.isArray(jobData[key]) ? jobData[key].length > 0 : String(jobData[key] || '').trim()).length}/7 Fields Completed
                </span>
                <span className={styles.stat}>
                  <i className="fa fa-tag"></i>
                  {jobData.skills.length} Skills Added
                </span>
                <span className={styles.stat}>
                  <i className="fa fa-clock"></i>
                  Review before saving
                </span>
              </div>
            </div>
          </div>
          </fieldset>
        </form>
      </div>
    </div>
  );
};

export default JobCreationModal;

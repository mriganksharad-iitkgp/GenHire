import { PROCTORING_OPTIONS } from "shared/constants/proctoringOptions";
import React, { useState, useEffect, useRef, useMemo } from 'react';
import { INDIA_LOCATION_OPTIONS } from 'shared/constants/jobTaxonomy';
import ConfirmDialog from 'shared/components/ui/ConfirmDialog';
import styles from './JobForm.module.css';
import proctoringStyles from './JobForm.module.css';
import useJobSetup from '../hooks/useJobSetup';
import useJobDraftRecovery from '../hooks/useJobDraftRecovery';
import JobDraftNotice from './JobDraftNotice';
import JobAIDraftBuilder from './JobAIDraftBuilder';
import questionDraftConfiguration from '../utils/questionDraftConfiguration';
import {getAssessmentWorkspace} from '../api/assessmentAuthoringApi';
import useJobWizardScroll from '../hooks/useJobWizardScroll';
import JobQuestionDrafts from './JobQuestionDrafts';
import attachJobQuestions from '../utils/attachJobQuestions';
import JobTemplatePicker from './JobTemplatePicker';
import {SetupNotice,PricingNote} from './HiringSetupWizard';
import RoleAssessmentTemplateControls from './RoleAssessmentTemplateControls';
import JobHiringSections,{revealJobSection,revealInvalidJobField} from './JobHiringSections';

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

// Job status workflow with one-way progression
const JOB_STATUSES = [
  { value: 'draft', label: 'Draft', description: 'Job is being prepared', color: '#6b7280' },
  { value: 'active', label: 'Active', description: 'Job is live and accepting applications', color: '#047857' },
  { value: 'paused', label: 'Paused', description: 'Job is temporarily stopped', color: '#92400e' },
  { value: 'closed', label: 'Closed', description: 'Job is closed, no longer accepting applications', color: '#b91c1c' }
];

const JobEditModal = ({ isOpen, onClose, onJobUpdate, jobData: initialJobData, showToast }) => {
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
    minimum_cv_score: 50,
    proctoring_config: {
      voice_detection: true,
      object_detection: true,
      eyeball_tracking: true,
      gaze_heatmap: true,
      ai_detection: false,
      dual_camera: false,
    }
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const dialogRef = useJobWizardScroll(isOpen);
  const [questionDrafts, setQuestionDrafts] = useState({editor:null,questions:[]});
  const [questionBusy, setQuestionBusy] = useState(false);
  const [questionsLoadError,setQuestionsLoadError]=useState('');
  const [questionReload,setQuestionReload]=useState(0);
  const [authoringMode,setAuthoringMode]=useState('manual');
  const [aiPrompt,setAiPrompt]=useState('');
  const [generation,setGeneration]=useState(null);
  const [isAiGenerating,setIsAiGenerating]=useState(false);
  const setup = useJobSetup({ isOpen, jobTitle:jobData.title, jobId: initialJobData?._id || initialJobData?.id, initialJobData,
    onResume: fields => setJobData(current => ({ ...current, ...fields,
      responsibilities: toString(fields.responsibilities ?? current.responsibilities),
      requirements: toString(fields.requirements ?? current.requirements),
      benefits: toString(fields.benefits ?? current.benefits),
    })) });
  useEffect(()=>{if(setup.configuration?.oa.source)setAuthoringMode(setup.configuration.oa.source==='ai'?'ai':'manual');},[setup.configuration?.oa.source]);
  useEffect(()=>{
    if(!isOpen||!setup.assessmentBlueprintId)return;
    let cancelled=false;setQuestionBusy(true);setQuestionsLoadError('');
    getAssessmentWorkspace(setup.assessmentBlueprintId).then(workspace=>{
      if(!cancelled)setQuestionDrafts(current=>current.questions.length||current.editor?current:{...current,questions:(workspace.questions||[]).map(q=>({_id:q._id,type:q.content.type,title:q.content.title,content:q.content})),replaceSelection:true});
    }).catch(err=>{if(!cancelled)setQuestionsLoadError(err.message||'Assessment questions could not be loaded.');})
      .finally(()=>{if(!cancelled)setQuestionBusy(false);});
    return()=>{cancelled=true;};
  },[isOpen,setup.assessmentBlueprintId,questionReload]);
  const saveHiringDraft = async () => {
    try { await setup.save(jobData); } catch (error) {
      showToast ? showToast(error.message, 'error') : alert(error.message);
    }
  };
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [skillInput, setSkillInput] = useState('');
  const [filteredSuggestions, setFilteredSuggestions] = useState([]);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  
  const departmentDropdownRef = useRef(null);
  const locationDropdownRef = useRef(null);
  const experienceDropdownRef = useRef(null);
  const salaryDropdownRef = useRef(null);
  const skillsDropdownRef = useRef(null);
  const statusDropdownRef = useRef(null);
  const dropdownRefs = useMemo(() => ({
    department: departmentDropdownRef,
    location: locationDropdownRef,
    experience: experienceDropdownRef,
    salary: salaryDropdownRef,
    skills: skillsDropdownRef,
    status: statusDropdownRef
  }), []);

  const recovery=useJobDraftRecovery({isOpen,hold:setup.loading||!!setup.savedDraft,jobId:initialJobData?._id||initialJobData?.id,value:{jobFields:jobData,configuration:setup.configuration,questionDrafts,authoringMode,aiPrompt,generation},onRestore:value=>{
    setAuthoringMode(value.authoringMode||'manual');setAiPrompt(value.aiPrompt||'');setGeneration(value.generation||null);setQuestionDrafts(value.questionDrafts||{editor:null,questions:[]});setJobData(value.jobFields);if(value.configuration)setup.restoreConfiguration(value.configuration);

  }});

  // Initialize job data when modal opens or initialJobData changes
  useEffect(() => {
    if (isOpen && initialJobData) {
      setQuestionDrafts({editor:null,questions:[]});setGeneration(null);setAuthoringMode('manual');setAiPrompt('');
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
        minimum_cv_score: initialJobData?.minimum_cv_score ?? 50,
        proctoring_config: initialJobData?.proctoring_config || {
          voice_detection: true,
          object_detection: true,
          eyeball_tracking: true,
          gaze_heatmap: true,
          ai_detection: false,
          dual_camera: false,
        }
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
  }, [dropdownRefs]);

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
      if (e.key === 'Escape' && isOpen && !questionBusy && !isSubmitting) {
        setShowCancelConfirm(true);
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, questionBusy, isSubmitting]);

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (questionBusy || isSubmitting || isAiGenerating || (generation?.key&&!['completed','failed'].includes(generation.state))) return;
    if(questionsLoadError){showToast?.('Reload assessment questions before updating this job.', 'error');return;}
    if (questionDrafts.editor) { const message='Save or discard the open question before saving this job.'; showToast ? showToast(message, 'error') : alert(message); revealJobSection(dialogRef.current,'oa'); return; }
    
    if (!jobData.title.trim()) {
      showToast ? showToast('Please enter a job title', 'error') : alert('Please enter a job title');
      return;
    }

    setIsSubmitting(true);
    
    try {
      const reference = await setup.save(jobData);
      const success = await onJobUpdate({
        _id: initialJobData?._id || initialJobData?.id, // Include the job ID
        ...jobData,
        ...reference,
        skills: jobData.skills,
        responsibilities: jobData.responsibilities.split('\n').filter(item => item.trim()),
        requirements: jobData.requirements.split('\n').filter(item => item.trim()),
        benefits: jobData.benefits.split('\n').filter(item => item.trim()),
        status: jobData.status,
        proctoring_config: jobData.proctoring_config,
        gaze_proctoring: Boolean(jobData.proctoring_config?.gaze_heatmap)
      });
      
      if (success !== false) { if(setup.configuration?.pipeline.oa_enabled)await attachJobQuestions(initialJobData?._id || initialJobData?.id, questionDrafts.questions,questionDrafts.replaceSelection); recovery.clear(); setQuestionDrafts({editor:null,questions:[]}); onClose(); }
    } catch (error) {
      console.error('Error updating job:', error);
      showToast
        ? showToast(error.message || 'Failed to update job. Please try again.', 'error')
        : alert(error.message || 'Failed to update job. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle input changes
  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setJobData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  // Handle cancel
  const handleCancel = () => {
    if (questionBusy || isSubmitting) return;
    setShowCancelConfirm(true);
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
      <div ref={dialogRef} className={styles.modalContent} role="dialog" aria-modal="true" aria-labelledby="edit-job-dialog-title">
        <div className={styles.modalHeader}>
          <div><h2 id="edit-job-dialog-title">Edit job</h2><p className={styles.headerHint}>Update the role and hiring plan. Existing candidates keep their current workflow.</p></div>
          <div className={styles.headerActions}><button type="button" className={styles.aiShortcut} disabled={questionBusy || isSubmitting} onClick={()=>revealJobSection(dialogRef.current,'ai')}>Fill with AI</button></div>
          <button type="button" disabled={questionBusy || isSubmitting} onClick={handleCancel} className={styles.closeButton} aria-label="Close">
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} onInvalidCapture={revealInvalidJobField} className={styles.jobForm}>
          <fieldset disabled={isSubmitting || setup.saving || questionBusy} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
          <JobDraftNotice setup={setup} draft={recovery} loading={setup.loading}/>
          <SetupNotice setup={setup} />
          {isAiGenerating&&<p role="status" className={styles.selectionNotice}>AI is preparing your draft. You can close and resume later. Save the job after generation finishes.</p>}
          {questionsLoadError&&<div role="alert" className={styles.aiError}>{questionsLoadError}<button type="button" onClick={()=>setQuestionReload(n=>n+1)}>Retry loading questions</button></div>}
          <div>
          {authoringMode==='manual'&&<JobTemplatePicker editing onSelect={(name,t)=>setJobData(current=>({...current,title:name,department:t.department,skills:[...t.skills],experience:t.experience,salary:t.salary,description:t.description,responsibilities:t.responsibilities.join('\n'),requirements:t.requirements.join('\n'),benefits:t.benefits.join('\n')}))}/>}
          {/* Form Grid */}
          <div className={styles.formGrid}>
            {/* Job Title */}
            <div className={styles.formGroup}>
              <label htmlFor="edit-job-title">
                Job Title
                <span className={styles.smartIndicator}> Suggestions</span>
              </label>
              <input id="edit-job-title"
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
              <label htmlFor="edit-job-department">
                Department
                <span className={styles.autoFilled}> Suggestions</span>
              </label>
              <div className={styles.inputWithDropdown}>
                <input id="edit-job-department"
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
              <label htmlFor="edit-job-location">
                Location
                <span className={styles.autoFilled}> Locations</span>
              </label>
              <div className={styles.inputWithDropdown}>
                <input id="edit-job-location"
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
              <label htmlFor="edit-job-type">Job Type</label>
              <select id="edit-job-type"
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
              <label htmlFor="edit-job-experience">
                Experience Level
                <span className={styles.autoFilled}> Suggestions</span>
              </label>
              <div className={styles.inputWithDropdown}>
                <input id="edit-job-experience"
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
              <label htmlFor="edit-job-salary">
                Salary Range
                <span className={styles.autoFilled}> Salary guide</span>
              </label>
              <div className={styles.inputWithDropdown}>
                <input id="edit-job-salary"
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
              <label htmlFor="edit-job-status">
                Job Status
                <span className={styles.smartIndicator}> Status</span>
              </label>
              <div className={styles.statusContainer}>
                <select id="edit-job-status"
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
              <label htmlFor="edit-job-minimum_cv_score">
                Minimum CV Score
                <span className={styles.smartIndicator}> Screening threshold</span>
              </label>
              <input id="edit-job-minimum_cv_score"
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

            {/* Interview monitoring */}
            <div className={styles.formGroup} style={{gridColumn: '1 / -1'}}>
              <details className={styles.formAccordion}><summary>Interview monitoring</summary>
              <div className={proctoringStyles.proctoringSection}>
                <div className={proctoringStyles.creditWarning}>
                  <i className="fa fa-exclamation-triangle"></i>
                    <PricingNote setup={setup} editing />
                </div>
                {PROCTORING_OPTIONS.map(opt => (
                  <div key={opt.key} className={proctoringStyles.proctoringToggle}>
                    <div className={proctoringStyles.proctoringInfo}>
                      <span className={proctoringStyles.proctoringIcon}><i className={`fa ${opt.icon}`} aria-hidden="true" /></span>
                      <div>
                        <strong>{opt.label}</strong>
                        <p>{opt.desc}</p>
                      </div>
                    </div>
                    <label className={proctoringStyles.toggleSwitch}>
                      <input
                        aria-label={opt.label}
                        type="checkbox"
                        checked={jobData.proctoring_config?.[opt.key] ?? !['dual_camera', 'ai_detection'].includes(opt.key)}
                        onChange={(e) => setJobData(prev => ({
                          ...prev,
                          proctoring_config: {
                            ...prev.proctoring_config,
                            [opt.key]: e.target.checked
                          }
                        }))}
                      />
                      <span className={proctoringStyles.slider}></span>
                    </label>
                  </div>
                ))}
              </div>
              <div className={styles.helpText}>
                Disabled monitoring checks are labelled in reports.
              </div></details>
            </div>


          </div>

          {/* Skills Section */}
          <div className={styles.formGroup} ref={dropdownRefs.skills}>
            <label>
              Required Skills
              <span className={styles.smartIndicator}> Suggestions</span>
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

          <details className={styles.formAccordion} data-job-section="description"><summary>Job description, responsibilities & benefits</summary>
          {/* Description */}
          <div className={styles.formGroup}>
            <label htmlFor="edit-job-description">
              Job Description
              <span className={styles.smartIndicator}> Suggestions</span>
            </label>
            <textarea id="edit-job-description"
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
            <label htmlFor="edit-job-responsibilities">
              Key Responsibilities
              <span className={styles.autoFilled}> Auto-list</span>
            </label>
            <textarea id="edit-job-responsibilities"
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
            <label htmlFor="edit-job-requirements">
              Requirements
              <span className={styles.autoFilled}> Auto-list</span>
            </label>
            <textarea id="edit-job-requirements"
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
            <label htmlFor="edit-job-benefits">
              Benefits & Perks
              <span className={styles.optional}> Optional</span>
            </label>
            <textarea id="edit-job-benefits"
              name="benefits"
              value={jobData.benefits}
              onChange={handleInputChange}
              placeholder="Enter each benefit on a new line..."
              className={styles.smartTextarea}
              rows="3"
            />
          </div>

          </details>
          {/* Form Actions */}
          </div>
          <JobHiringSections templateControls={<RoleAssessmentTemplateControls onMode={setAuthoringMode} setup={setup} jobTitle={jobData.title} value={questionDrafts} onChange={setQuestionDrafts} onBusy={setQuestionBusy} blocked={!!questionsLoadError||questionBusy||isAiGenerating}/>} onAuthoringMode={setAuthoringMode} questionEditor={setup.configuration?.pipeline.oa_enabled ? <JobQuestionDrafts configuration={setup.configuration.oa} value={questionDrafts} onChange={value=>{setQuestionDrafts(value);if(value.questions!==questionDrafts.questions)setup.setConfiguration(current=>questionDraftConfiguration(current,value.questions));}} onBusy={setQuestionBusy} mode={authoringMode}/> : null} setup={setup} onSaveDraft={saveHiringDraft} jobStatus={initialJobData?.status} editing />
          <details className={styles.formAccordion} data-job-section="ai"><summary>Fill with AI - {setup.catalog?.prices?.ai_jd??'loading'} credits for the complete draft</summary>
          <JobAIDraftBuilder jobTitle={jobData.title} mode={authoringMode} onMode={mode=>{setAuthoringMode(mode);setup.setConfiguration(current=>current?({...current,oa:{...current.oa,source:mode}}):current);}}
            setup={setup} prompt={aiPrompt} onPrompt={setAiPrompt} generation={generation}
            onGeneration={value=>{setGeneration(value);recovery.checkpoint({generation:value});}} onBusy={setIsAiGenerating} isOpen={isOpen}
            onReady={result=>{
              const ai=result.job_data;
              const next={...jobData,...ai,status:jobData.status,responsibilities:toString(ai.responsibilities),requirements:toString(ai.requirements),benefits:toString(ai.benefits)};
              const nextConfiguration={...(setup.configuration||result.configuration),oa:result.configuration.oa};
              setJobData(next);setup.restoreConfiguration(nextConfiguration);setQuestionDrafts({editor:null,questions:result.questions,replaceSelection:true});
              recovery.checkpoint({jobFields:next,configuration:nextConfiguration,generation:{key:generation?.key,state:'completed'},questionDrafts:{editor:null,questions:result.questions,replaceSelection:true},wizardStep:0});
              revealJobSection(dialogRef.current,result.questions.length?'oa':'description');
            }}/>
          </details>
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
              disabled={isSubmitting || isAiGenerating || !setup.catalog || !setup.ready}
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
          </fieldset>
        </form>
      </div>

      <ConfirmDialog
        isOpen={showCancelConfirm}
        onClose={() => setShowCancelConfirm(false)}
        onConfirm={() => {
          recovery.flush();
          setShowCancelConfirm(false);
          onClose();
        }}
        title="Close job editor?"
        message="Your progress is saved on this device when autosave is available. It has not updated the published job. You can resume it when you return."
        confirmText="Close editor"
        confirmVariant="primary"
      />
    </div>
  );
};

export default JobEditModal;

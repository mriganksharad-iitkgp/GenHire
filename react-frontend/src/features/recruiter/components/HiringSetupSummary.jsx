import React, { useEffect, useState } from 'react';
import { getHiringSetup } from '../api/jobSetupApi';
import styles from './HiringSetupWizard.module.css';
import AssessmentAuthoringPanel from './AssessmentAuthoringPanel';
import HiringActivationPanel from './HiringActivationPanel';
import RecruiterAssessmentQuestions from './RecruiterAssessmentQuestions';

export default function HiringSetupSummary({ job }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [authoringOpen, setAuthoringOpen] = useState(false);
  const [deliveryLoaded,setDeliveryLoaded]=useState(false);
  const id = job._id || job.id;
  useEffect(() => {
    let cancelled = false;
    setResult(null); setError('');
    setAuthoringOpen(false);setDeliveryLoaded(false);
    if (job.hiring_setup_version_id) getHiringSetup(id)
      .then(value => { if (!cancelled) setResult(value); })
      .catch(err => { if (!cancelled) setError(err.message || 'Hiring setup could not be loaded.'); });
    return () => { cancelled = true; };
  }, [id, job.hiring_setup_version_id]);
  if (!job.hiring_setup_version_id) return null;
  const version = result?.version;
  const c = version?.configuration;
  return <section className={styles.panel} aria-label="Saved hiring setup">
    <h3>Hiring setup {version ? `· version ${version.revision}` : ''}</h3>
    {error ? <p role="alert">{error}</p> : !c ? <p role="status">Loading hiring setup…</p> : <>
      <p>{job.status==='active'?'Job published':'Saved hiring plan'} · {c.pipeline.advancement === 'manual' ? 'Recruiter approves invitations' : 'Automatic OA invitations when screening clears'}</p>
      <p>Application review → AI screening{c.pipeline.oa_enabled ? ' → Online assessment' : ''}{c.pipeline.company_stages.map(s => ` → ${s.name}`).join('')}</p>
      <p>Screening minimum: {c.qualification.interview_minimum ?? 'Not configured'} · Required proctoring: {c.qualification.require_proctoring ? `${c.qualification.proctoring_minimum}%` : 'No'}</p>
      {c.pipeline.oa_enabled && <p>{c.oa.sections.filter(s => s.count > 0).map(s => `${s.count} ${s.type.toUpperCase()}`).join(' + ')} · {c.oa.duration_minutes} minutes · {c.oa.timer_mode === 'shared' ? 'Shared timer' : 'Section timers'} · {c.oa.source} authoring</p>}
      <p>Schedule timezone: {c.schedule.timezone}. Applications close {new Date(c.schedule.application_closes_at).toLocaleString('en-IN', { timeZone: c.schedule.timezone })}.</p>
      <p className={styles.notice}>{result.impact} {result.existing_application_count} existing applications. Edit the job to revise this plan.</p>
      {version.assessment_blueprint_id && result.authoring_enabled && <>
        <button type="button" aria-expanded={authoringOpen} onClick={() => setAuthoringOpen(value => !value)}>{authoringOpen ? 'Hide OA questions' : 'View OA questions (recruiter only)'}</button>
        {authoringOpen && <RecruiterAssessmentQuestions blueprintId={version.assessment_blueprint_id} />}
      </>}
      {result.authoring_enabled && <details key={`${id}-${job.hiring_setup_version_id}`} className={styles.accordion} onToggle={e=>{if(e.target===e.currentTarget&&e.currentTarget.open)setDeliveryLoaded(true);}}><summary>Assessment delivery tools</summary>
        <p className={styles.hint}>Job publication does not require this step. Use these tools to prepare assessment delivery.</p>
        {deliveryLoaded&&<>
          {version.assessment_blueprint_id&&<AssessmentAuthoringPanel blueprintId={version.assessment_blueprint_id}/>}
          <HiringActivationPanel job={job} setup={version} />
        </>}
      </details>}
    </>}
  </section>;
}

import React from 'react';
import HiringSetupWizard from './HiringSetupWizard';
import styles from './HiringSetupWizard.module.css';

export function revealJobSection(dialog, name) {
  const section=dialog?.querySelector(`[data-job-section="${name}"]`);
  if(!section)return;
  section.open=true;
  section.scrollIntoView?.({block:'start',behavior:'auto'});
  section.querySelector('summary')?.focus({preventScroll:true});
}

export function revealInvalidJobField(event) {
  let parent=event.target.parentElement;
  while(parent){if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement;}
}

export default function JobHiringSections({setup,questionEditor,onSaveDraft,onAuthoringMode,jobStatus,editing,templateControls}) {
  if(!setup.enabled)return <details className={styles.accordion} data-job-section="oa"><summary>Want to add an online assessment? Click to add</summary><p>Assessment settings are currently unavailable for this workspace. Your job details remain editable.</p><button type="button" onClick={setup.reload}>Reload assessment options</button></details>;
  if(!setup.configuration)return null;
  const common={setup,onSaveDraft,onAuthoringMode,jobStatus,editing,inline:true};
  return <div className={styles.singlePageSections}>
    <details className={styles.accordion} data-job-section="pipeline"><summary>Screening criteria & company rounds</summary>
      <HiringSetupWizard {...common} step={1}/>
    </details>
    <details className={styles.accordion} data-job-section="schedule"><summary>Application dates, schedule & credit review</summary>
      <HiringSetupWizard {...common} step={3}/>
    </details>
    <details className={styles.accordion} data-job-section="oa"><summary>{setup.configuration?.pipeline.oa_enabled?'Online assessment — included':'Want to add an online assessment? Click to add'}</summary>
      {templateControls||<label className={styles.toggle}><input type="checkbox" checked={!!setup.configuration?.pipeline.oa_enabled}
        onChange={e=>setup.setAssessmentEnabled(e.target.checked)}/>Include an online assessment</label>}
      {setup.configuration?.pipeline.oa_enabled&&<HiringSetupWizard {...common} step={2} questionEditor={questionEditor}/>}
    </details>
  </div>;
}

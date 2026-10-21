import React from 'react';
import styles from './HiringSetupWizard.module.css';
export default function JobDraftNotice({draft,loading,setup}) {
  const server=setup?.savedDraft, device=draft.pending;
  const resume=()=>{if(device){draft.resume();setup?.dismissSaved();}else setup?.resume();};
  const discard=()=>{draft.discard();setup?.dismissSaved();};
  return <aside className={device||server?styles.notice:styles.savedStatus} aria-label="Job draft recovery">
    {device||server?<><p>Resume your unfinished job{device?' and questions':''}. There is one working draft for this job.</p>
      <button type="button" disabled={loading} onClick={resume}>{device?'Resume device draft':'Resume saved draft'}</button>{' '}
      <button type="button" disabled={loading} onClick={discard}>Use current details</button></>:<p role="status">{draft.status||'Changes autosave on this device. Uploaded files must be reattached.'}</p>}
  </aside>;
}

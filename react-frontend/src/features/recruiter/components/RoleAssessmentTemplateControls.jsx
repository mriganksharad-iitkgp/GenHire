import {authoringError} from '../utils/authoringError';
import React,{useRef,useState} from 'react';
import {request} from 'shared/api/client';
import {JOB_TEMPLATES} from '../utils/jobTemplates';
import styles from './HiringSetupWizard.module.css';
export default function RoleAssessmentTemplateControls({setup,jobTitle,value,onChange,onBusy,onMode,blocked=false}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
  const [confirm,setConfirm]=useState(false),keys=useRef(new Map()),autoApplied=useRef(new Set());
  const role=JOB_TEMPLATES[jobTitle];
  const apply=async()=>{
    if(!role||blocked||value.editor)return;
    if(value.questions.length&&!confirm){setConfirm(true);return;}
    setBusy(true);onBusy(true);setError('');
    const payload={sql_engine:setup.configuration.oa.sql_engine,languages:setup.configuration.oa.languages,
      specialization:role.specialization};
    const signature=JSON.stringify([jobTitle,payload]);
    if(!keys.current.has(signature))keys.current.set(signature,crypto.randomUUID());
    try{
      const result=await request(`/job-setup/templates/${role.oaTemplateId}/apply`,{method:'POST',body:JSON.stringify({...payload,operation_key:keys.current.get(signature)})});
      setup.setConfiguration(current=>({...current,pipeline:{...current.pipeline,oa_enabled:true},oa:result.oa}));
      onMode?.('manual');
      onChange({editor:null,questions:result.questions.map(q=>({_id:q._id,title:q.content.title,type:q.content.type,content:q.content})),replaceSelection:true});
      setMessage(`Full ${jobTitle} OA loaded: ${result.questions.length} editable questions. Review and validate before activation. No credits charged.`);setConfirm(false);
    }catch(err){setError(authoringError(err));}
    finally{setBusy(false);onBusy(false);}
  };
  if(!setup.configuration)return null;
  return <div className={styles.templateControls}>
    <label className={styles.toggle}><input type="checkbox" checked={!!setup.configuration.pipeline.oa_enabled} disabled={busy||blocked}
      onChange={e=>{setup.setAssessmentEnabled(e.target.checked);if(e.target.checked&&role&&!value.questions.length&&!value.editor&&!autoApplied.current.has(jobTitle)){autoApplied.current.add(jobTitle);apply();}}}/>Include an online assessment</label>
    {setup.configuration.pipeline.oa_enabled&&role&&<div className={styles.questionActions}>
      <button type="button" disabled={busy||blocked||!!value.editor} onClick={apply}>{busy?'Loading complete template...':confirm?'Confirm replacement of selected questions':`Use full ${jobTitle} OA template`}</button>
      {confirm&&<button type="button" onClick={()=>setConfirm(false)}>Keep my questions</button>}
      <span className={styles.hint}>Questions, answers and tests included. Free to edit.</span>
    </div>}
    {error&&<p role="alert" className={styles.error}>{error}</p>}{message&&<p role="status" className={styles.hint}>{message}</p>}
  </div>;
}

import {authoringError} from '../utils/authoringError';
import React, { useEffect, useRef, useState } from 'react';
import { request } from 'shared/api/client';
import styles from './HiringSetupWizard.module.css';

export function sectionsForCounts(counts, minutes=90) {
  const rows=Object.entries(counts).filter(([,count])=>count>0);
  if(!rows.length)return [{type:'mcq',count:0,difficulty:{easy:0,medium:0,hard:0},marks:[],weight:0,duration_minutes:0}];
  const total=rows.reduce((sum,[kind,count])=>sum+count*({mcq:1,coding:5,sql:3}[kind]),0);
  let assigned=0, time=0;
  return rows.map(([type,count],index)=>{
    const last=index===rows.length-1, share=count*({mcq:1,coding:5,sql:3}[type])/total;
    const weight=last?100-assigned:Math.max(1,Math.floor(100*share));assigned+=weight;
    const duration_minutes=last?Math.max(1,minutes-time):Math.max(1,Math.floor(minutes*share));time+=duration_minutes;
    return {type,count,difficulty:{easy:0,medium:count,hard:0},marks:Array(count).fill(1),weight,duration_minutes};
  });
}

export default function JobAIDraftBuilder({mode,onMode,setup,prompt,onPrompt,file,onFile,generation,onGeneration,onReady,onBusy,isOpen,jobTitle=''}) {
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[status,setStatus]=useState(''),[uncertain,setUncertain]=useState(false);
  const ready=useRef(onReady), state=useRef(onGeneration), busyCallback=useRef(onBusy), delivered=useRef(null), mounted=useRef(true),posting=useRef(false),accept=useRef(null),generationRef=useRef(generation);
  generationRef.current=generation;
  ready.current=onReady;state.current=onGeneration;busyCallback.current=onBusy;
  const pending=!!generation?.key&&!['completed','failed'].includes(generation.state);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{busyCallback.current(busy||pending);},[busy,pending]);
  accept.current=(job,current)=>{
        setError('');setUncertain(false);setStatus(job.phase==='waiting_provider'?`AI is temporarily busy. ${job.completed_questions}/${job.total_questions} questions saved; resuming automatically. No extra credits.`:job.state==='queued'?'Queued for AI drafting. You can keep reviewing your hiring settings.':job.phase==='job_details'?'Drafting job details...':job.phase==='saving'?'Saving your complete draft...':`Preparing JD and questions: ${job.completed_questions}/${job.total_questions} questions ready.`);
        if(job.state==='completed') {
          if(delivered.current!==job.id){delivered.current=job.id;ready.current(job);}
          state.current({...current,key:current.key,id:job.id,state:'completed'});
          setStatus('JD and selected OA questions filled. Review the prepared fields before saving.');
        } else if(job.state==='failed') {
          state.current({...current,key:current.key,id:job.id,state:'failed'});
          setStatus('');
          const reason={cancelled:'Generation was cancelled.',invalid_generation:'AI returned incomplete or inconsistent question content.',external_outcome_unknown:'AI preparation was interrupted.',generation_disabled:'AI drafting is temporarily unavailable.',provider_invalid_json:'AI returned incomplete question content after automatic retries. Your brief was kept; no partial questions were attached.',provider_rate_limit_exhausted:'AI remained busy beyond the retry window. Try later or use a role template.',providers_unavailable:'AI providers could not respond. Check provider funding, quota and availability before trying again.',jd_generation_failed:'AI could not prepare the job details. Check provider availability and try again.',invalid_generated_job_details:'AI returned incomplete job fields. Try a clearer role brief.',invalid_generated_question:'AI returned a question that did not pass the content checks.',invalid_test_suite:'AI could not produce the required 15-20 coding testcases.',generation_failed:'Draft preparation encountered an internal error. Contact support if it repeats.'}[job.error_code]||'AI could not complete this draft.';
          setError(`${reason} The reserved credits were released. Your previous fields are unchanged.`);
        }
  };
  useEffect(()=>{
    if(!isOpen||!generation?.key||posting.current||['completed','failed'].includes(generation.state))return;
    let cancelled=false,inFlight=false;
    const poll=async()=>{
      if(inFlight)return;inFlight=true;
      try {
        const {generation:job}=await request(`/job-draft-generations/${encodeURIComponent(generation.key)}`);
        if(cancelled)return;
        accept.current(job,generationRef.current);
      } catch(err){if(!cancelled){setUncertain(true);if(err.status===404&&err.code==='not_found'){setStatus('Request not acknowledged yet. Retry the same request or cancel; do not start a second one.');setError('');}else setError(`${authoringError(err)} Checking will continue.`);}}
      finally{inFlight=false;}
    };
    poll();const timer=setInterval(poll,2000);
    return()=>{cancelled=true;clearInterval(timer);};
  },[isOpen,generation?.key,generation?.state,busy]);
  const c=setup.configuration, price=setup.catalog?.prices?.ai_jd;
  const changeOA=(key,value)=>setup.setConfiguration(current=>({...current,oa:{...current.oa,[key]:value}}));
  const start=async(retry=false)=>{
    if(busy||(pending&&!retry)||!c||!price)return;
    if(!prompt.trim()&&!file){setError('Describe the job or upload its JD.');return;}
    if(c.pipeline.oa_enabled&&!c.oa.sections.some(s=>s.count>0)){setError('Choose at least one OA question.');return;}
    posting.current=true;setBusy(true);setError('');setStatus('Sending draft request...');setUncertain(false);
    const key=retry?generation.key:crypto.randomUUID();
    const payload=retry?generation.payload:{prompt,configuration:{...c,oa:{...c.oa,source:'ai'}},operation_key:key,accepted_credits:price};
    if(!payload){posting.current=false;setBusy(false);setError('Reopen the original saved request to check its status.');return;}
    if(retry&&generation.fileName&&file?.name!==generation.fileName){posting.current=false;setBusy(false);setError('Reattach the original JD document before retrying the same request.');return;}
    state.current({key,state:'submitting',payload,fileName:file?.name||generation?.fileName||''});
    try {
      let body=JSON.stringify(payload);
      if(file){body=new FormData();Object.entries(payload).forEach(([name,value])=>body.append(name,typeof value==='string'?value:JSON.stringify(value)));body.append('jd_file',file);}
      const {generation:job}=await request('/job-draft-generations',{method:'POST',body});
      if(!mounted.current)return;
      state.current({key,id:job.id,state:job.state,payload,fileName:file?.name||''});
      accept.current(job,{key,payload,fileName:file?.name||''});
    } catch(err){
      if(!mounted.current)return;
      // Explicit HTTP rejections did not create an operation. Network uncertainty
      // retains the key and polls rather than risking a second billable request.
      if(err.data?.error_code==='generation_busy') {
        try {
          const {generation:active}=await request('/job-draft-generations/active');
          if(!mounted.current)return;
          state.current({key:active.operation_key,id:active.id,state:active.state});
          setStatus('Resuming your pending draft. The new brief was not charged.');return;
        } catch { /* Keep the original key visible for a safe retry. */ }
      }
      const rejected=['generation_disabled','invalid_pricing_configuration','atomicity_unavailable'].includes(err.data?.error_code);
      if(rejected||(err.status&&err.status<500&&err.data?.error_code!=='idempotency_conflict')){state.current(null);setStatus('');}
      setUncertain(true);
      setError(authoringError(err));
    } finally{posting.current=false;if(mounted.current)setBusy(false);}
  };
  return <section className={styles.builder} aria-label="Job drafting method">
    <div className={styles.modeChoices} role="group" aria-label="Creation method">
      <button type="button" aria-pressed={mode==='manual'} disabled={busy||pending} onClick={()=>onMode('manual')}>Fill manually · free</button>
      <button type="button" aria-pressed={mode==='ai'} disabled={busy||pending} onClick={()=>onMode('ai')}>Create with AI · {price??'loading'} credits total</button>
    </div>
    {mode==='manual'?<p className={styles.hint}>Fill the JD and add your own questions in Online assessment. No AI calls or authoring charges.</p>:<>
      <h3>One brief. Your JD and OA drafted together.</h3>
      <label className={styles.field}>Describe the job and assessment<textarea rows={3} maxLength={2000} value={prompt} onChange={e=>onPrompt(e.target.value)} disabled={pending||busy}
        placeholder="Role, experience, location, skills and the topics your OA should test..."/></label>
      <fieldset disabled={pending||busy} className={styles.sectionCard}>
        <label className={styles.toggle}><input type="checkbox" checked={!!c?.pipeline.oa_enabled} disabled={!c||!setup.enabled}
          onChange={e=>{
            if(e.target.checked&&jobTitle.trim())setup.setAssessmentEnabled(true);
            else setup.setConfiguration(current=>({...current,pipeline:{...current.pipeline,oa_enabled:e.target.checked},oa:{...current.oa,source:'ai',
              sections:e.target.checked?sectionsForCounts({mcq:0,coding:0,sql:0},current.oa.duration_minutes):current.oa.sections}}));
          }}/>Include an online assessment in this draft</label>
        {c?.pipeline.oa_enabled&&<>
          <div className={styles.grid}>{['mcq','coding','sql'].map(kind=><label key={kind} className={styles.field}>{kind.toUpperCase()} questions<input type="number" min={0} max={kind==='mcq'?100:10}
            value={c.oa.sections.find(s=>s.type===kind)?.count||0} onChange={e=>{
              const counts=Object.fromEntries(['mcq','coding','sql'].map(type=>[type,c.oa.sections.find(s=>s.type===type)?.count||0]));
              counts[kind]=Math.max(0,Math.min(kind==='mcq'?100:10,Math.floor(Number(e.target.value)||0)));
              setup.setConfiguration(current=>({...current,oa:{...current.oa,sections:sectionsForCounts(counts,c.oa.duration_minutes),timer_mode:'shared',revisit_allowed:true}}));
            }}/></label>)}</div>
          <p className={styles.hint}>Set a count above zero for each question type you want. Leave the others at zero.</p>
          <div className={styles.grid}>
            <label className={styles.field}>OA time (minutes)<input type="number" min={5} max={300} value={c.oa.duration_minutes} onChange={e=>{
              const minutes=Math.max(5,Math.min(300,Number(e.target.value)||5));
              setup.setConfiguration(current=>({...current,oa:{...current.oa,duration_minutes:minutes,timer_mode:'shared',revisit_allowed:true,
                sections:sectionsForCounts(Object.fromEntries(current.oa.sections.map(s=>[s.type,s.count])),minutes)}}));
            }}/></label>
            <label className={styles.field}>Question difficulty<select value={['easy','medium','hard'].find(d=>c.oa.sections.every(s=>s.difficulty[d]===s.count))||'balanced'} onChange={e=>{
              const level=e.target.value;
              changeOA('sections',c.oa.sections.map(s=>({...s,difficulty:level==='balanced'?{easy:Math.floor(s.count/3),medium:s.count-2*Math.floor(s.count/3),hard:Math.floor(s.count/3)}:{easy:0,medium:0,hard:0,[level]:s.count}})));
            }}><option value="balanced">Balanced / custom mix</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></label>
            {c.oa.sections.some(s=>s.type==='sql'&&s.count>0)&&<label className={styles.field}>SQL engine<select value={c.oa.sql_engine} onChange={e=>changeOA('sql_engine',e.target.value)}><option value="postgresql">PostgreSQL 17</option><option value="mysql">MySQL 8.4</option></select></label>}
            {c.oa.sections.some(s=>s.type==='mcq'&&s.count>0)&&<label className={styles.field}>MCQ answers<select value={c.oa.mcq_mode} onChange={e=>changeOA('mcq_mode',e.target.value)}><option value="single">Single correct</option><option value="multiple">Multiple correct</option><option value="mixed">Both types</option></select></label>}
          </div>
          {c.oa.sections.some(s=>s.type==='coding'&&s.count>0)&&<details className={styles.compactHelp}><summary>Coding languages and format</summary>
            <label className={styles.field}>Coding format<select value={c.oa.coding_contract} onChange={e=>changeOA('coding_contract',e.target.value)}><option value="stdin_stdout">Standard input/output</option><option value="function">Function signature</option></select></label>
            <div className={styles.languageChoices}>{[['python','Python'],['javascript','JavaScript'],['java','Java'],['cpp','C++']].map(([language,name])=><label key={language} className={styles.toggle}><input type="checkbox" checked={c.oa.languages.includes(language)} onChange={e=>changeOA('languages',e.target.checked?[...c.oa.languages,language]:c.oa.languages.filter(l=>l!==language))}/>{name}</label>)}</div>
          </details>}
          <p className={styles.hint}>AI supplies statements, answer keys, explanations, reference solutions and sample/hidden tests. You can edit every field afterwards.</p>
        </>}
      </fieldset>
        {onFile&&<label className={styles.field}>Optional JD document (PDF/TXT, max 10MB)<input type="file" accept=".pdf,.txt" disabled={busy||(pending&&!uncertain)} onChange={e=>{
          const selected=e.target.files?.[0];if(selected&&selected.size>10*1024*1024){setError('Choose a file smaller than 10MB.');return;}onFile(selected||null);
        }}/>{file?.name&&<span>{file.name}</span>}</label>}
      <p className={styles.hint}><strong>{price??'Loading price'} credits total</strong> for the JD and all selected OA questions.</p>
      <details className={styles.compactHelp}><summary>Credits and review</summary><p>No extra authoring charge per question. {setup.catalog?.prices?.oa_setup===0?'No separate OA setup fee.':'Activation fees appear in the credit review.'} A new generation costs the displayed amount again. Existing fields are replaced only after the whole draft succeeds. Review and execution validation follow before activation.</p></details>
      <button type="button" className={styles.primaryAction} disabled={busy||pending||!c||!price} onClick={()=>start()}>{pending||busy?'Preparing your draft...':c?.pipeline.oa_enabled?'Generate JD + OA questions':'Generate JD'}</button>
      {pending&&uncertain&&<button type="button" disabled={busy||!generation.payload} onClick={()=>start(true)}>Retry the same request · no duplicate charge</button>}
      {pending&&<button type="button" disabled={busy} onClick={async()=>{
        setBusy(true);setError('');
        try {
          await request(`/job-draft-generations/${encodeURIComponent(generation.key)}/cancel`,{method:'POST',body:'{}'});
          if(mounted.current){state.current({...generation,state:'failed'});setStatus('Generation cancelled. Any reserved credits were released; your existing fields are unchanged.');}
        } catch(err){if(mounted.current)setError(authoringError(err));}finally{if(mounted.current)setBusy(false);}
      }}>Cancel generation</button>}
      {status&&<p role="status" className={styles.hint}>{status}</p>}
      {error&&<p role="alert" className={styles.error}>{error}</p>}
    </>}
  </section>;
}

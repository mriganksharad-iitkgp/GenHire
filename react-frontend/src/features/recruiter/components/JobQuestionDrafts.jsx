import React, { useEffect, useRef, useState } from 'react';
import QuestionAccordionGroup from './QuestionAccordionGroup';
import AssessmentQuestionEditor from './AssessmentQuestionEditor';
import { newQuestion, prepareQuestion, editQuestion } from '../utils/questionEditor';
import { saveQuestionVersion, getQuestionVersion } from '../api/assessmentAuthoringApi';
import styles from './HiringSetupWizard.module.css';

export default function JobQuestionDrafts({ configuration, value, onChange, onBusy, mode='manual' }) {
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [error, setError] = useState('');
  const keys = useRef(new Map());
  const editorAnchor=useRef(null), focusRequested=useRef(false);
  useEffect(()=>{
    if(!focusRequested.current||!value.editor||!editorAnchor.current)return;
    focusRequested.current=false;
    editorAnchor.current.scrollIntoView?.({block:'start',behavior:'auto'});
    editorAnchor.current.querySelector('input,textarea,select')?.focus({preventScroll:true});
  });
  const save = async () => {
    setBusy(true); onBusy(true); setError('');
    try {
      const content = prepareQuestion(value.editor);
      const signature = JSON.stringify([content,value.activeVersion]);
      if (!keys.current.has(signature)) keys.current.set(signature, crypto.randomUUID());
      const { question } = await saveQuestionVersion({ content, previous_version_id:value.activeVersion||null, suite_policy:'oa_test_suite_v2', operation_key: keys.current.get(signature) });
      const entry={_id:question._id,title:question.content.title,type:question.content.type,content:question.content};
      onChange({ ...value, editor: null, activeVersion:null, questions:value.activeVersion ? value.questions.map(q=>q._id===value.activeVersion?entry:q) : [...value.questions.filter(q=>q._id!==question._id),entry] });
      setMessage('Private question saved. It will be attached when you save this job. No credits charged.');
    } catch (err) { setError(err.message || 'Could not save question. Your editor is retained.'); }
    finally { setBusy(false); onBusy(false); }
  };
  return <section className={styles.sectionCard} aria-label="Questions for this job">
    <h4>{mode==='ai'?'Your AI-prepared questions':'Add your own questions'}</h4>
    <details className={styles.compactHelp}><summary>Where question drafts are saved</summary><p>An unfinished editor autosaves on this device. Save private question version stores it in your question bank. Save hiring draft stores hiring settings only. Save the job to attach saved questions to its OA.</p></details>
    <p className={styles.hint}>{mode==='ai'?'Generated drafts are prefilled below. Review or edit them; no further generation payment is needed to attach these drafts.':'Enter statements, answers, reference solutions and testcases yourself. Manual authoring is free.'} Save the job to attach questions. Validation and approval follow before activation.</p>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {message && <p role="status" className={styles.hint}>{message}</p>}
    {mode==='manual'&&<div className={styles.draftActions}>{['mcq', 'coding', 'sql'].map(kind => <button key={kind} type="button" disabled={busy || !!value.editor || value.questions.length >= 120}
      onClick={() => { focusRequested.current=true;onChange({ ...value, activeVersion:null, editor: newQuestion(kind, configuration) }); setMessage(`${kind.toUpperCase()} editor opened below.`); }}>Add {kind.toUpperCase()} question</button>)}</div>}
    <div ref={editorAnchor} className={styles.editorAnchor}><AssessmentQuestionEditor value={value.editor} onChange={editor => onChange({ ...value, editor })} onSave={save} busy={busy} /></div>
    {value.editor && <button type="button" disabled={busy} onClick={() => onChange({ ...value, activeVersion:null, editor: null })}>Discard unsaved question</button>}
    {['mcq','coding','sql'].map(kind=>{
      const questions=value.questions.filter(q=>q.type===kind);
      return !!questions.length&&<QuestionAccordionGroup key={kind} label={`${kind.toUpperCase()} questions`} items={questions}
        title={(q,index)=>`${index+1}. ${q.title}`} render={q=><>
          {q.content&&<><p>{q.content.statement}</p>{q.content.mcq&&<ul>{q.content.mcq.options.map(o=><li key={o.id}>{o.text}{q.content.mcq.correct_option_ids.includes(o.id)?' (correct)':''}</li>)}</ul>}
            <p className={styles.hint}>{q.content.difficulty} · {q.content.marks} marks{q.content.coding?` · ${q.content.coding.tests.length} testcases`:q.content.sql?` · ${q.content.sql.datasets.length} datasets`:''}</p></>}
          <button type="button" disabled={busy||!!value.editor} onClick={async()=>{
            setBusy(true);onBusy(true);setError('');
            try{const content=q.content||(await getQuestionVersion(q._id)).question.content;focusRequested.current=true;onChange({...value,activeVersion:q._id,editor:editQuestion(content)});setMessage('Saved question opened in the prefilled editor above.');}
            catch(err){setError(err.message);}finally{setBusy(false);onBusy(false);}
          }}>Edit prefilled question</button>{' '}
          <button type="button" disabled={busy||!!value.editor} onClick={()=>onChange({...value,questions:value.questions.filter(item=>item._id!==q._id)})}>Remove from this job</button>
        </>}/>;
    })}
  </section>;
}

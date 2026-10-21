import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React,{useState} from 'react';
import {request} from 'shared/api/client';

export default function PracticeAssessmentReport({attemptId,oaRequest=request}){
  const [value,setValue]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  if(!attemptId)return null;
  return <section className={panelStyles.panel} aria-label="Practice assessment educational report"><button disabled={busy} onClick={async()=>{setBusy(true);setError('');try{setValue(await oaRequest(`/assessment-attempts/${attemptId}/evaluation`));}catch(err){setError(err.message);}finally{setBusy(false);}}}>View / refresh practice feedback</button>
    {error&&<p role="alert">{error}</p>}{value&&!value.result_available&&<p>{value.message}</p>}
    {value?.result_available&&<><h3>Objective practice score: {value.score}%</h3><p>These marks use deterministic grading. AI advice cannot change them.</p>
      <ul>{value.sections.map(s=><li key={s.type}>{s.type}: {s.earned}/{s.possible}, weight {s.weight}%</li>)}</ul>
      {value.questions.map(q=><details key={q.question_id}><summary>{q.title}: {q.earned}/{q.marks}</summary><p style={{whiteSpace:'pre-wrap'}}>{q.question.statement}</p>
        {q.question.mcq&&<ul>{q.question.mcq.options.map(option=><li key={option.id}>{option.text}{q.correct_option_ids.includes(option.id)?' — correct answer':''}</li>)}</ul>}<p>{q.explanation}</p></details>)}
      <h4>AI educational advice</h4><p>{value.ai_feedback.label}</p>{value.ai_feedback.state==='completed'?<><p>{value.ai_feedback.advice.summary}</p>{['strengths','improvements','practice_topics'].map(key=><div key={key}><strong>{key.replaceAll('_',' ')}</strong><ul>{value.ai_feedback.advice[key].map((text,index)=><li key={index}>{text}</li>)}</ul></div>)}</>:<p>Advice: {value.ai_feedback.state}. Your objective score and explanations remain available.</p>}
    </>}
  </section>;
}

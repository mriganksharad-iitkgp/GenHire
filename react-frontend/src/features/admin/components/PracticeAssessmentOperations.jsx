import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React,{useRef,useState} from 'react';
import {request,post} from 'shared/api/client';
import AssessmentIntegrityControls from 'features/recruiter/components/AssessmentIntegrityControls';
import PracticeAssessmentReport from 'features/assessment/components/PracticeAssessmentReport';

export default function PracticeAssessmentOperations({candidateId}){
  const [page,setPage]=useState(null),[reason,setReason]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const keys=useRef(new Map());
  const load=async(after)=>{const value=await request(`/admin/practice-assessments/${candidateId}${after?`?after=${after}`:''}`);setPage(old=>({...value,purchases:after?[...old.purchases,...value.purchases]:value.purchases}));};
  const run=async fn=>{setBusy(true);setError('');try{await fn();}catch(err){setError(err.message);}finally{setBusy(false);}};
  return <section className={panelStyles.panel} aria-label="Mock OA support operations"><h3>Mock OA support operations</h3><button disabled={busy} onClick={()=>run(()=>load())}>Inspect candidate mock OAs</button>
    {error&&<p role="alert">{error}</p>}<label>Verified platform failure evidence<textarea value={reason} maxLength={1000} onChange={e=>setReason(e.target.value)}/></label>
    <p>Only confirmed platform faults qualify for a technical refund. Ordinary incorrect/blank answers, disconnection and monitoring observations do not.</p>
    {page&&<><ul>{page.purchases.map(p=><li key={p.purchase_id}>{p.purchase_id}: {p.state}, {p.price.total_credits} quoted credits.
      <AssessmentIntegrityControls practice invitation={p.invitation} attemptId={p.attempt_id}/>{p.attempt_id&&<PracticeAssessmentReport attemptId={p.attempt_id}/>}
      {!['completed','failed','unavailable','expired'].includes(p.state)&&<button disabled={busy||reason.trim().length<20} onClick={()=>run(async()=>{if(!window.confirm('Confirm a verified platform failure? This ends participation and returns the applicable funds once.'))return;const signature=JSON.stringify([p.purchase_id,reason]);if(!keys.current.has(signature))keys.current.set(signature,crypto.randomUUID());await post(`/practice/assessments/${p.purchase_id}/platform-failure`,{operation_key:keys.current.get(signature),reason});await load();})}>Record platform failure and return funds</button>}
    </li>)}</ul>{page.next_cursor&&<button disabled={busy} onClick={()=>run(()=>load(page.next_cursor))}>Load older mock purchases</button>}</>}
  </section>;
}

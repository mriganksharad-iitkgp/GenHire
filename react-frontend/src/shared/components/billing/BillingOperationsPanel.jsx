import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React,{useState} from 'react';
import {request} from 'shared/api/client';

export default function BillingOperationsPanel(){
  const [page,setPage]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const load=async(after)=>{setBusy(true);setError('');try{const value=await request(`/billing-operations${after?`?after=${after}`:''}`);setPage(old=>({...value,operations:after?[...old.operations,...value.operations]:value.operations}));}catch(err){setError(err.message);}finally{setBusy(false);}};
  return <section className={panelStyles.panel} aria-label="Assessment purchases and refunds" aria-busy={busy}><h3>Assessment purchases and refunds</h3>
    <p>Reservations, captured charges and returned funds come from recorded billing operations. A reservation is not a completed charge.</p>
    <button disabled={busy} onClick={()=>load()}>Load / refresh purchase history</button>{error&&<p role="alert">{error}</p>}
    {page&&<><ul>{page.operations.map(op=><li key={op.operation_id}>{op.purpose.replaceAll('_',' ')} — {op.credits} credits; {op.state.replaceAll('_',' ')}; {op.refunded_credits} refunded. {new Date(op.created_at).toLocaleString()}
      {op.price_snapshot&&<ul>{op.price_snapshot.line_items.map(line=><li key={line.code}>{line.code.replaceAll('_',' ')}: {line.credits} × {line.quantity} ({line.unit.replaceAll('_',' ')})</li>)}</ul>}
      {op.refunds.map((refund,index)=><p key={index}>{refund.credits} credits returned: {refund.reason}</p>)}</li>)}</ul>{!page.operations.length&&<p>No assessment billing operations yet.</p>}
      {page.next_cursor&&<button disabled={busy} onClick={()=>load(page.next_cursor)}>Load more purchases</button>}</>}
  </section>;
}

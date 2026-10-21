import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React, { useRef, useState } from 'react';
import { request, post } from 'shared/api/client';

export default function CompanyReviewPanel({ applicationId }) {
  const [value, setValue] = useState(null), [history, setHistory] = useState(null), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [reason, setReason] = useState(''), [name, setName] = useState(''), [busy, setBusy] = useState(false);
  const keys = useRef(new Map());
  const load = async () => {
    const [review, timeline] = await Promise.all([request(`/applications/${applicationId}/company-review`), request(`/applications/${applicationId}/stages`)]);
    setValue(review); setHistory(timeline);
  };
  const perform = async action => {
    setBusy(true); setError(''); setNotice('');
    try {
      if (action === 'load') await load();
      else {
        const payload = { action, expected_revision: history.workflow.revision, reason };
        if (action === 'add_company_stage') payload.name = name;
        const signature = JSON.stringify(payload);
        if (!keys.current.has(signature)) keys.current.set(signature, crypto.randomUUID());
        const operation_key = keys.current.get(signature);
        if (['clear', 'not_clear', 'review', 'hire', 'reject', 'close'].includes(action)) await post(`/applications/${applicationId}/stage-actions`, { ...payload, operation_key });
        else await post(`/applications/${applicationId}/company-actions`, { ...payload, operation_key });
        setNotice('Decision saved.'); await load(); window.dispatchEvent(new Event('hiring-workflow-updated'));
      }
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const workflow = history?.workflow, stage = workflow?.stages.find(s => s.stage_id === workflow.current_stage_id);
  const active = workflow?.lifecycle === 'active', disabled = busy || reason.trim().length < 10 || !value?.enabled;
  const button = (action, label, extra = false) => <button type="button" disabled={disabled || extra} onClick={() => perform(action)}>{label}</button>;
  return <section className={panelStyles.panel} aria-label="Company hiring review" style={{ marginTop: 16 }}>
    <h4>Company hiring decisions</h4>
    <button type="button" disabled={busy} onClick={() => perform('load')}>Load / refresh decisions and timeline</button>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {value && <>
      <p>{workflow?.workflow_label}. Objective recommendation: {value.objective_recommendation.replaceAll('_', ' ')}. Recruiter OA decision: {value.decision?.outcome?.replaceAll('_', ' ') || 'pending'}. Candidate result: {value.released ? 'released' : 'withheld'}.</p>
      {value.integrity_hold && <p>Integrity review is unresolved. Review the evidence before qualifying this candidate.</p>}
      {!value.enabled && <p>Company decision writes are disabled.</p>}
      <label>Decision reason (private)<textarea maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {active && stage?.type === 'oa' && stage.state === 'completed' && <>
          {button('qualify', 'Approve OA qualification', value.integrity_hold)}{button('not_qualify', 'Record OA not qualified')}{button('hold', 'Hold OA for review')}
        </>}
        {value.decision && <>{button('release', 'Release candidate summary')}{value.released && button('revoke_release', 'Withdraw result release')}</>}
        {active && stage?.type === 'company' && <>{button('clear', 'Company round cleared')}{button('not_clear', 'Company round not cleared')}{button('review', 'Company round needs review')}
          {stage.outcome === 'cleared' && button('hire', 'Record hired outcome')}
        </>}
        {active && stage?.state === 'completed' && <>{button('advance', 'Shortlist / advance to next company round')}</>}
        {active && <>{button('reject', 'Record final rejection')}{button('close', 'Close application')}</>}
      </div>
      {active && ['screening', 'oa', 'company'].includes(stage?.type) && ['completed', 'eligible'].includes(stage?.state) && <div style={{ marginTop: 12 }}><label>Additional company round<input value={name} maxLength={80} onChange={e => setName(e.target.value)} placeholder="Technical interview / HR discussion" /></label>{button('add_company_stage', 'Add company-managed round', !name.trim())}<p>Your company arranges and conducts these interviews. Adding a round does not notify candidates.</p></div>}
      <ol aria-label="Recorded hiring events">{history.events.map(event => <li key={event.revision}>{new Date(event.occurred_at).toLocaleString()} — {event.action.replaceAll('_', ' ')}{event.reason && `: ${event.reason}`}</li>)}</ol>
      {history.has_more && <button type="button" disabled={busy} onClick={async () => {
        setBusy(true); setError('');
        try { const page = await request(`/applications/${applicationId}/stages?after_revision=${history.next_after_revision}`); setHistory(old => ({ ...page, events: [...old.events, ...page.events] })); }
        catch (err) { setError(err.message); } finally { setBusy(false); }
      }}>Load more recorded events</button>}
    </>}
  </section>;
}

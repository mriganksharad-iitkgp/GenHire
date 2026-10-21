import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React, { useRef, useState } from 'react';
import { request, post, requestBlob } from 'shared/api/client';
import { saveBlob } from '../api/jobExportApi';

export default function CompanyPipelinePanel({ jobId }) {
  const [page, setPage] = useState(null), [selected, setSelected] = useState([]), [outcomes, setOutcomes] = useState(null);
  const [stage, setStage] = useState(''), [lifecycle, setLifecycle] = useState(''), [qualification, setQualification] = useState('');
  const [reason, setReason] = useState(''), [action, setAction] = useState('advance'), [subject, setSubject] = useState(''), [message, setMessage] = useState('');
  const [preview, setPreview] = useState(null), [approved, setApproved] = useState(false), [batch, setBatch] = useState(null), [delivery, setDelivery] = useState(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const keys = useRef(new Map());
  if (!jobId) return <p>Select one job to compare its hiring stages, shortlist candidates, export contacts or prepare a company email.</p>;
  const filters = () => new URLSearchParams(Object.fromEntries(Object.entries({ stage, lifecycle, qualification }).filter(([, v]) => v))).toString();
  const keyFor = payload => { const s = JSON.stringify(payload); if (!keys.current.has(s)) keys.current.set(s, crypto.randomUUID()); return keys.current.get(s); };
  const run = async fn => { setBusy(true); setError(''); try { await fn(); } catch (err) { setError(err.message); } finally { setBusy(false); } };
  const load = async after => { const result = await request(`/jobs/${jobId}/company-candidates?${filters()}${after ? `&after=${after}` : ''}`); setPage(result); setSelected([]); setPreview(null); setApproved(false); };
  const selectedRows = page?.rows.filter(row => selected.includes(row.application_id)) || [];
  const dirty = fn => value => { fn(value); setPage(null); setSelected([]); setPreview(null); setApproved(false); };
  const exportRows = async format => { const blob = await requestBlob(`/jobs/${jobId}/exports?${filters()}&format=${format}`); saveBlob(blob, `company_candidates.${format}`); };
  return <section className={panelStyles.panel} aria-label="Company hiring pipeline" aria-busy={busy}>
    <h3>Company rounds and shortlist</h3>
    <p>Compare objective scores and review status separately. Company interviews are arranged by your team. OA recommendations require a recruiter decision.</p>
    <div className={panelStyles.grid}><label>Current stage ID<input value={stage} onChange={e => dirty(setStage)(e.target.value)} placeholder="All stages" /></label>
    <label>Lifecycle<select value={lifecycle} onChange={e => dirty(setLifecycle)(e.target.value)}><option value="">All</option>{['active', 'hired', 'rejected', 'withdrawn', 'closed'].map(v => <option key={v}>{v}</option>)}</select></label>
    <label>Objective OA recommendation<select value={qualification} onChange={e => dirty(setQualification)(e.target.value)}><option value="">All</option>{['cleared', 'not_cleared', 'review_required'].map(v => <option key={v}>{v}</option>)}</select></label>
    </div><div className={panelStyles.actions}><button disabled={busy} onClick={() => run(() => load())}>Load / refresh company candidates</button>
    <button disabled={busy} onClick={() => run(() => exportRows('csv'))}>Export filtered CSV</button><button disabled={busy} onClick={() => run(() => exportRows('xlsx'))}>Export filtered XLSX</button></div>
    {error && <p role="alert">{error}</p>}
    {page && <>
      <ul aria-label="Canonical hiring funnel">{page.funnel.map(item => <li key={`${item._id.stage}:${item._id.lifecycle}`}>{item._id.stage} / {item._id.lifecycle}: {item.count}</li>)}</ul>
      <div className={panelStyles.tableScroll} role="region" aria-label="Candidate comparison" tabIndex={0}><table><caption>Current page comparison (up to 100 candidates)</caption><thead><tr><th>Select</th><th>Candidate</th><th>Stage / outcome</th><th>Screening</th><th>OA score</th><th>Recommendation</th><th>Integrity</th><th>Recruiter decision</th></tr></thead>
        <tbody>{page.rows.map(row => <tr key={row.application_id}><td><input type="checkbox" aria-label={`Select ${row.name || row.application_id}`} checked={selected.includes(row.application_id)} onChange={e => { setSelected(old => e.target.checked ? [...old, row.application_id] : old.filter(id => id !== row.application_id)); setPreview(null); setApproved(false); }} /></td>
          <td>{row.name}<br />{row.email}</td><td>{row.label}<br />{row.stage_id}</td><td>{row.interview_score ?? 'Unavailable'}</td><td>{row.oa_score === null ? 'Unavailable' : `${row.oa_score}%`}</td><td>{row.oa_recommendation}</td><td>{row.integrity_hold ? 'Review pending' : 'No unresolved hold'}</td><td>{row.recruiter_decision}</td></tr>)}</tbody></table></div>
      {page.has_more && <button disabled={busy} onClick={() => run(() => load(page.next_after))}>Next candidate page</button>}
      <p>{selected.length} selected on this page. Open the candidate card for detailed evaluation, evidence review and company round configuration.</p>
      <label>Bulk action<select value={action} onChange={e => setAction(e.target.value)}>{[['qualify', 'Approve OA qualification'], ['not_qualify', 'OA not qualified'], ['hold', 'Hold OA'], ['advance', 'Shortlist / advance to company round'], ['release', 'Release candidate summary'], ['reject', 'Final rejection'], ['hire', 'Record hired']].map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label>
      <label>Private decision reason<textarea value={reason} maxLength={1000} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={busy || !selected.length || reason.trim().length < 10} onClick={() => run(async () => {
        const payload = { items: selectedRows.map(row => ({ application_id: row.application_id, expected_revision: row.revision })), action, reason };
        const result = await post(`/jobs/${jobId}/bulk-stage-actions`, { ...payload, operation_key: keyFor(payload) }); setOutcomes(result.outcomes); await load(); window.dispatchEvent(new Event('hiring-workflow-updated'));
      })}>Apply selected decision</button>
      {outcomes && <ul aria-label="Bulk per-candidate outcomes">{outcomes.map(item => <li key={item.application_id}>{item.application_id}: {item.ok ? 'Saved' : item.error}</li>)}</ul>}
      <h4>Company email</h4><p>Compose only the information you want recipients to receive. Decisions and result release are separate actions. Each recipient receives an individual email.</p>
      <label>Email subject<input maxLength={160} value={subject} onChange={e => { setSubject(e.target.value); setPreview(null); setApproved(false); }} /></label>
      <label>Email message<textarea maxLength={10000} value={message} onChange={e => { setMessage(e.target.value); setPreview(null); setApproved(false); }} /></label>
      <button disabled={busy || !selected.length || !subject.trim() || message.trim().length < 10} onClick={() => run(async () => { setPreview(await post(`/jobs/${jobId}/communications/preview`, { application_ids: selected, subject, message })); setApproved(false); })}>Preview recipients and email</button>
      {preview && <div aria-label="Email recipient preview"><p>{preview.subject}</p><pre style={{ whiteSpace: 'pre-wrap' }}>{preview.message}</pre><ul>{preview.recipients.map(row => <li key={row.email}>{row.name}: {row.email}</li>)}</ul><p>{preview.skipped.length} skipped. Preview expires {new Date(preview.expires_at).toLocaleString()}.</p>
        <label><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />I approve these exact recipients and this message.</label>
        <button disabled={busy || !approved} onClick={() => run(async () => { const payload = { preview_id: preview.preview_id, accepted: true }; setBatch(await post(`/jobs/${jobId}/communications`, { ...payload, operation_key: keyFor(payload) })); setPreview(null); setApproved(false); })}>Queue approved email batch</button>
      </div>}
    </>}
    {batch && <div><p role="status">{batch.queued} emails queued. Queued does not mean delivered. Batch ID: {batch.batch_id}.</p><button disabled={busy} onClick={() => run(async () => setDelivery(await request(`/jobs/${jobId}/communications/${batch.batch_id}`)))}>Refresh delivery status</button>{delivery && <ul>{delivery.messages.map(row => <li key={row._id}>{row.email}: {row.state}</li>)}</ul>}</div>}
  </section>;
}

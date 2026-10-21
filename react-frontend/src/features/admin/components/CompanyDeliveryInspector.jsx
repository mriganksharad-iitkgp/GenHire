import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React, { useRef, useState } from 'react';
import { request, post } from 'shared/api/client';

export default function CompanyDeliveryInspector({ jobId }) {
  const [batchId, setBatchId] = useState(''), [messages, setMessages] = useState(null), [reason, setReason] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const keys = useRef(new Map());
  const load = async () => setMessages((await request(`/jobs/${jobId}/communications/${encodeURIComponent(batchId)}`)).messages);
  const run = async fn => { setBusy(true); setError(''); try { await fn(); } catch (err) { setError(err.message); } finally { setBusy(false); } };
  const reconcile = async (row, disposition) => {
    const payload = { disposition, reason }, signature = JSON.stringify([row._id, payload]);
    if (!keys.current.has(signature)) keys.current.set(signature, crypto.randomUUID());
    await post(`/company-communications/${row._id}/reconcile`, { ...payload, operation_key: keys.current.get(signature) }); await load();
  };
  return <section className={panelStyles.panel} aria-label="Company email delivery inspection"><h4>Company email delivery inspection</h4>
    <label>Batch ID<input value={batchId} onChange={e => { setBatchId(e.target.value); setMessages(null); }} /></label>
    <button disabled={busy || !batchId.trim()} onClick={() => run(load)}>Inspect delivery batch</button>
    <p>Unknown or stale dispatch requires provider-side confirmation. A confirmed non-send cancels the message; a fresh preview and approval are required before another send.</p>
    {error && <p role="alert">{error}</p>}
    <label>Provider evidence / reconciliation reason<textarea maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
    {messages && <ul>{messages.map(row => <li key={row._id}>{row.email}: {row.state}{['dispatching', 'delivery_unknown'].includes(row.state) && <>
      <button disabled={busy || reason.trim().length < 20} onClick={() => run(() => reconcile(row, 'confirmed_sent'))}>Confirm provider accepted send</button>
      <button disabled={busy || reason.trim().length < 20} onClick={() => run(() => reconcile(row, 'confirmed_not_sent'))}>Confirm provider did not send</button>
    </>}</li>)}</ul>}
  </section>;
}

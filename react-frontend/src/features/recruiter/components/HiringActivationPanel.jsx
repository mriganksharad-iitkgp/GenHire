import React, { useEffect, useRef, useState } from 'react';
import { getHiringOperations, quoteHiringActivation, activateHiring, changeOaWindow } from '../api/hiringProgressionApi';
import styles from './HiringSetupWizard.module.css';
import AssessmentVariantPool from './AssessmentVariantPool';

export default function HiringActivationPanel({ job, setup }) {
  const id = job._id || job.id;
  const [overview, setOverview] = useState(null);
  const [content, setContent] = useState('');
  const [quote, setQuote] = useState(null);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('');
  const [opening, setOpening] = useState('');
  const [closing, setClosing] = useState('');
  const keys = useRef(new Map());
  const key = value => {
    if (!keys.current.has(value)) keys.current.set(value, crypto.randomUUID());
    return keys.current.get(value);
  };
  useEffect(() => {
    let cancelled = false;
    setOverview(null); setQuote(null); setAccepted(false); setError(''); keys.current.clear();
    getHiringOperations(id).then(result => { if (!cancelled) { setOverview(result); setContent(result.published_content[0]?._id || ''); } })
      .catch(err => { if (!cancelled) setError(err.message || 'Hiring operations could not be loaded.'); });
    return () => { cancelled = true; };
  }, [id, setup._id]);
  const run = async fn => {
    setBusy(true); setError(''); setMessage('');
    try { await fn(); } catch (err) { setError(err.message || 'Hiring action failed.'); }
    finally { setBusy(false); }
  };
  const refresh = async () => {
    const result = await getHiringOperations(id); setOverview(result);
    if (!content && result.published_content[0]) setContent(result.published_content[0]._id);
  };
  const activate = () => run(async () => {
    const result = await activateHiring({ quote_id: quote._id, accepted, operation_key: key(`activate:${quote._id}`) });
    setQuote(null); setAccepted(false); await refresh();
    setMessage(`Hiring version activated. ${result.setup_credits_captured} setup credits captured. Existing candidates were not changed.`);
    window.dispatchEvent(new Event('hiring-workflow-updated'));
  });
  const windowAction = reschedule => run(async () => {
    const dates = reschedule ? { opens_at: new Date(opening).toISOString(), closes_at: new Date(closing).toISOString() } : {};
    const payload = { ...dates, reason, expected_revision: overview.window_revision };
    await changeOaWindow(overview.active_version_id, { ...payload, operation_key: key(JSON.stringify(['window', payload])) });
    await refresh(); setMessage(reschedule ? 'Unstarted OA invitations rescheduled. Accepted attempt deadlines were preserved.' : 'The configured OA window is authorized. Its scheduled dates still apply.');
    window.dispatchEvent(new Event('hiring-workflow-updated'));
  });
  return <section className={styles.sectionCard} aria-label="Hiring activation and scheduling">
    <h4>Activate hiring and manage entry windows</h4>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {message && <p role="status">{message}</p>}
    {!overview ? <button type="button" onClick={() => run(refresh)} disabled={busy}>Load hiring operations</button> : <>
      <p>{overview.impact}</p>
      <AssessmentVariantPool setup={setup} content={overview.published_content} />
      <p>{overview.active_version_id ? `Active setup: ${overview.active_setup_version_id === setup._id ? 'this configuration' : 'an earlier configuration'}.` : 'No hiring schedule is active.'} {overview.existing_application_count} existing applications.</p>
      {!overview.scheduling_enabled && <p className={styles.hint}>Hiring scheduling is currently disabled. Saved configuration and question content remain available.</p>}
      {setup.configuration.pipeline.oa_enabled && <label className={styles.field}>Published assessment content
        <select value={content} onChange={e => { setContent(e.target.value); setQuote(null); setAccepted(false); }}>
          <option value="">Choose reviewed content</option>{overview.published_content.map(v => <option key={v._id} value={v._id}>Content revision {v.workspace_revision} · {new Date(v.created_at).toLocaleString()}</option>)}
        </select>
      </label>}
      <div className={styles.draftActions}>
        <button type="button" disabled={busy} onClick={() => run(refresh)}>Refresh content and stage counts</button>
        <button type="button" disabled={busy || !overview.scheduling_enabled || (setup.configuration.pipeline.oa_enabled && !content)} onClick={() => run(async () => {
          const result = await quoteHiringActivation(id, content); setQuote(result.quote); setAccepted(false);
        })}>Preview activation credits</button>
      </div>
      {quote && <aside className={styles.notice}>
        <p>{quote.setup_credits===0?'No OA setup charge.':<>OA activation setup: <strong>{quote.setup_credits} credits</strong>.</>} Candidate OA attempt: {quote.attempt_credits ?? 'Not applicable'} credits per accepted start, reserved separately.</p>
        <p>Expires {new Date(quote.expires_at).toLocaleString()}. Any existing approved setup hold is reused. This activates the job and schedule for future applications.</p>
        <label className={styles.toggle}><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} disabled={busy} />I approve this activation, its credit cost and its candidate impact.</label>
        <button type="button" disabled={busy || !accepted || Date.parse(quote.expires_at) <= Date.now()} onClick={activate}>Activate approved hiring version</button>
      </aside>}
      {overview.active_schedule && <>
        <p>Screening: {new Date(overview.active_schedule.screening_opens_at).toLocaleString()} – {new Date(overview.active_schedule.screening_closes_at).toLocaleString()}. Candidates must finish screening by close.</p>
        {overview.active_oa_enabled && <>
          <p>OA entry: {new Date(overview.active_schedule.oa_opens_at).toLocaleString()} – {new Date(overview.active_schedule.oa_start_closes_at).toLocaleString()}. A timely start gets the full attempt duration.</p>
          <label className={styles.field}>Reason for OA window action<textarea value={reason} maxLength={1000} onChange={e => setReason(e.target.value)} /></label>
          {overview.active_schedule.oa_activation === 'manual' && !overview.manual_oa_authorized && <button type="button" disabled={busy || !overview.scheduling_enabled || reason.trim().length < 3} onClick={() => windowAction(false)}>Authorize configured OA window</button>}
          <div className={styles.grid}>
            <label className={styles.field}>New OA entry opening (your local time)<input type="datetime-local" value={opening} onChange={e => setOpening(e.target.value)} /></label>
            <label className={styles.field}>New OA entry cutoff (your local time)<input type="datetime-local" value={closing} onChange={e => setClosing(e.target.value)} /></label>
          </div>
          <button type="button" disabled={busy || !overview.scheduling_enabled || !opening || !closing || reason.trim().length < 3} onClick={() => windowAction(true)}>Reschedule unstarted OA entries</button>
        </>}
      </>}
      {overview.stage_counts.length > 0 && <ul>{overview.stage_counts.map(row => <li key={JSON.stringify(row._id)}>{row._id.type} · {row._id.state.replaceAll('_', ' ')} · {row._id.outcome.replaceAll('_', ' ')}: {row.count}</li>)}</ul>}
    </>}
  </section>;
}

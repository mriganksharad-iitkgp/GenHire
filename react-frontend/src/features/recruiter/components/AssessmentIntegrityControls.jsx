import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React, { useState } from 'react';
import { request } from 'shared/api/client';
const post = (path, value) => request(path, { method: 'POST', body: JSON.stringify(value) });

export default function AssessmentIntegrityControls({ invitation, attemptId, practice=false }) {
  const [reason, setReason] = useState(''), [browser, setBrowser] = useState(false), [waiver, setWaiver] = useState(false), [minutes, setMinutes] = useState(0);
  const [report, setReport] = useState(null), [error, setError] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false);
  const [quote, setQuote] = useState(null), [approved, setApproved] = useState(false), [similarity, setSimilarity] = useState(null);
  const [media, setMedia] = useState([]), [mediaUrl, setMediaUrl] = useState(''), [cursor, setCursor] = useState(null);
  if (!invitation) return null;
  const run = async fn => { setBusy(true); setError(''); try { await fn(); } catch (err) { setError(err.message); } finally { setBusy(false); } };
  const load = async () => setReport(await request(`/assessment-attempts/${attemptId}/integrity`));
  const accommodate = () => run(async () => {
    const fresh = await request(`/assessment-invitations/${invitation.invitation_id}`);
    await post(`/assessment-invitations/${invitation.invitation_id}/accommodation`, { operation_key: crypto.randomUUID(),
      expected_revision: fresh.integrity_policy?.accommodation_revision || 0, reason, browser_allowed: browser, camera_waived: waiver, extra_minutes: minutes });
    setMessage('Accommodation saved for this invitation. The candidate must reopen preflight.');
  });
  const review = decision => run(async () => {
    await post(`/assessment-attempts/${attemptId}/integrity-review`, { operation_key: crypto.randomUUID(), expected_revision: report.review_revision || 0, decision, reason });
    await load(); setMessage('Reasoned review recorded. Objective marks and company-round decisions were not changed.');
  });
  return <section className={panelStyles.panel} aria-label="OA integrity and accommodations" style={{ marginTop: 16 }}>
    <h4>OA integrity and accommodations</h4>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <label>Reason for integrity or accommodation action<textarea maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
    {invitation.state === 'invited' && <>
      <p>Use a functional accommodation reason; medical details are not required. Changes apply before start and do not alter the cohort.</p>
      <label><input type="checkbox" checked={browser} onChange={e => setBrowser(e.target.checked)} /> Approve accessible browser mode and assistive clipboard use</label>
      <label><input type="checkbox" checked={waiver} onChange={e => setWaiver(e.target.checked)} /> Approve camera waiver</label>
      <label>Extra minutes<input type="number" min="0" max="180" value={minutes} onChange={e => setMinutes(Number(e.target.value))} /></label>
      <button disabled={busy || reason.trim().length < 10} onClick={accommodate}>Approve invitation accommodation</button>
    </>}
    {attemptId && <>
      <button disabled={busy} onClick={() => run(load)}>View / refresh integrity summary</button>
      <button disabled={busy} onClick={() => run(async () => { const value = await request(`/assessment-attempts/${attemptId}/evidence`); setMedia(value.items); setCursor(value.next_cursor); })}>List retained camera evidence</button>
      {cursor && <button disabled={busy} onClick={() => run(async () => { const value = await request(`/assessment-attempts/${attemptId}/evidence?after=${encodeURIComponent(cursor)}`); setMedia(current => [...current, ...value.items]); setCursor(value.next_cursor); })}>Load more retained samples</button>}
      {media.length > 0 && <ul>{media.map(item => <li key={item.media_id}>{item.source}, {new Date(item.created_at).toLocaleString()} <button disabled={busy} onClick={() => run(async () => setMediaUrl((await request(`/assessment-attempts/${attemptId}/evidence/${item.media_id}`)).url))}>Prepare private sample link</button></li>)}</ul>}
      {mediaUrl && <p><a href={mediaUrl} target="_blank" rel="noreferrer">Open authorized camera sample (link expires in five minutes)</a></p>}
      {report && <>
        <p>Evidence status: {report.status.replaceAll('_', ' ')}. Observations and missing coverage require human judgment; they are not proof of misconduct.</p>
        <p>Camera samples: {report.camera_evidence?.stored_samples ?? 'unknown'}. Analyzed samples: {report.camera_evidence?.analyzed_samples ?? 'unknown'}.</p>
        {report.counts && <ul>{Object.entries(report.counts).map(([name, count]) => <li key={name}>{name.replaceAll('_', ' ')}: {count}</li>)}</ul>}
        {report.review && <p>Latest review: {report.review.decision.replaceAll('_', ' ')}.</p>}
        <button disabled={busy || reason.trim().length < 10} onClick={() => review('reviewed_clear')}>Record reviewed clear</button>
        <button disabled={busy || reason.trim().length < 10} onClick={() => review('needs_followup')}>Request integrity follow-up</button>
        <button disabled={busy || reason.trim().length < 10} onClick={() => review('insufficient_evidence')}>Record insufficient evidence</button>
        <label>Verified disruption extra minutes<input type="number" min="1" max="180" value={minutes} onChange={e => setMinutes(Number(e.target.value))} /></label>
        <button disabled={busy || minutes < 1 || reason.trim().length < 10} onClick={() => run(async () => {
          await post(`/assessment-attempts/${attemptId}/time-extension`, { operation_key: crypto.randomUUID(), expected_revision: report.attempt_revision, minutes, reason }); await load(); setMessage('Accepted deadline extended with an audit event. It was not restarted.');
        })}>Approve extra time for verified disruption</button>
        <button disabled={busy || reason.trim().length < 10} onClick={() => run(async () => {
          await post(`/assessment-attempts/${attemptId}/evidence-privacy`, { operation_key: crypto.randomUUID(), action: 'preserve', reason, hold_days: 30 }); setMessage('Evidence preservation scheduled for 30 days.');
        })}>Preserve evidence for 30 days</button>
        <button disabled={busy || reason.trim().length < 10} onClick={() => run(async () => {
          if (!window.confirm('Schedule retained OA evidence deletion? Scores and application history remain.')) return;
          await post(`/assessment-attempts/${attemptId}/evidence-privacy`, { operation_key: crypto.randomUUID(), action: 'purge', reason }); setMessage('Evidence deletion scheduled; active preservation holds are enforced.');
        })}>Schedule evidence deletion</button>
      </>}
      {!practice&&<><p>Optional similarity is a bounded token-overlap review aid. Common/trivial solutions can overlap; no objective score changes.</p>
      <button disabled={busy} onClick={() => run(async () => { setQuote(await post('/assessment-integrity-quotes', { kind: 'similarity', target_id: attemptId })); setApproved(false); })}>Preview similarity report credits</button>
      {quote && <><p>Similarity report: {quote.credits} credits.</p><label><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} /> I approve this optional report cost</label>
        <button disabled={busy || !approved} onClick={() => run(async () => { await post('/assessment-integrity-purchases', { quote_id: quote.quote_id, operation_key: crypto.randomUUID(), accepted: true }); setSimilarity(await request(`/assessment-attempts/${attemptId}/similarity`)); })}>Create approved similarity report</button></>}
      {similarity && <><p>{similarity.warning}</p><ul>{similarity.pairs.map((pair, index) => <li key={index}>{pair.overlap_percentage}% token overlap for question {pair.question_version_id}, peer attempt {pair.peer_attempt_id}. Review source and context through authorized tools.</li>)}</ul></>}
      </>}
    </>}
  </section>;
}

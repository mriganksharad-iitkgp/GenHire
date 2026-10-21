import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React, { useEffect, useRef, useState } from 'react';
import { getHiringProgress, enrollHiring, inviteToOa, hiringStageAction } from '../api/hiringProgressionApi';
import AssessmentEvaluationReport from './AssessmentEvaluationReport';
import AssessmentIntegrityControls from './AssessmentIntegrityControls';
import CompanyReviewPanel from './CompanyReviewPanel';

export default function HiringCandidateActions({ application }) {
  const [progress, setProgress] = useState(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const keys = useRef(new Map());
  const id = application._id;
  const available = !!(application.workflow_version_id || application.hiring_available);
  useEffect(() => {
    let cancelled = false;
    if (available) getHiringProgress(id).then(value => { if (!cancelled) setProgress(value); }).catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [id, available, application.workflow?.revision]);
  if (!available) return null;
  const workflow = progress?.workflow;
  const stage = workflow?.stages.find(s => s.stage_id === workflow.current_stage_id);
  const active = workflow?.lifecycle === 'active';
  const run = async action => {
    setBusy(true); setError(''); setNotice('');
    const payload = { expected_revision: workflow?.revision ?? null, reason };
    const signature = JSON.stringify([action, payload]);
    if (!keys.current.has(signature)) keys.current.set(signature, crypto.randomUUID());
    const operation_key = keys.current.get(signature);
    try {
      if (action === 'enroll') await enrollHiring(id, { expected_revision: payload.expected_revision, operation_key });
      else if (action === 'invite') await inviteToOa(id, { ...payload, operation_key });
      else await hiringStageAction(id, { ...payload, action, operation_key });
      setProgress(await getHiringProgress(id)); setNotice('Workflow action saved.');
      window.dispatchEvent(new Event('hiring-workflow-updated'));
    } catch (err) { setError(err.message || 'Hiring action failed. Refresh the application before retrying a conflict.'); }
    finally { setBusy(false); }
  };
  return <section className={panelStyles.panel} aria-label="Candidate hiring actions" style={{ marginTop: 16 }}>
    <h4>Hiring progression</h4>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {workflow && <p>{workflow.workflow_label}</p>}
    <AssessmentEvaluationReport attemptId={workflow?.stages.find(s => s.type === 'oa')?.attempt_id} />
    <AssessmentIntegrityControls invitation={progress?.invitation} attemptId={workflow?.stages.find(s => s.type === 'oa')?.attempt_id} />
    {workflow && <CompanyReviewPanel key={id} applicationId={id} />}
    {progress?.screening_result_reason && <p>Screening policy: {progress.screening_result_reason.replaceAll('_', ' ')}.</p>}
    {!progress ? <button type="button" disabled={busy} onClick={async () => { try { setProgress(await getHiringProgress(id)); setError(''); } catch (err) { setError(err.message); } }}>Refresh hiring progress</button> : <>
      <label>Decision or invitation reason<textarea value={reason} maxLength={1000} onChange={e => setReason(e.target.value)} style={{ display: 'block', width: '100%' }} /></label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
        {application.hiring_available && (!workflow || (active && !progress.invitation)) && <button type="button" disabled={busy || !progress.scheduling_enabled} onClick={() => run('enroll')}>{workflow ? 'Enroll in current hiring version' : 'Enroll in activated hiring pipeline'}</button>}
        {active && ((stage?.type === 'application_review' && ['eligible', 'completed'].includes(stage.state)) || (stage?.type === 'screening' && stage.state === 'completed')) && <>
          <button type="button" disabled={busy || reason.trim().length < 3} onClick={() => run('clear')}>Record cleared decision</button>
          <button type="button" disabled={busy || reason.trim().length < 3} onClick={() => run('not_clear')}>Record not cleared decision</button>
          <button type="button" disabled={busy || reason.trim().length < 3} onClick={() => run('review')}>Hold for review</button>
        </>}
        {active && stage?.state === 'completed' && stage.outcome === 'cleared' && stage.type === 'application_review' && <button type="button" disabled={busy || reason.trim().length < 3} onClick={() => run('advance')}>Advance to screening</button>}
        {active && !progress.invitation && workflow.stages.some(s => s.type === 'oa' && s.enabled) && workflow.stages.some(s => s.type === 'screening' && s.state === 'completed' && s.outcome === 'cleared') && <button type="button" disabled={busy || !progress.scheduling_enabled || reason.trim().length < 3} onClick={() => run('invite')}>Invite to online assessment</button>}
      </div>
      {progress.invitation && <p>OA invitation: {progress.invitation.state}. Entry closes {new Date(progress.invitation.start_closes_at).toLocaleString()}. {progress.invitation.attempt_deadline ? `Accepted attempt ends ${new Date(progress.invitation.attempt_deadline).toLocaleString()}.` : ''}</p>}
    </>}
  </section>;
}

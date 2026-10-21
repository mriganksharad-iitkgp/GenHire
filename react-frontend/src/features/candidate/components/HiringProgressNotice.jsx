import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React, { useEffect, useState } from 'react';
import { request } from 'shared/api/client';
import ReleasedAssessmentSummary from './ReleasedAssessmentSummary';

export default function HiringProgressNotice({ applicationId, enabled }) {
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let cancelled = false;
    if (enabled) request(`/applications/${applicationId}/hiring-progress`)
      .then(result => { if (!cancelled) setProgress(result); }).catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [applicationId, enabled]);
  if (!enabled) return null;
  const refresh = async () => {
    setBusy(true); setError('');
    try { setProgress(await request(`/applications/${applicationId}/hiring-progress`)); }
    catch (err) { setError(err.message || 'Hiring progress is unavailable.'); }
    finally { setBusy(false); }
  };
  const invitation = progress?.invitation;
  const stage = progress?.workflow?.stages.find(s => s.stage_id === progress.workflow.current_stage_id);
  return <section aria-label="Hiring timeline and assessment invitation" className={panelStyles.panel}>
    <strong>{progress?.workflow?.workflow_label || 'Hiring timeline'}</strong>
    {error && <p role="alert">{error}</p>}
    {stage?.type === 'screening' && stage.outcome === 'cleared' && !invitation && <p>Screening cleared. The recruiter will confirm the next hiring step.</p>}
    {progress?.schedule && <p>Screening opens {new Date(progress.schedule.screening_opens_at).toLocaleString()} and must finish by {new Date(progress.schedule.screening_closes_at).toLocaleString()}. Times use your device timezone.</p>}
    {invitation && <>
      <p>Online assessment: {invitation.state}. Entry opens {new Date(invitation.opens_at).toLocaleString()} and closes {new Date(invitation.start_closes_at).toLocaleString()}.</p>
      <p>A valid start receives the full {invitation.duration_minutes} minutes, including time after the entry window closes. Reconnecting does not restart the timer.</p>
      {invitation.attempt_deadline && <p>Your accepted attempt deadline: {new Date(invitation.attempt_deadline).toLocaleString()}.</p>}
      {invitation.state === 'expired' && <p>You did not start within the entry window. Contact the recruiter about the next step.</p>}
      {!invitation.runtime_ready && <p>The OA workspace is not enabled yet. Check here for availability.</p>}
      {(invitation.runtime_ready || invitation.state === 'accepted') && <p><a href={`/assessments/${invitation.invitation_id}`}>Open assessment workspace</a></p>}
    </>}
    <button type="button" onClick={refresh} disabled={busy}>{busy ? 'Refreshing hiring progress…' : 'Refresh hiring progress'}</button>
    <ReleasedAssessmentSummary key={applicationId} attemptId={progress?.workflow?.stages.find(s => s.type === 'oa')?.attempt_id} />
  </section>;
}

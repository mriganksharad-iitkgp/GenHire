import React, { useEffect, useMemo, useRef, useState } from 'react';
import ConfirmDialog from 'shared/components/ui/ConfirmDialog';
import styles from '../pages/Assessment.module.css';
import Assessment from '../pages/Assessment';
import { scopedAssessmentClient } from '../api/scopedAssessment';
import { returnFromKiosk } from '../../interview/utils/kioskReturn';
import QRCode from 'react-qr-code';

export default function ScopedAssessment({ launch }) {
  const [session, setSession] = useState(null), [ready, setReady] = useState(false), [error, setError] = useState('');
  const [confirmExit,setConfirmExit]=useState(false);
  const [pairing,setPairing]=useState(false);
  const [busy, setBusy] = useState(false), [consent, setConsent] = useState(false), [phone, setPhone] = useState('');
  const video = useRef(null), stream = useRef(null), activeAttempt = useRef(null);
  const nonce = useRef(crypto.randomUUID());
  const apiBase = `${launch.apiUrl.replace(/\/$/, '')}/api`;
  const sessionKey = `genhire:oa:${launch.invitationId}`;
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        window.electronAPI?.enableKiosk();
        const runtime = window.electronAPI ? await window.electronAPI.getAssessmentRuntime() : { release_id: '', kiosk_active: false };
        const response = await fetch(`${apiBase}/assessment-launches/redeem`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ invitation_id: launch.invitationId, launch_code: launch.launchCode, nonce: nonce.current, runtime_info: runtime }) });
        const value = await response.json(); if (!response.ok) throw new Error(value.error || 'Secure launch could not be redeemed.');
        if (mounted) { setSession(value); sessionStorage.setItem(sessionKey, JSON.stringify(value)); }
      } catch (failure) {
        // A renderer refresh may outlive the five-minute launch grant. Only a
        // still-valid scoped session can recover; the server rechecks every call.
        try { const cached = JSON.parse(sessionStorage.getItem(sessionKey) || 'null'); if (cached && mounted) { setSession(cached); return; } } catch { /* Reopen from dashboard. */ }
        if (mounted) setError(failure.message);
      }
    })();
    return () => { mounted = false; };
  }, [apiBase, launch.invitationId, launch.launchCode, sessionKey]);
  const client = useMemo(() => session ? scopedAssessmentClient(apiBase, session.access_token, token => {
    sessionStorage.setItem(sessionKey, JSON.stringify({ ...session, access_token: token }));
  }) : null, [apiBase, session, sessionKey]);
  const post = async (path, body) => client.request(path, { method: 'POST', body: JSON.stringify(body) });
  const takeFrame = async () => {
    if (!video.current || !stream.current) return;
    const canvas = document.createElement('canvas'); canvas.width = 480; canvas.height = 360;
    canvas.getContext('2d').drawImage(video.current, 0, 0, 480, 360);
    return post(`/assessment-invitations/${launch.invitationId}/camera-frame`, { operation_key: crypto.randomUUID(), image: canvas.toDataURL('image/jpeg', .65) });
  };
  useEffect(() => {
    if (!ready || !client) return undefined;
    let sending = false;
    const timer = setInterval(async () => {
      if (sending) return; sending = true;
      try {
        if (activeAttempt.current && activeAttempt.current.state !== 'in_progress') return;
        const refresh = await client.request(`/assessment-invitations/${launch.invitationId}/session-refresh`, { method: 'POST', body: '{}' });
        client.replaceToken(refresh.access_token);
        if (stream.current) await takeFrame();
      } catch (failure) { if (failure.code !== 'attempt_locked') setError('Monitoring coverage is interrupted. Your timer continues; reconnect or contact the recruiter.'); }
      finally { sending = false; }
    }, 15000);
    return () => clearInterval(timer);
    // Camera is a stable ref; no frame/credential is included in dependency keys.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, client, launch.invitationId]);
  useEffect(() => () => { stream.current?.getTracks().forEach(track => track.stop()); }, []);
  const prepare = async () => {
    setBusy(true); setError('');
    try {
      const needsCamera = session.policy.tier !== 'basic' && !session.policy.camera_waived;
      if (needsCamera && !stream.current) {
        stream.current = await navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360 }, audio: false });
        video.current.srcObject = stream.current; await video.current.play();
      }
      const runtime = window.electronAPI ? await window.electronAPI.getAssessmentRuntime() : { kiosk_active: false };
      await post(`/assessment-invitations/${launch.invitationId}/preflight`, { consent_version: 'oa-integrity-v1',
        readiness: { camera_ready: !!stream.current, visible: !document.hidden, kiosk_active: runtime.kiosk_active } });
      if (needsCamera) await takeFrame();
      setReady(true);
    } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  const pair = async () => {
    if(pairing)return;setPairing(true);setError('');
    try {
      const value = await post(`/assessment-invitations/${launch.invitationId}/mobile-pair`, {});
      setPhone(`${launch.webOrigin}/oa-companion/${launch.invitationId}#${encodeURIComponent(value.pairing_token)}`);
    } catch (failure) { setError(failure.message); } finally {setPairing(false);}
  };
  const exit = () => {
    stream.current?.getTracks().forEach(track => track.stop());
      const path=launch.practice?'/practice?mode=oa':'/applications';
      if (window.electronAPI) returnFromKiosk(window.electronAPI, launch, path);
      else window.location.assign(path);
  };
  return <>
    <section aria-label="Secure OA monitoring" className={styles.monitor}>
      {!session&&!error&&<p role="status">Opening your secure assessment...</p>}
      {error && <p role="alert">{error}</p>}
      {session && <>
        {!ready && <>
          <h1>Prepare your assessment</h1>
          <p>Mode: {session.policy.mode}. Monitoring: {session.policy.camera_waived ? 'camera waived by accommodation' : session.policy.tier}.</p>
          <details><summary>Monitoring, privacy and permitted resources</summary><p>Visibility/focus and monitoring gaps are recorded for human review. Camera tiers collect sampled camera images, not continuous audio or screen recordings. Unknown coverage is not proof of misconduct. Your timer continues through disconnection.</p>
          <p>Raw camera images expire {session.policy.raw_retention_days} days after completion; integrity summaries expire after {session.policy.summary_retention_days} days, unless a reasoned preservation hold applies. Scores/history follow a separate policy.</p>
          <p>{session.policy.clipboard === 'internal_editor' ? 'Editor copy/paste within this assessment is permitted. External paste is blocked by the supplied client.' : 'External clipboard and assistive tools are allowed by your approved browser accommodation.'} Secure browser restrictions cannot prevent every external device or OS escape.</p></details>
          <p>Approved extra time: {session.policy.extra_minutes} minutes. Preflight does not start your assessment timer.</p>
          <label><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /> I consent to the disclosed monitoring and retention policy.</label>
          <p><button disabled={!consent || busy} onClick={prepare}>{busy ? 'Checking devices…' : 'Confirm devices and continue'}</button></p>
        </>}
        {session.policy.tier === 'dual' && !session.policy.camera_waived && <><button disabled={!consent||pairing} onClick={pair}>{pairing?'Creating companion link...':phone?'Replace companion camera link':'Create companion camera link'}</button>{phone && <div><p>Scan this code on your phone, consent there, and keep its camera page visible before starting the OA.</p><QRCode value={phone} size={200} /><p><a href={phone} target="_blank" rel="noreferrer">Open companion link on your phone</a></p></div>}</>}
        <video ref={video} muted playsInline aria-label="Camera preview" style={{ width: 160, display: session.policy.tier === 'basic' || session.policy.camera_waived ? 'none' : 'block' }} />
      </>}
      <button onClick={()=>activeAttempt.current?.state==='in_progress'?setConfirmExit(true):exit()}>{launch.practice?'Return to practice':'Return to applications'}</button>
    </section>
    <ConfirmDialog isOpen={confirmExit} title="Leave this assessment?" message="The assessment timer keeps running. Only answers acknowledged by the server are guaranteed saved. Return through the same invitation to continue before the deadline." confirmText="Leave assessment" cancelText="Keep working" onConfirm={exit} onClose={()=>setConfirmExit(false)}/>
    {ready && client && <Assessment invitationId={launch.invitationId} oaRequest={client.request} secureContext={session.policy}
      onAccessToken={client.replaceToken} onAttempt={value => { activeAttempt.current = value; if (value.state !== 'in_progress') { stream.current?.getTracks().forEach(track => track.stop()); stream.current = null; window.electronAPI?.disableKiosk(); } }} />}
  </>;
}

import React, { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { request, API_BASE } from 'shared/api/client';
import { setToken } from 'shared/utils/session';
import useAssessmentIntegrity from '../hooks/useAssessmentIntegrity';
import ConfirmDialog from 'shared/components/ui/ConfirmDialog';
import AssessmentExperience from '../components/AssessmentExperience';
import KioskLaunchGuide, { openKiosk } from '../../interview/components/KioskLaunchGuide';
const ScopedAssessment = lazy(() => import('../components/ScopedAssessment'));

const key = () => `oa-${crypto.randomUUID()}`;

export default function Assessment({ invitationId: providedId, oaRequest, secureContext, onAccessToken, onAttempt, developerPreview = false } = {}) {
  const params = useParams();
  const invitationId = providedId || params.invitationId;
  const call = oaRequest || request;
  const post = useCallback((path, data) => call(path, { method: 'POST', body: JSON.stringify(data) }), [call]);
  const [launchGuide, setLaunchGuide] = useState(false), [browserLaunch, setBrowserLaunch] = useState(null);
  const clipboard = useRef(''), callback = useRef(onAttempt); callback.current = onAttempt;
  const [invitation, setInvitation] = useState(null);
  const [attempt, setAttempt] = useState(null);
  const [confirmSubmit,setConfirmSubmit]=useState(false),[languageChange,setLanguageChange]=useState(null),[confirmReload,setConfirmReload]=useState(false);
  const submissionPending=useRef(false);
  const [consent, setConsent] = useState(false);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const [sectionRemaining, setSectionRemaining] = useState(null);
  const [custom, setCustom] = useState({});
  const [run, setRun] = useState(null);
  const [privacyNotice, setPrivacyNotice] = useState('');
  const attemptRef = useRef(null), draft = useRef({}), pending = useRef(null), lock = useRef(false);
  const boundaryRefresh = useRef(false);
  const dirtyRef = useRef(false), clock = useRef(null), startKey = useRef(key());
  const storageKey = useCallback(id => `oa-draft:${id}`, []);

  const apply = useCallback(snapshot => {
    attemptRef.current = snapshot; setAttempt(snapshot);
    callback.current?.(snapshot);
    if (snapshot.latest_run) setRun(snapshot.latest_run);
    clock.current = { server: Date.parse(snapshot.server_now), local: performance.now() };
    setRemaining(Math.max(0, Math.ceil((Date.parse(snapshot.deadline) - clock.current.server) / 1000)));
    if (!dirtyRef.current) { draft.current = snapshot.answers; setAnswers(snapshot.answers); }
    if (snapshot.state !== 'in_progress') {
      sessionStorage.removeItem(storageKey(snapshot.attempt_id));
      dirtyRef.current = false; setDirty(false); pending.current = null;
    }
  }, [storageKey]);

  const load = useCallback(async id => {
    const snapshot = await call(`/assessment-attempts/${id}`);
    if (attemptRef.current && snapshot.revision < attemptRef.current.revision) return;
    if (!attemptRef.current) {
      try {
        const recovered = JSON.parse(sessionStorage.getItem(storageKey(id)) || 'null');
        if (recovered && snapshot.state === 'in_progress') {
          draft.current = recovered.answers; pending.current = recovered.pending;
          dirtyRef.current = true; setDirty(true); setAnswers(recovered.answers);
        }
      } catch { /* Storage recovery is best effort; server saves remain authoritative. */ }
    }
    apply(snapshot);
  }, [apply, storageKey, call]);

  useEffect(() => {
    let active = true;
    call(`/assessment-invitations/${invitationId}`).then(async result => {
      if (!active) return;
      setInvitation(result);
      if (result.state === 'accepted' && (!result.security_required || secureContext)) await load(result.attempt_id);
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [invitationId, load, call, secureContext]);

  const persist = () => {
    try { sessionStorage.setItem(storageKey(attemptRef.current.attempt_id), JSON.stringify({ answers: draft.current, pending: pending.current })); }
    catch { setError('Local recovery storage is unavailable. Keep this page open and save to the server.'); }
  };

  const save = useCallback(async () => {
    if (!dirtyRef.current || !attemptRef.current || lock.current) return !dirtyRef.current;
    lock.current = true; setSaving(true);
    const current = attemptRef.current;
    if (!pending.current) {
      const visible = new Set(current.questions.map(q => q.id));
      pending.current = { operation_key: key(), expected_revision: current.revision,
        answers: Object.fromEntries(Object.entries(draft.current).filter(([id]) => visible.has(id))) };
    }
    const payload = pending.current;
    try {
      try { sessionStorage.setItem(storageKey(current.attempt_id), JSON.stringify({ answers: draft.current, pending: payload })); }
      catch { /* A full local cache must not prevent the authoritative server save. */ }
      const result = await post(`/assessment-attempts/${current.attempt_id}/answers`, payload);
      attemptRef.current = { ...attemptRef.current, revision: result.revision };
      pending.current = null;
      const visible = new Set(current.questions.map(q => q.id));
      const unchanged = Object.keys(draft.current).filter(id => visible.has(id)).length === Object.keys(payload.answers).length &&
        Object.entries(payload.answers).every(([id, value]) => JSON.stringify(value) === JSON.stringify(draft.current[id]));
      if (unchanged) { dirtyRef.current = false; setDirty(false); sessionStorage.removeItem(storageKey(current.attempt_id)); }
      setError(''); return unchanged;
    } catch (err) { setError(`${err.message} Your local draft is retained. Retry saving or reload server answers to reconcile.`); return false; }
    finally { lock.current = false; setSaving(false); }
  }, [storageKey, post]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (dirtyRef.current) save();
    }, 1500);
    const online = () => save();
    const beforeUnload = event => { if (dirtyRef.current) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('online', online); window.addEventListener('beforeunload', beforeUnload);
    return () => { clearInterval(timer); window.removeEventListener('online', online); window.removeEventListener('beforeunload', beforeUnload); };
  }, [save]);

  useEffect(() => {
    if (!attempt?.attempt_id) return undefined;
    const timer = setInterval(() => {
      if (clock.current) {
        const now = clock.current.server + performance.now() - clock.current.local;
        setRemaining(Math.max(0, Math.ceil((Date.parse(attempt.deadline) - now) / 1000)));
        const section = attemptRef.current.sections.find(s => Date.parse(s.opens_at) <= now && now < Date.parse(s.closes_at));
        setSectionRemaining(section ? Math.max(0, Math.ceil((Date.parse(section.closes_at) - now) / 1000)) : 0);
        const boundary = now >= Date.parse(attempt.deadline) || (attemptRef.current.timer_mode === 'section' && section &&
          attemptRef.current.questions.some(q => !section.question_ids.includes(q.id)));
        if (boundary && !lock.current && !boundaryRefresh.current && attemptRef.current.state === 'in_progress') {
          boundaryRefresh.current = true;
          load(attempt.attempt_id).catch(err => setError(err.message)).finally(() => { boundaryRefresh.current = false; });
        }
      }
    }, 1000);
    const poll = setInterval(() => { if (!lock.current) load(attempt.attempt_id).catch(err => setError(err.message)); }, 10000);
    return () => { clearInterval(timer); clearInterval(poll); };
  }, [attempt?.attempt_id, attempt?.deadline, load]);

  useEffect(() => {
    if (!run || !['queued', 'running', 'dispatching'].includes(run.state)) return undefined;
    const timer = setInterval(() => call(`/assessment-attempts/${attemptRef.current.attempt_id}/runs/${run.run_id}`)
      .then(result => setRun(current => ({ ...result, question_id: result.question_id || current?.question_id }))).catch(err => setError(err.message)), 2500);
    return () => clearInterval(timer);
  }, [run, call]);
  useAssessmentIntegrity(call, attempt, secureContext);

  const change = (id, value) => {
    draft.current = { ...draft.current, [id]: value }; setAnswers(draft.current);
    dirtyRef.current = true; setDirty(true); persist();
  };
  const start = async () => {
    setBusy(true); setError('');
    try {
      const result = await post(`/assessment-invitations/${invitationId}/start`, { operation_key: startKey.current, consent_version: 'oa-v1' });
      if (onAccessToken) onAccessToken(result.access_token); else setToken(result.access_token);
      await load(result.attempt_id);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const submit = async () => {
    if(submissionPending.current)return;
    submissionPending.current=true;setConfirmSubmit(false);setBusy(true);
    try {
      if (dirtyRef.current && !await save()) return;
      await post(`/assessment-attempts/${attemptRef.current.attempt_id}/submit`, { expected_revision: attemptRef.current.revision });
      await load(attemptRef.current.attempt_id);
    } catch (err) { setError(err.message); } finally { submissionPending.current=false;setBusy(false); }
  };
  const reloadAnswers=async()=>{
    setConfirmReload(false);setBusy(true);setError('');
    try{
      const snapshot=await call(`/assessment-attempts/${attemptRef.current.attempt_id}`);
      if(snapshot.revision<attemptRef.current.revision)throw new Error('The saved answers are stale. Your local work is retained.');
      dirtyRef.current=false;pending.current=null;setDirty(false);
      sessionStorage.removeItem(storageKey(snapshot.attempt_id));apply(snapshot);
    }catch(failure){setError(`${failure.message} Your local answers are retained.`);}
    finally{setBusy(false);}
  };
  const runCode = async (q, useCustom = false) => {
    setBusy(true); setError('');
    try {
      const answer = answers[q.id] || { language: q.type === 'sql' ? 'sql' : q.coding.languages[0], source: q.type === 'coding' ? q.coding.starter_code[q.coding.languages[0]] : '' };
      let input = custom[q.id] ?? '';
      if (useCustom && q.type === 'coding' && q.coding.contract === 'function') input = JSON.parse(input);
      const result = await post(`/assessment-attempts/${attempt.attempt_id}/runs`, { operation_key: key(), question_id: q.id, answer, ...(useCustom ? { custom_input: input } : {}) });
      setRun({ ...result, question_id: q.id, state: 'queued' });
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const launch = async () => {
    setBusy(true); setError('');
    try {
      const mode = invitation.integrity_policy.mode;
      const grant = await post(`/assessment-invitations/${invitationId}/secure-launch`, { operation_key: key(), mode });
      const payload = { mode: 'oa', practice: invitation.pool === 'practice', launchCode: grant.launch_code, invitationId, apiUrl: new URL(API_BASE, window.location.origin).href.replace(/\/api\/?$/, ''), webOrigin: window.location.origin, returnToExistingTab: true };
      if (mode === 'browser') setBrowserLaunch(payload); else openKiosk(payload);
    } catch (failure) { setError(failure.message); } finally { setBusy(false); }
  };
  if (browserLaunch) return <Suspense fallback={<p>Opening accommodated assessment…</p>}><ScopedAssessment launch={browserLaunch} /></Suspense>;
  return <>
    <AssessmentExperience invitation={invitation} attempt={attempt} answers={answers} error={error} busy={busy} saving={saving} dirty={dirty}
      remaining={remaining} sectionRemaining={sectionRemaining} consent={consent} setConsent={setConsent} start={start} launch={launch} openGuide={() => setLaunchGuide(true)}
      save={save} reload={() => dirty ? setConfirmReload(true) : reloadAnswers()} submit={() => setConfirmSubmit(true)} change={change}
      languageChange={(question, language) => { const next = { language, source: question.coding.starter_code[language] }; const current = answers[question.id];
        if (current?.source?.trim() && current.source !== question.coding.starter_code[current.language]) setLanguageChange({ questionId: question.id, answer: next }); else change(question.id, next); }}
      runCode={runCode} run={run} custom={custom} setCustom={setCustom} secureContext={secureContext} clipboard={clipboard} developerPreview={developerPreview}
      call={call} privacyNotice={privacyNotice} requestPrivacy={async () => { try { await post(`/assessment-attempts/${attempt.attempt_id}/evidence-privacy`, { operation_key: key(), action: 'request_deletion', reason: 'Please review deletion of my retained OA evidence.' }); setPrivacyNotice('Evidence deletion review requested. Scores/history and any reasoned preservation hold follow their separate policies.'); } catch (failure) { setError(failure.message); } }} />
    <KioskLaunchGuide assessment practice={invitation?.pool === 'practice'} isOpen={launchGuide} onClose={() => setLaunchGuide(false)} onOpen={launch} busy={busy} />
    <ConfirmDialog isOpen={confirmReload} title="Reload saved answers?" message="This replaces your unsaved edits with the server's saved answers. Your local work is retained if the reload fails." confirmText="Reload saved answers" cancelText="Keep local answers" onConfirm={reloadAnswers} onClose={()=>setConfirmReload(false)} isLoading={busy}/>
    <ConfirmDialog isOpen={!!languageChange} title="Change coding language?" message="This replaces the current editor content with the selected language's starter code. Keep your current language to retain your work." confirmText="Change language" cancelText="Keep current code" onConfirm={()=>{if(languageChange)change(languageChange.questionId,languageChange.answer);setLanguageChange(null);}} onClose={()=>setLanguageChange(null)}/>
    <ConfirmDialog isOpen={confirmSubmit} title="Submit your assessment?" message="Your latest answers will be saved first. Submission locks all answers; you cannot edit them afterwards. Unanswered questions receive no marks." confirmText="Save and submit" cancelText="Keep working" onConfirm={submit} onClose={()=>setConfirmSubmit(false)} isLoading={busy||saving}/>
  </>;
}

import React, { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { request, API_BASE } from 'shared/api/client';
import { setToken } from 'shared/utils/session';
import CodeEditor from 'shared/components/ui/CodeEditor';
import useAssessmentIntegrity from '../hooks/useAssessmentIntegrity';
import styles from './Assessment.module.css';
import ConfirmDialog from 'shared/components/ui/ConfirmDialog';
import PracticeAssessmentReport from '../components/PracticeAssessmentReport';
import KioskLaunchGuide, { openKiosk } from '../../interview/components/KioskLaunchGuide';
const ScopedAssessment = lazy(() => import('../components/ScopedAssessment'));

const key = () => `oa-${crypto.randomUUID()}`;

export default function Assessment({ invitationId: providedId, oaRequest, secureContext, onAccessToken, onAttempt } = {}) {
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
      .then(setRun).catch(err => setError(err.message)), 2500);
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
      setRun({ ...result, state: 'queued' });
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
  return <main className={styles.page}>
    <h1>Online assessment</h1>
    {error && <p role="alert">{error}</p>}
    {!invitation&&!attempt&&!error&&<p role="status">Loading assessment details...</p>}
    {!attempt ? <section aria-label="Assessment preflight">
      {invitation?.security_required && !secureContext && <>
        <p>This OA requires {invitation.integrity_policy.mode === 'browser' ? 'the approved browser accommodation' : 'GenHire Secure Browser'}. Device preflight does not start your timer. Contact {invitation.pool === 'practice' ? 'support' : 'the recruiter'} to request extra time or an accessible browser/camera accommodation.</p>
        <button disabled={busy} onClick={() => invitation.integrity_policy.mode === 'browser' ? launch() : setLaunchGuide(true)}>Open secure assessment</button>
        <KioskLaunchGuide assessment practice={invitation.pool==='practice'} isOpen={launchGuide} onClose={() => setLaunchGuide(false)} onOpen={launch} busy={busy} />
      </>}
      <p>Save your work regularly. The server timer continues during disconnection. Only acknowledged saves are guaranteed; unsent drafts can be recovered in this browser tab.</p>
      <p>Use only permitted resources. Your answers are stored for assessment evaluation. Submission locks the attempt; Run uses public examples or your custom input and does not determine your final score.</p>
      {invitation && <p>Duration: {invitation.duration_minutes} minutes. Start between {new Date(invitation.opens_at).toLocaleString()} and {new Date(invitation.start_closes_at).toLocaleString()}. A timely start receives the full duration even after the entry window closes.</p>}
      <label><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /> I accept these assessment rules and am ready to start the timer.</label>
      <p><button disabled={!consent || !invitation?.runtime_ready || busy || (invitation?.security_required && !secureContext)} onClick={start}>Start assessment</button></p>
      {invitation && !invitation.runtime_ready && <p>The assessment is awaiting launch readiness. Contact {invitation.pool === 'practice' ? 'support' : 'the recruiter'} for availability.</p>}
    </section> : attempt.state !== 'in_progress' ? <section role="status"><h2>Assessment submitted</h2>
      {invitation?.pool === 'practice' && <><PracticeAssessmentReport attemptId={attempt.attempt_id} oaRequest={call}/><p><a href="/practice?mode=oa">Return to mock OA history</a></p></>}
      <p>{invitation?.pool === 'practice' ? 'Your practice answers are locked. Objective results and educational feedback appear after evaluation; unavailable execution never becomes a guessed score.' : attempt.state === 'completed' ? 'Evaluation is complete. Check your application for any recruiter-released result and next steps.' : attempt.state === 'unavailable' ? 'Evaluation needs technical review. No final score has been assigned; the recruiter will confirm the next step.' : 'Your saved answers are locked and awaiting evaluation. The recruiter will confirm the next step.'}</p>
      {secureContext && <><button onClick={async () => { try { await post(`/assessment-attempts/${attempt.attempt_id}/evidence-privacy`, { operation_key: key(), action: 'request_deletion', reason: 'Please review deletion of my retained OA evidence.' }); setPrivacyNotice('Evidence deletion review requested. Scores/history and any reasoned preservation hold follow their separate policies.'); } catch (failure) { setError(failure.message); } }}>Request evidence deletion review</button>{privacyNotice && <p>{privacyNotice}</p>}</>}
    </section> : <>
      <div className={styles.toolbar}><p role="timer" aria-label="Total time remaining">Time remaining: {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, '0')}</p>
      {attempt.timer_mode === 'section' && sectionRemaining !== null && <p role="timer" aria-label="Section time remaining">Section remaining: {Math.floor(sectionRemaining / 60)}:{String(sectionRemaining % 60).padStart(2, '0')}</p>}
      <p role="status">{saving ? 'Saving…' : dirty ? 'Unsaved local changes' : 'All changes acknowledged by server'}</p>
        <details className={styles.questionNavigation}><summary>Jump to question ({attempt.questions.filter(q=>answers[q.id]?.option_ids?.length||answers[q.id]?.source?.trim()).length}/{attempt.questions.length} answered)</summary>
          <nav aria-label="Assessment question navigation">{attempt.questions.map((q,index)=><button key={q.id} type="button" aria-label={`Go to question ${index+1}: ${q.title}`} onClick={()=>{const target=document.getElementById(`oa-question-${q.id}`);target?.scrollIntoView?.({block:'start',behavior:'auto'});target?.focus({preventScroll:true});}}>{index+1}{answers[q.id]?.option_ids?.length||answers[q.id]?.source?.trim()?' *':''}</button>)}</nav>
        </details>
      </div>
      {attempt.timer_mode === 'section' && <p>Sections have fixed server windows. Closed sections cannot be revisited. {attempt.sections.map(s => `${s.type}: ${new Date(s.opens_at).toLocaleTimeString()}–${new Date(s.closes_at).toLocaleTimeString()}`).join('; ')}</p>}
      <button onClick={save} disabled={saving || !dirty}>Retry / save answers</button>{' '}
      <button disabled={busy || saving} onClick={()=>dirty?setConfirmReload(true):reloadAnswers()}>Reload server answers</button>
      <fieldset className={styles.questions} disabled={busy} style={{ border: 0, padding: 0 }}><legend>Assessment questions</legend>
      {attempt.questions.map((q, index) => <section id={`oa-question-${q.id}`} tabIndex={-1} key={q.id} aria-label={`Question ${index + 1}`} style={{ borderTop: '1px solid #ccd2dd', marginTop: 24, paddingTop: 16 }}>
        <h2>{index + 1}. {q.title} ({q.marks} marks)</h2><p style={{ whiteSpace: 'pre-wrap' }}>{q.statement}</p>
        {q.type === 'mcq' ? <fieldset><legend>{q.mcq.selection === 'single' ? 'Select one answer' : 'Select all correct answers'}</legend>
          {q.mcq.options.map(option => <label key={option.id} style={{ display: 'block', padding: 8 }}><input type={q.mcq.selection === 'single' ? 'radio' : 'checkbox'} name={q.id}
            checked={(answers[q.id]?.option_ids || []).includes(option.id)} onChange={e => change(q.id, { option_ids: q.mcq.selection === 'single' ? [option.id] : e.target.checked ? [...(answers[q.id]?.option_ids || []), option.id] : (answers[q.id]?.option_ids || []).filter(id => id !== option.id) })} /> {option.text}</label>)}
          <button onClick={() => change(q.id, { option_ids: [] })}>Clear selection</button>
        </fieldset> : <>
          {q.type === 'coding' ? <>
            {q.coding.signature && <pre aria-label="Function signature">{JSON.stringify(q.coding.signature, null, 2)}</pre>}
            <h3>Input format</h3><p>{q.coding.input_format}</p><h3>Output format</h3><p>{q.coding.output_format}</p><h3>Constraints</h3><p>{q.coding.constraints}</p>
            <label>Language <select value={answers[q.id]?.language || q.coding.languages[0]} onChange={e => {const next={language:e.target.value,source:q.coding.starter_code[e.target.value]};const current=answers[q.id];if(current?.source?.trim()&&current.source!==q.coding.starter_code[current.language])setLanguageChange({questionId:q.id,answer:next});else change(q.id,next);}}>
              {q.coding.languages.map(language => <option key={language} value={language}>{language} — {q.coding.runtime_versions[language]}</option>)}
            </select></label>
          </> : <><p>Dialect: {q.sql.engine} {q.sql.engine_version}</p><pre aria-label="Database schema">{q.sql.schema_sql}</pre></>}
          <h3>Public examples</h3><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(q.type === 'coding' ? q.coding.examples : q.sql.examples, null, 2)}</pre>
          <CodeEditor label={`Answer for ${q.title}`} readOnly={busy} language={answers[q.id]?.language || (q.type === 'sql' ? 'sql' : q.coding.languages[0])}
            clipboardRef={secureContext?.clipboard === 'internal_editor' ? clipboard : undefined}
            value={answers[q.id]?.source ?? (q.type === 'coding' ? q.coding.starter_code[q.coding.languages[0]] : '')}
            onChange={source => change(q.id, { language: answers[q.id]?.language || (q.type === 'sql' ? 'sql' : q.coding.languages[0]), source })} />
          {q.type === 'coding' && <label>{q.coding.contract === 'function' ? 'Custom input (JSON object keyed by parameter names)' : 'Custom standard input'}<textarea style={{ display: 'block', width: '100%' }} value={custom[q.id] || ''} onChange={e => setCustom({ ...custom, [q.id]: e.target.value })} /></label>}
          <button onClick={() => runCode(q)} disabled={busy || ['queued', 'running', 'dispatching'].includes(run?.state)}>Run public example</button>
          {q.type === 'coding' && <button onClick={() => runCode(q, true)} disabled={busy || ['queued', 'running', 'dispatching'].includes(run?.state)}>Run custom input</button>}
        </>}
      </section>)}
      </fieldset>
      {run && <section aria-label="Run output"><h2>Run output</h2>
        <p role="status">{(run.result?.status || run.state).replaceAll('_', ' ')}</p>
        {run.result?.stdout !== undefined && <pre style={{ whiteSpace: 'pre-wrap' }}>{run.result.stdout}</pre>}
        {run.result?.diagnostics && <pre aria-label="Compiler or runtime diagnostics" style={{ whiteSpace: 'pre-wrap' }}>{run.result.diagnostics}</pre>}
        {run.result?.columns && <div style={{ overflowX: 'auto' }}><table><caption>Query result</caption>
          <thead><tr>{run.result.columns.map((column, index) => <th key={index} scope="col">{column}</th>)}</tr></thead>
          <tbody>{run.result.rows?.map((row, index) => <tr key={index}>{row.map((cell, column) => <td key={column}>{cell === null ? 'NULL' : String(cell)}</td>)}</tr>)}</tbody>
        </table></div>}
      </section>}
      {['dispatch_unknown', 'blocked'].includes(run?.state) && <p role="status">This run needs operator reconciliation. Your timer continues; you can still save answers and submit your assessment.</p>}
      <p><button onClick={()=>setConfirmSubmit(true)} disabled={busy || saving}>Submit and lock assessment</button></p>
    </>}
    <ConfirmDialog isOpen={confirmReload} title="Reload saved answers?" message="This replaces your unsaved edits with the server's saved answers. Your local work is retained if the reload fails." confirmText="Reload saved answers" cancelText="Keep local answers" onConfirm={reloadAnswers} onClose={()=>setConfirmReload(false)} isLoading={busy}/>
    <ConfirmDialog isOpen={!!languageChange} title="Change coding language?" message="This replaces the current editor content with the selected language's starter code. Keep your current language to retain your work." confirmText="Change language" cancelText="Keep current code" onConfirm={()=>{if(languageChange)change(languageChange.questionId,languageChange.answer);setLanguageChange(null);}} onClose={()=>setLanguageChange(null)}/>
    <ConfirmDialog isOpen={confirmSubmit} title="Submit your assessment?" message="Your latest answers will be saved first. Submission locks all answers; you cannot edit them afterwards. Unanswered questions receive no marks." confirmText="Save and submit" cancelText="Keep working" onConfirm={submit} onClose={()=>setConfirmSubmit(false)} isLoading={busy||saving}/>
  </main>;
}

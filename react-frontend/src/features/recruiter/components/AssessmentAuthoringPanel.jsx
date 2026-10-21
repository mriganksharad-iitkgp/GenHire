import React, { useEffect, useRef, useState } from 'react';
import { getAssessmentWorkspace, saveAssessmentWorkspace, publishAssessmentContent, listQuestionBank,
  getQuestionVersion, saveQuestionVersion, validateQuestionVersion, reviewQuestionVersion, getQuestionValidationJob } from '../api/assessmentAuthoringApi';
import { newQuestion, editQuestion, prepareQuestion } from '../utils/questionEditor';
import AssessmentQuestionEditor from './AssessmentQuestionEditor';
import AssessmentGenerationPanel from './AssessmentGenerationPanel';
import styles from './HiringSetupWizard.module.css';

export default function AssessmentAuthoringPanel({ blueprintId }) {
  const [workspace, setWorkspace] = useState(null);
  const [selected, setSelected] = useState([]);
  const [bank, setBank] = useState({ items: [], next_cursor: null });
  const [active, setActive] = useState(null);
  const [editor, setEditor] = useState(null);
  const [reason, setReason] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const keys = useRef(new Map());
  const key = (action, body) => {
    const signature = JSON.stringify([action, body]);
    if (!keys.current.has(signature)) keys.current.set(signature, crypto.randomUUID());
    return keys.current.get(signature);
  };
  useEffect(() => {
    let cancelled = false;
    setWorkspace(null); setError(''); setEditor(null); setActive(null); setSelected([]); keys.current.clear();
    Promise.all([getAssessmentWorkspace(blueprintId), listQuestionBank()]).then(([ws, questions]) => {
      if (!cancelled) { setWorkspace(ws); setSelected(ws.questions); setBank(questions); }
    }).catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [blueprintId]);
  useEffect(() => {
    const validationJob = active?.validation_job;
    if (!validationJob?.id || !['queued', 'running'].includes(validationJob.state)) return;
    let cancelled = false;
    let inFlight = false;
    const versionId = active._id;
    const timer = setInterval(async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const result = await getQuestionValidationJob(validationJob.id);
        if (!cancelled && ['completed', 'failed'].includes(result.job.state)) {
          const { question } = await getQuestionVersion(versionId);
          if (!cancelled) {
            setActive(current => current?._id === versionId ? question : current);
            setSelected(current => current.map(q => q._id === versionId ? question : q));
            setReviewed(false); setApproved(false);
            if (result.job.error_code) setError(`Execution validation is unavailable: ${result.job.error_code.replaceAll('_', ' ')}.`);
          }
        }
      } catch (err) { if (!cancelled) setError(err.message || 'Validation status could not be refreshed.'); }
      finally { inFlight = false; }
    }, 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [active?._id, active?.validation_job]);
  const run = async callback => {
    setBusy(true); setError(''); setMessage('');
    try { await callback(); } catch (err) { setError(err.message || 'Assessment action failed. Your editor is retained.'); }
    finally { setBusy(false); }
  };
  const updateQuestion = value => {
    setActive(value); setReason(''); setReviewed(false); setApproved(false);
    setSelected(current => current.map(q => q._id === value._id ? value : q));
  };
  const loadQuestion = id => run(async () => {
    const { question } = await getQuestionVersion(id);
    updateQuestion(question); setEditor(editQuestion(question.content));
  });
  const addToSelection = question => {
    setSelected(current => current.some(q => q.question_id === question.question_id) ?
      current.map(q => q.question_id === question.question_id ? question : q) : [...current, question]);
    setApproved(false);
  };
  const saveQuestion = () => run(async () => {
    const content = prepareQuestion(editor);
    const body = { content, suite_policy:'oa_test_suite_v2', blueprint_id: blueprintId, previous_version_id: active?._id || null };
    const { question } = await saveQuestionVersion({ ...body, operation_key: key('question', body) });
    updateQuestion(question); setEditor(editQuestion(question.content)); addToSelection(question);
    const questions = await listQuestionBank(); setBank(questions);
    setMessage('Private question version saved and added to the working selection. Save the selection to keep its order.');
  });
  const validate = () => run(async () => {
    const outcome = await validateQuestionVersion(active._id, { operation_key: key('validate', [active._id, active.validation?._id,
      active.validation_job?.state === 'failed' ? active.validation_job.id : null, workspace.validator.profile_hash]) });
    const result = await getQuestionVersion(active._id); updateQuestion(result.question);
    if (outcome.job) {
      setActive(current => ({ ...current, validation_job: outcome.job }));
      setMessage('Execution validation queued. You can leave and reopen this question while the worker checks it.');
      return;
    }
    setMessage(active.content.type === 'mcq' ? 'MCQ structure checked. Independently review the correct answer and ambiguity before approval.' : 'Execution validation finished. Review its evidence before approval.');
  });
  const review = decision => run(async () => {
    const body = { validation_id: active.validation?._id || null, decision, reason };
    await reviewQuestionVersion(active._id, { ...body, operation_key: key('review', [active._id, active.review?._id, body]) });
    const result = await getQuestionVersion(active._id); updateQuestion(result.question);
    setMessage(decision === 'approve' ? 'This exact question version is approved.' : 'Question rejected for content publication.');
  });
  const ids = selected.map(q => q._id);
  const dirty = JSON.stringify(ids) !== JSON.stringify(workspace?.question_version_ids);
  const saveSelection = () => run(async () => {
    const body = { question_version_ids: ids, expected_revision: workspace.revision };
    const result = await saveAssessmentWorkspace(blueprintId, { ...body, operation_key: key('workspace', body) });
    setWorkspace(current => ({ ...current, ...result.workspace })); setApproved(false);
    setMessage('Assessment working selection saved. Existing published versions stay unchanged.');
  });
  const publish = () => run(async () => {
    const body = { expected_revision: workspace.revision, approved };
    const result = await publishAssessmentContent(blueprintId, { ...body, operation_key: key('publish', body) });
    setMessage(`Content published as version ${result.version._id}. This does not activate the OA, charge credits or invite candidates.`);
  });
  return <section className={styles.panel} aria-label="Assessment question authoring">
    <h3>Assessment questions and review</h3>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {message && <p role="status" className={styles.notice}>{message}</p>}
    {!workspace ? <p>Loading private assessment content…</p> : <fieldset disabled={busy} style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
      <p>Working revision {workspace.revision}. Question versions are immutable; editing creates a new version.</p>
      <p>{workspace.blueprint.configuration.sections.map(s => `${s.count} ${s.type.toUpperCase()} (${s.weight}% section weight)`).join(' · ')}</p>
      {!workspace.validator.available && <p className={styles.notice}>{workspace.validator.reason} Private drafts and MCQ structure review are available. Coding/SQL drafts can be prepared through Edit job, but execution validation and approval still need configured execution services.</p>}
      <p className={styles.hint}>Generation instructions: {workspace.blueprint.configuration.instructions || 'No additional instructions.'}</p>
      <p className={styles.notice}>For a complete AI JD and OA, use Edit job / Create with AI. Review attached questions here and open a saved version to edit it. Manual forms follow the saved authoring method; advanced single-question AI tools are optional and separately priced.</p>
      {workspace.blueprint.configuration.source!=='manual'&&<details className={styles.compactHelp}><summary>Advanced single-question AI tools (separate generation)</summary>
      <AssessmentGenerationPanel blueprintId={blueprintId} workspace={workspace} activeQuestion={active} onDraft={(kind,statement)=>{setActive(null);const draft=newQuestion(kind,workspace.blueprint.configuration);draft.statement=statement;draft.title=statement.split('\n')[0].slice(0,160);setEditor(draft);setReason('');setReviewed(false);setMessage('Statement copied to the manual form. Complete answers, reference solutions and testcases before saving.');}} onReady={versionIds => run(async () => {
        const questions = await Promise.all(versionIds.map(id => getQuestionVersion(id)));
        questions.forEach(result => addToSelection(result.question));
        setBank(await listQuestionBank());
        setMessage('Generated private versions are in the working selection. Open each, review its answer and save the selection before publication.');
      })} />
      </details>}
      {workspace.blueprint.configuration.source!=='ai'&&<div className={styles.draftActions}>{['mcq', 'coding', 'sql'].map(kind => <button key={kind} type="button" onClick={() => {
        setActive(null); setEditor(newQuestion(kind, workspace.blueprint.configuration)); setReason(''); setReviewed(false);
      }}>Add {kind.toUpperCase()} question</button>)}</div>}
      <AssessmentQuestionEditor value={editor} onChange={setEditor} onSave={saveQuestion} busy={busy} />
      {active && <section className={styles.review} aria-label="Question validation and review">
        <h4>Saved version {active.revision}: {active.content.title}</h4>
        <p>Validation: {active.validation ? active.validation.passed ? 'Passed' : 'Failed' : 'Not validated'} · Human review: {active.review?.decision || 'Pending'}</p>
        {active.validation_job && <p role="status">Execution job: {active.validation_job.state}</p>}
        <p className={styles.hint}>Actions below refer to the saved version above. Save editor changes as a new version before validating them.</p>
        {active.validation?.evidence?.note && <p>{active.validation.evidence.note}</p>}
        <button type="button" disabled={(active.content.type !== 'mcq' && !workspace.validator.available) || ['queued', 'running'].includes(active.validation_job?.state)} onClick={validate}>Validate saved question</button>
        <label className={styles.field}>Review rationale<textarea rows={3} minLength={10} maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <label className={styles.toggle}><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I checked the statement, correct answers, examples, hidden tests and ambiguity for this saved version.</label>
        <div className={styles.draftActions}>
          <button type="button" disabled={!active.validation?.passed || !reviewed || reason.trim().length < 10} onClick={() => review('approve')}>Approve saved question</button>
          <button type="button" disabled={reason.trim().length < 10} onClick={() => review('reject')}>Reject saved question</button>
        </div>
      </section>}
      <section className={styles.sectionCard} aria-label="Assessment working selection">
        <h4>Questions selected for this assessment ({selected.length})</h4>
        {selected.map((q, i) => <div className={styles.round} key={q._id}>
          <span>{i + 1}. {q.content.title} · {q.content.type} · {q.content.difficulty} · {q.content.marks} marks · v{q.revision} · {q.review?.decision || 'Needs review'}</span>
          <button type="button" onClick={() => loadQuestion(q._id)}>Open {i + 1}</button>
          <button type="button" disabled={i === 0} onClick={() => { const next = [...selected]; [next[i - 1], next[i]] = [next[i], next[i - 1]]; setSelected(next); setApproved(false); }}>Move {i + 1} earlier</button>
          <button type="button" onClick={() => { setSelected(current => current.filter(v => v._id !== q._id)); setApproved(false); }}>Remove {i + 1}</button>
        </div>)}
        <button type="button" disabled={!dirty} onClick={saveSelection}>Save assessment selection</button>
        {dirty && <p className={styles.hint}>Selection has unsaved changes.</p>}
        <label className={styles.toggle}><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />I approve this saved assessment content and its selected question versions.</label>
        <button type="button" disabled={dirty || !approved || !selected.length || selected.some(q => q.review?.decision !== 'approve')} onClick={publish}>Publish reviewed content</button>
        <p className={styles.hint}>The server checks every configured count, difficulty, mark, language, dialect and current validation/review. Content publication is separate from job/OA activation.</p>
      </section>
      <section className={styles.sectionCard} aria-label="Private question bank">
        <h4>Your private question bank</h4>
        {bank.items.length === 0 && <p>No saved question versions yet.</p>}
        {bank.items.map(q => <div className={styles.round} key={q._id}><span>{q.content.title} · {q.content.type} · v{q.revision}</span>
          <button type="button" onClick={() => loadQuestion(q._id)}>Edit {q.content.title}</button>
          <button type="button" onClick={() => run(async () => { const result = await getQuestionVersion(q._id); addToSelection(result.question); })}>Use {q.content.title}</button>
        </div>)}
        {bank.next_cursor && <button type="button" onClick={() => run(async () => { const page = await listQuestionBank(bank.next_cursor); setBank(current => ({ items: [...current.items, ...page.items], next_cursor: page.next_cursor })); })}>Load more question versions</button>}
      </section>
    </fieldset>}
  </section>;
}

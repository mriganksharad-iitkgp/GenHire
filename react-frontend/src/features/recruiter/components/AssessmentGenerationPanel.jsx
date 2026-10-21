import React, { useEffect, useRef, useState } from 'react';
import { quoteQuestionGeneration, enqueueQuestionGeneration, getQuestionGeneration, releaseAssessmentSetupHold } from '../api/assessmentAuthoringApi';
import styles from './HiringSetupWizard.module.css';

const terminal = new Set(['completed', 'failed']);
export default function AssessmentGenerationPanel({ blueprintId, workspace, activeQuestion, onReady, onDraft }) {
  const oa = workspace.blueprint.configuration;
  const sections = oa.sections.filter(s => s.count > 0);
  const [kind, setKind] = useState(sections[0]?.type || 'mcq');
  const [difficulty, setDifficulty] = useState('medium');
  const [marks, setMarks] = useState(sections[0]?.marks[0] || 1);
  const [count, setCount] = useState(1);
  const [instructions, setInstructions] = useState('');
  const [importMode,setImportMode]=useState(false),[statement,setStatement]=useState(''),[referenceUrl,setReferenceUrl]=useState('');
  const [providedTests,setProvidedTests]=useState(''),[referenceSolution,setReferenceSolution]=useState(''),[strategy,setStrategy]=useState('generate_and_review');
  const [quote, setQuote] = useState(null);
  const [accepted, setAccepted] = useState(false);
  const [job, setJob] = useState(workspace.generation?.latest_job || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pollFailed, setPollFailed] = useState(false);
  const keys = useRef(new Map());
  const onReadyRef = useRef(onReady);
  const notified = useRef(new Set(workspace.generation?.latest_job?.state === 'completed' ? [workspace.generation.latest_job.id] : []));
  onReadyRef.current = onReady;
  const operation = value => {
    if (!keys.current.has(value)) keys.current.set(value, crypto.randomUUID());
    return keys.current.get(value);
  };
  const change = setter => value => { setter(value); setQuote(null); setAccepted(false); };
  const run = async callback => {
    setBusy(true); setError('');
    try { await callback(); } catch (err) { setError(err.message || 'Generation action failed.'); }
    finally { setBusy(false); }
  };
  useEffect(() => {
    if (!job?.id || terminal.has(job.state) || pollFailed) return;
    let cancelled = false;
    let inFlight = false;
    const timer = setInterval(async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const result = await getQuestionGeneration(job.id);
        if (!cancelled) { setJob(result.job); setError(''); }
      } catch (err) { if (!cancelled) { setPollFailed(true); setError(err.message || 'Could not refresh generation progress.'); } }
      finally { inFlight = false; }
    }, 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [job?.id, job?.state, pollFailed]);
  useEffect(() => {
    if (job?.state === 'completed' && job.question_version_ids?.length && !notified.current.has(job.id)) {
      notified.current.add(job.id);
      onReadyRef.current(job.question_version_ids);
    }
  }, [job]);
  const requestQuote = previous => run(async () => {
    const specs = previous ? [{ type: previous.content.type, difficulty: previous.content.difficulty, marks: previous.content.marks,
      previous_version_id: previous._id }] : Array.from({ length: count }, () => ({ type: kind, difficulty, marks }));
    const result = await quoteQuestionGeneration(blueprintId, { requests: specs, instructions,
      ...(importMode?{problem_source:{statement,reference_url:referenceUrl,provided_tests:providedTests,reference_solution:referenceSolution,test_strategy:strategy}}:{}) });
    setQuote(result.quote); setAccepted(false);
  });
  const enqueue = () => run(async () => {
    const result = await enqueueQuestionGeneration({ quote_id: quote._id, accepted, operation_key: operation(`generation:${quote._id}`) });
    setJob(result.job); setQuote(null); setAccepted(false); setPollFailed(false);
  });
  const release = () => run(async () => {
    const result = await releaseAssessmentSetupHold(blueprintId, { operation_key: operation(`release:${job?.id || 'current'}`) });
    setJob(result.job); setQuote(null); setPollFailed(false);
  });
  const pending = !!job?.id && !terminal.has(job.state);
  const enabled = workspace.generation?.enabled && oa.source !== 'manual';
  const canGenerate = enabled && (kind === 'mcq' || workspace.validator.available);
  return <section className={styles.sectionCard} aria-label="AI question generation">
    <h4>Create with AI or convert a pasted problem</h4>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {!enabled && <p className={styles.hint}>AI generation is currently unavailable. Manual question authoring remains available. The saved blueprint must use AI or hybrid authoring, and a generation worker must be enabled.</p>}
    <fieldset disabled={busy || pending} style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
      <div className={styles.grid}>
        <label className={styles.field}>Generate question type<select value={kind} onChange={e => change(setKind)(e.target.value)}>{sections.map(s => <option key={s.type} value={s.type}>{s.type.toUpperCase()}</option>)}</select></label>
        <label className={styles.field}>Generate difficulty<select value={difficulty} onChange={e => change(setDifficulty)(e.target.value)}>{['easy', 'medium', 'hard'].map(d => <option key={d} value={d}>{d}</option>)}</select></label>
        <label className={styles.field}>Questions in batch<input type="number" min={1} max={5} disabled={importMode} value={count} onChange={e => change(setCount)(Number(e.target.value))} /></label>
        <label className={styles.field}>Marks per generated question<input type="number" min={0.01} max={1000} step={0.01} value={marks} onChange={e => change(setMarks)(Number(e.target.value))} /></label>
      </div>
      <label className={styles.field}>Additional generation instructions<textarea rows={3} maxLength={1000} value={instructions} onChange={e => change(setInstructions)(e.target.value)} /></label>
      <label className={styles.toggle}><input type="checkbox" checked={importMode} onChange={e=>{change(setImportMode)(e.target.checked);if(e.target.checked)setCount(1);}}/>Use a pasted problem or a reference link</label>
      {importMode&&<section className={styles.notice} aria-label="Problem import">
        <p>Paste content you own or are allowed to reuse. A link is attribution only; paste the statement too. External sites' hidden tests are not available from a public problem link.</p>
        <label className={styles.field}>Problem link (optional, HTTPS)<input type="url" maxLength={500} value={referenceUrl} onChange={e=>change(setReferenceUrl)(e.target.value)}/></label>
        <label className={styles.field}>Paste problem statement<textarea rows={7} maxLength={8000} value={statement} onChange={e=>change(setStatement)(e.target.value)} placeholder="Include the task, constraints, input/output format and examples."/></label>
        <label className={styles.field}>How should testcases be prepared?<select value={strategy} onChange={e=>change(setStrategy)(e.target.value)}>
          <option value="generate_and_review">AI proposes sample + hidden edge cases; I review them</option>
          <option value="use_provided_cases">Use my testcase guidance and add edge cases</option>
          <option value="reference_solution">Use my trusted reference solution as guidance</option>
        </select></label>
        <label className={styles.field}>Your sample/testcase guidance<textarea rows={4} maxLength={4000} value={providedTests} onChange={e=>change(setProvidedTests)(e.target.value)} placeholder="Input, expected output and cases to cover. Review generated cases against these requirements."/></label>
        <label className={styles.field}>Trusted reference solution (optional; include its language)<textarea rows={5} maxLength={8000} value={referenceSolution} onChange={e=>change(setReferenceSolution)(e.target.value)}/></label>
        <p>AI can fill an editable draft, not prove that every case is correct. Review the answers, constraints, examples and private tests, then run validation before approval. AI-generated reference code agreeing with AI-generated outputs is not independent proof.</p>
        {onDraft&&<button type="button" disabled={statement.trim().length<20} onClick={()=>onDraft(kind,statement)}>Copy statement to manual question form</button>}
      </section>}
      <div className={styles.draftActions}>
        <button type="button" disabled={!canGenerate || count < 1 || count > 5 || !Number.isInteger(count) || (importMode&&(statement.trim().length<20||(strategy==='use_provided_cases'&&!providedTests.trim())||(strategy==='reference_solution'&&!referenceSolution.trim())))} onClick={() => requestQuote(null)}>{importMode?'Preview conversion credits':'Preview generation credits'}</button>
        {activeQuestion && <button type="button" disabled={importMode || !enabled || (activeQuestion.content.type !== 'mcq' && !workspace.validator.available)} onClick={() => requestQuote(activeQuestion)}>Quote regeneration of saved question</button>}
      </div>
      {kind !== 'mcq' && !workspace.validator.available && <p className={styles.hint}>Code and SQL generation require a validated execution provider. You can save manual drafts now.</p>}
      {quote && <aside className={styles.notice}>
        <p>Reserve now: <strong>{quote.total_to_reserve} credits</strong> · legacy setup hold: {quote.setup_hold_credits} · AI generation: {quote.regeneration_credits}.</p>
        <p>Any pre-existing setup hold stays reserved until activation or explicit release. AI generation is charged once usable validated content is produced. Failed generation releases its applicable reservation. Expires: {new Date(quote.expires_at).toLocaleString()}.</p>
        <label className={styles.toggle}><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} />I approve this credit reservation and generation request.</label>
        <button type="button" disabled={!accepted || Date.parse(quote.expires_at) <= Date.now()} onClick={enqueue}>Start quoted generation</button>
      </aside>}
    </fieldset>
    {job && <p role="status">Generation job: {job.state.replaceAll('_', ' ')}{job.error_code ? ` (${job.error_code.replaceAll('_', ' ')})` : ''}. Generated questions require human review and a saved assessment selection.</p>}
    {job?.state === 'completed' && job.question_version_ids?.length > 0 && <button type="button" onClick={() => onReadyRef.current(job.question_version_ids)}>Add generated versions to selection</button>}
    {pollFailed && <button type="button" onClick={() => setPollFailed(false)}>Retry generation status</button>}
    <button type="button" disabled={busy || pending} onClick={release}>Release unactivated setup hold</button>
    <p className={styles.hint}>Releasing a hold preserves private content and does not activate an assessment. A fresh setup reservation is required before later activation. A queued release is processed durably by the worker.</p>
  </section>;
}

import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, Bookmark, Check, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, Clock3, Code2, Database, FileText, Flag, ListChecks, Loader2, Maximize2, Minimize2, Moon, Play, RotateCcw, Save, ShieldCheck, Sun, Terminal, Undo2, Redo2, Search } from 'lucide-react';
import CodeEditor from 'shared/components/ui/CodeEditor';
import ConfirmDialog from 'shared/components/ui/ConfirmDialog';
import GenHireBrand from 'shared/components/ui/GenHireBrand';
import PracticeAssessmentReport from './PracticeAssessmentReport';
import styles from '../pages/Assessment.module.css';

const kinds = { coding: 'Coding', sql: 'SQL', mcq: 'Multiple choice' };
const names = { python: 'Python', cpp: 'C++', c: 'C', java: 'Java', javascript: 'JavaScript', nodejs: 'Node.js' };
const extensions = { python: 'py', cpp: 'cpp', c: 'c', java: 'java', javascript: 'js', nodejs: 'js', sql: 'sql' };
const format = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
const answered = value => Boolean(value?.option_ids?.length || value?.source?.trim());
const duration = seconds => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;

function SqlCode({ source, engine, label }) {
  const [rendered, setRendered] = useState(null);
  useEffect(() => {
    let active = true;
    (async () => { try { const modules = import.meta.glob('../../../shared/components/ui/codeFormatting.js'); const { formatCode } = await modules['../../../shared/components/ui/codeFormatting.js'](); const value = await formatCode(source, 'sql', { dialect: engine }); if (active) setRendered({ source, value }); } catch { /* Retain the original readable source if formatting is unavailable. */ } })();
    return () => { active = false; };
  }, [source, engine]);
  return <pre aria-label={label}>{rendered?.source === source ? rendered.value : source}</pre>;
}

function ResultTable({ columns, rows }) {
  return <div className={styles.tableScroll}><table><thead><tr>{columns.map((column, index) => <th key={index} scope="col">{column}</th>)}</tr></thead>
    <tbody>{rows.length ? rows.map((row, index) => <tr key={index}>{row.map((value, cell) => <td key={cell}>{value === null ? <em>NULL</em> : String(value)}</td>)}</tr>) : <tr><td colSpan={columns.length}>No rows</td></tr>}</tbody></table></div>;
}

function Examples({ question }) {
  const examples = question.type === 'coding' ? question.coding.examples : question.sql.examples;
  return <div className={styles.examples}>{examples.map((example, index) => <section className={styles.example} key={index}>
    <h3>Sample {index + 1}</h3>
    {question.type === 'coding' ? <><h4>Input</h4><pre>{format(example.input)}</pre><h4>Expected output</h4><pre>{format(example.expected)}</pre></>
      : <><h4>Expected result</h4><ResultTable columns={example.columns} rows={example.expected_rows} /><details><summary>Sample data</summary><SqlCode source={example.seed_sql} engine={question.sql.engine} /></details></>}
    {example.explanation && <p className={styles.subtle}>{example.explanation}</p>}
  </section>)}</div>;
}

export default function AssessmentExperience({ invitation, attempt, answers, error, busy, saving, dirty, remaining, sectionRemaining,
  consent, setConsent, start, launch, openGuide, save, reload, submit, change, languageChange, runCode, run, custom, setCustom,
  secureContext, clipboard, developerPreview, call, privacyNotice, requestPrivacy }) {
  const [activeId, setActiveId] = useState(null), [tab, setTab] = useState('problem');
  const [resultTab, setResultTab] = useState('results'), [resultsOpen, setResultsOpen] = useState(true);
  const [entered, setEntered] = useState(false), [flagged, setFlagged] = useState(new Set());
  const [dark, setDark] = useState(() => { try { return localStorage.getItem('genhire-oa-theme') === 'dark'; } catch { return false; } });
  const [focusEditor, setFocusEditor] = useState(false), [fontSize, setFontSize] = useState(14), [split, setSplit] = useState(43);
  const [resetPrompt, setResetPrompt] = useState(false);
  const body = useRef(null), heading = useRef(null), editorCommands = useRef(null);
  const [formatNotice, setFormatNotice] = useState(''), [formatting, setFormatting] = useState(false);
  const questions = attempt?.questions || [], question = questions.find(q => q.id === activeId) || questions[0];
  const index = questions.findIndex(q => q.id === question?.id), count = questions.filter(q => answered(answers[q.id])).length;
  const coding = question?.type === 'coding', sql = question?.type === 'sql';
  const language = question ? answers[question.id]?.language || (coding ? question.coding.languages[0] : 'sql') : 'python';
  const source = question ? answers[question.id]?.source ?? (coding ? question.coding.starter_code[language] : '') : '';
  const currentRun = run?.question_id === question?.id ? run : null;
  const pendingRun = ['queued', 'running', 'dispatching'].includes(run?.state);
  const summary = invitation?.assessment_summary;
  const sections = summary?.sections || ['coding', 'sql', 'mcq'].map(type => ({ type, count: questions.filter(q => q.type === type).length })).filter(s => s.count);
  const total = summary?.question_count || questions.length;
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, [question?.id]);
  useEffect(() => { try { localStorage.setItem('genhire-oa-theme', dark ? 'dark' : 'light'); } catch { /* Preference is optional. */ } }, [dark]);
  const navigate = id => { setActiveId(id); setTab('problem'); setFocusEditor(false); setFormatNotice(''); };
  const next = async () => { if (!dirty || await save()) navigate(questions[(index + 1) % questions.length].id); };
  const toggleFlag = () => setFlagged(previous => { const value = new Set(previous); if (value.has(question.id)) value.delete(question.id); else value.add(question.id); return value; });
  const resize = event => {
    if (event.button !== 0) return;
    event.preventDefault(); const bounds = body.current.getBoundingClientRect();
    const move = pointer => setSplit(Math.max(30, Math.min(65, (pointer.clientX - bounds.left - 88) / (bounds.width - 88) * 100)));
    const end = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', end); };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', end, { once: true });
  };
  const brand = <GenHireBrand label="Assessments" />;
  const themeButton = <button className={styles.iconButton} aria-label={dark ? 'Use light theme' : 'Use dark theme'} onClick={() => setDark(value => !value)}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button>;
  const rootClass = `${styles.experience} ${dark ? styles.night : ''}`;
  const terminal = attempt && attempt.state !== 'in_progress';
  const landing = !attempt || (developerPreview && !entered && !terminal);

  if (landing) return <main className={`${rootClass} ${styles.landing}`}>
    <header className={styles.landingHeader}>{brand}<div className={styles.headerRight}><span className={styles.secureLabel}><ShieldCheck size={15} /> Assessment workspace</span>{themeButton}</div></header>
    <div className={styles.welcomeGrid}>
      <section className={styles.welcomeIntro}>
        <span className={styles.eyebrow}>{developerPreview ? 'DEVELOPER PREVIEW' : invitation?.pool === 'practice' ? 'YOUR PRACTICE SESSION' : 'YOUR NEXT OPPORTUNITY'}</span>
        <h1>{summary?.title || 'A space to show\nwhat you can do.'}</h1>
        <p>Welcome to your GenHire assessment. Take a moment to get comfortable with the format, then put your skills into practice.</p>
        <div className={styles.welcomeFacts}><div><Clock3 size={20} /><span><strong>{developerPreview ? 'Untimed preview' : invitation?.duration_minutes ? `${invitation.duration_minutes} minutes` : 'Loading duration'}</strong><small>{developerPreview ? 'Explore at your own pace' : 'Full duration from your accepted start'}</small></span></div>
          {!!total && <div><ListChecks size={20} /><span><strong>{total} questions</strong><small>{sections.map(section => kinds[section.type]).join(' · ')}</small></span></div>}
          <div><Save size={20} /><span><strong>Your work stays with you</strong><small>Automatic saving with server acknowledgment</small></span></div></div>
        <div className={styles.welcomeFoot}><span className={styles.brandDot} /> Built for your next chapter.<p>Powered by GenHire</p></div>
      </section>
      <section className={styles.instructions} aria-label="Assessment preflight">
        <div className={styles.stepTrail}><span className={styles.currentStep}>01 Instructions</span><span>02 Workspace</span><span>03 Submission</span></div>
        <h2>Before you begin</h2><p className={styles.subtle}>A few things to help you feel prepared.</p>
        <ol className={styles.instructionList}>
          <li><strong>Read the question carefully</strong><p>Review the problem, constraints and sample cases before writing your answer.</p></li>
          <li><strong>Make the workspace yours</strong><p>Choose a supported language, adjust the editor and switch between questions using the sidebar.</p></li>
          <li><strong>Run, review, improve</strong><p>Run public examples or your own input. Hidden tests are evaluated only after final submission.</p></li>
          <li><strong>Keep an eye on your progress</strong><p>{developerPreview ? 'This developer session lets you explore without taking a timed exam.' : 'The server timer continues during disconnection. Section windows, when configured, limit revisiting.'} Only acknowledged saves are guaranteed.</p></li>
          <li><strong>Submit when you are ready</strong><p>Your latest answers are saved before submission locks the assessment. Unanswered questions receive no marks.</p></li>
        </ol>
        {!!sections.length && <div className={styles.formatCard}><h3>Test format</h3><table><thead><tr><th>Section</th><th>Questions</th></tr></thead><tbody>{sections.map(section => <tr key={section.type}><td>{kinds[section.type] || section.type}</td><td>{section.count}</td></tr>)}</tbody></table></div>}
        {error && <p role="alert" className={styles.alert}>{error}</p>}
        {!invitation && !error && <p role="status">Loading assessment details...</p>}
        {invitation?.security_required && !secureContext && <p className={styles.securityNote}><ShieldCheck size={18} /> Use {invitation.integrity_policy.mode === 'browser' ? 'your approved browser accommodation' : 'GenHire Secure Browser'} for this assessment. Device preflight does not start your timer. Contact {invitation.pool === 'practice' ? 'support' : 'the recruiter'} for an accommodation.</p>}
        {!developerPreview && <label className={styles.consent}><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /><span>I accept these assessment rules and am ready to start the timer.</span></label>}
        <div className={styles.landingActions}><span>{developerPreview ? 'Prefilled answers · disposable local session' : invitation ? `Entry closes ${new Date(invitation.start_closes_at).toLocaleString()}` : 'Your timer has not started'}</span>
          {developerPreview ? <button className={styles.primary} disabled={!attempt} onClick={() => setEntered(true)}>Enter developer workspace <ArrowRight size={17} /></button>
            : invitation?.security_required && !secureContext ? <button className={styles.primary} disabled={busy} onClick={() => invitation.integrity_policy.mode === 'browser' ? launch() : openGuide()}>Open secure assessment <ArrowRight size={17} /></button>
              : <button className={styles.primary} disabled={!consent || !invitation?.runtime_ready || busy} onClick={start}>{busy && <Loader2 className={styles.spin} size={16} />}Start assessment <ArrowRight size={17} /></button>}
        </div>
        {invitation && !invitation.runtime_ready && !developerPreview && <p className={styles.subtle}>The assessment is awaiting launch readiness. Contact {invitation.pool === 'practice' ? 'support' : 'the recruiter'} for availability.</p>}
      </section>
    </div>
  </main>;

  if (terminal) return <main className={`${rootClass} ${styles.landing}`}><header className={styles.landingHeader}>{brand}{themeButton}</header>
    <section className={styles.completion} role="status"><span className={styles.completionIcon}><CheckCircle2 size={36} /></span><span className={styles.eyebrow}>ANSWERS SAVED</span><h1>Assessment submitted</h1>
      <p>{invitation?.pool === 'practice' ? 'Your practice answers are locked. Objective results and educational feedback appear after evaluation; unavailable execution never becomes a guessed score.' : attempt.state === 'completed' ? 'Evaluation is complete. Check your application for any recruiter-released result and next steps.' : attempt.state === 'unavailable' ? 'Evaluation needs technical review. No final score has been assigned; the recruiter will confirm the next step.' : 'Your saved answers are locked and awaiting evaluation. The recruiter will confirm the next step.'}</p>
      {invitation?.pool === 'practice' && <PracticeAssessmentReport attemptId={attempt.attempt_id} oaRequest={call} />}
      {secureContext && <><button className={styles.secondary} onClick={requestPrivacy}>Request evidence deletion review</button>{privacyNotice && <p>{privacyNotice}</p>}</>}
    </section></main>;

  if (!question) return <main className={rootClass}><p className={styles.alert}>No question is available in the current section window.</p></main>;
  return <main className={`${rootClass} ${styles.workspace} ${focusEditor ? styles.editorFocused : ''}`}>
    <header className={styles.workspaceHeader}>{brand}<span className={styles.assessmentName}>{developerPreview ? 'Assessment preview' : summary?.title || 'Online assessment'}</span>
      <div className={styles.headerRight}><span className={styles.saveState} role="status">{saving ? <Loader2 size={14} className={styles.spin} /> : dirty ? <span className={styles.unsavedDot} /> : <CheckCircle2 size={14} />}{saving ? 'Saving…' : dirty ? 'Unsaved local changes' : 'All changes acknowledged by server'}</span>
        {developerPreview ? <span className={styles.previewBadge}>Developer workspace — no timed exam</span> : <span className={`${styles.timerBadge} ${remaining < 300 ? styles.urgent : ''}`} role="timer" aria-label="Total time remaining"><Clock3 size={16} />{duration(remaining)}</span>}
        {attempt.timer_mode === 'section' && sectionRemaining !== null && <span className={styles.timerBadge} role="timer" aria-label="Section time remaining">Section {duration(sectionRemaining)}</span>}
        {themeButton}<button className={styles.primary} disabled={busy || saving} onClick={submit}>{developerPreview ? 'Test final submission' : 'Submit and lock assessment'}<ArrowRight size={16} /></button>
      </div>
    </header>
    {error && <p role="alert" className={styles.alert}>{error}</p>}
    <div className={`${styles.workspaceBody} ${!coding && !sql ? styles.choiceLayout : ''}`} ref={body} style={{ '--problem-width': `${split}%` }}>
      <aside className={styles.questionRail}><div className={styles.railTitle}><ListChecks size={19} /><span>{count}/{questions.length}</span></div>
        <nav aria-label="Assessment question navigation">{['coding', 'sql', 'mcq'].map(type => {
          const selected = questions.filter(q => q.type === type); if (!selected.length) return null;
          const Icon = type === 'coding' ? Code2 : type === 'sql' ? Database : ListChecks;
          return <div className={styles.railGroup} key={type}><span className={styles.railGroupLabel}><Icon size={15} /><span>{type === 'mcq' ? 'MCQ' : kinds[type]}</span></span>
            {selected.map(q => { const position = questions.indexOf(q); return <button key={q.id} className={`${styles.questionNumber} ${q.id === question.id ? styles.activeQuestion : ''} ${answered(answers[q.id]) ? styles.answeredQuestion : ''}`} aria-label={`Go to question ${position + 1}: ${q.title}`} aria-current={q.id === question.id ? 'step' : undefined} onClick={() => navigate(q.id)}>
              <span>{String(position + 1).padStart(2, '0')}</span>{flagged.has(q.id) ? <Bookmark size={11} /> : answered(answers[q.id]) ? <Check size={12} /> : <span className={styles.emptyStatus} />}</button>; })}
          </div>;
        })}</nav><span className={styles.railFoot}><ShieldCheck size={17} /></span></aside>

      <section className={`${styles.problemPanel} ${!coding && !sql ? styles.choicePanel : ''}`} id={`oa-question-${question.id}`} tabIndex={-1} aria-label={`Question ${index + 1}`}>
        <div className={styles.panelTabs} role="tablist" aria-label="Question details">
          {[['problem', 'Problem', FileText], ['examples', 'Examples', ListChecks], ...(sql ? [['schema', 'Schema', Database]] : [])].filter(item => question.type !== 'mcq' || item[0] === 'problem').map(([id, label, Icon]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}><Icon size={15} />{label}</button>)}
          <button className={styles.flagButton} aria-label="Mark question for review" aria-pressed={flagged.has(question.id)} onClick={toggleFlag}><Bookmark size={17} /></button>
        </div>
        <div className={styles.problemContent}>
          <div className={styles.questionMeta}><span>QUESTION {String(index + 1).padStart(2, '0')} / {questions.length}</span><span>{kinds[question.type]}<i />{question.marks} {question.marks === 1 ? 'mark' : 'marks'}</span></div>
          <h1 ref={heading} tabIndex={-1}>{question.title}</h1>
          {(tab === 'problem' || question.type === 'mcq') && <>
            <p className={styles.statement}>{question.statement}</p>
            {coding && <>
              {question.coding.signature && <section className={styles.signature}><h3>Function signature</h3><code>{question.coding.signature.return_type} {question.coding.signature.name}({question.coding.signature.parameters.map(parameter => `${parameter.type} ${parameter.name}`).join(', ')})</code></section>}
              <h3>Input format</h3><p>{question.coding.input_format}</p><h3>Output format</h3><p>{question.coding.output_format}</p><h3>Constraints</h3><p>{question.coding.constraints}</p>
              <Examples question={question} />
            </>}
            {sql && <><p className={styles.dialectTag}><Database size={14} />{question.sql.engine.toUpperCase()} · {question.sql.engine_version}</p><h3>Database schema</h3><SqlCode label="Database schema" source={question.sql.schema_sql} engine={question.sql.engine} /><Examples question={question} /></>}
            {question.type === 'mcq' && <fieldset className={styles.answerChoices}><legend>{question.mcq.selection === 'single' ? 'Select one answer' : 'Select all correct answers'}</legend>
              {question.mcq.options.map((option, position) => <label className={(answers[question.id]?.option_ids || []).includes(option.id) ? styles.selectedChoice : ''} key={option.id}><input type={question.mcq.selection === 'single' ? 'radio' : 'checkbox'} name={question.id} checked={(answers[question.id]?.option_ids || []).includes(option.id)} disabled={busy}
                onChange={event => change(question.id, { option_ids: question.mcq.selection === 'single' ? [option.id] : event.target.checked ? [...(answers[question.id]?.option_ids || []), option.id] : (answers[question.id]?.option_ids || []).filter(id => id !== option.id) })} /><span className={styles.optionLetter}>{String.fromCharCode(65 + position)}</span><span>{option.text}</span><CheckCircle2 className={styles.choiceCheck} size={18} /></label>)}
              <button className={styles.textButton} disabled={busy} onClick={() => change(question.id, { option_ids: [] })}>Clear selection</button>
            </fieldset>}
          </>}
          {tab === 'examples' && (coding || sql) && <Examples question={question} />}
          {tab === 'schema' && sql && <><h3>Database schema</h3><SqlCode label="Database schema" source={question.sql.schema_sql} engine={question.sql.engine} /><p className={styles.subtle}>Each test uses an independent dataset. Write one read-only SELECT or WITH query.</p></>}
        </div>
        <footer className={styles.problemFooter}><button className={styles.iconButton} disabled={index === 0} aria-label="Previous question" onClick={() => navigate(questions[index - 1].id)}><ChevronLeft size={18} /></button><span>{index + 1} of {questions.length}</span>
          <button className={styles.secondary} disabled={saving || busy} onClick={next}>Save & next<ChevronRight size={16} /></button></footer>
      </section>

      {(coding || sql) && <>
        <div className={styles.splitter} role="separator" aria-label="Problem panel width" aria-orientation="vertical" aria-valuenow={Math.round(split)} aria-valuemin={30} aria-valuemax={65} tabIndex={0} onPointerDown={resize}
          onKeyDown={event => { if (['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); setSplit(value => Math.max(30, Math.min(65, value + (event.key === 'ArrowRight' ? 2 : -2)))); } }}><span /></div>
        <section className={styles.idePanel} aria-label="Coding workspace">
          <header className={styles.editorToolbar}><span className={styles.fileTab}><Code2 size={15} />{language === 'java' ? 'Main.java' : `solution.${extensions[language] || 'sql'}`}</span>
            <div className={styles.editorTools}>{coding ? <label>Language<select aria-label="Language" value={language} disabled={busy} onChange={event => languageChange(question, event.target.value)}>{question.coding.languages.map(value => <option key={value} value={value}>{names[value] || value} · {question.coding.runtime_versions[value]}</option>)}</select></label> : <span className={styles.editorDialect}>{question.sql.engine.toUpperCase()}</span>}
              <label className={styles.fontControl}>Font size<select aria-label="Editor font size" value={fontSize} onChange={event => setFontSize(Number(event.target.value))}>{[12, 14, 16, 18].map(size => <option key={size} value={size}>{size}px</option>)}</select></label>
              <button className={styles.secondary} title="Format code (Shift+Alt+F)" disabled={busy || formatting} onClick={() => editorCommands.current?.format()}>{formatting ? 'Formatting...' : 'Format code'}</button>
              <button className={styles.iconButton} aria-label="Undo code edit" disabled={busy} onClick={() => editorCommands.current?.undo()}><Undo2 size={15} /></button>
              <button className={styles.iconButton} aria-label="Redo code edit" disabled={busy} onClick={() => editorCommands.current?.redo()}><Redo2 size={15} /></button>
              <button className={styles.iconButton} aria-label="Find in code" onClick={() => editorCommands.current?.find()}><Search size={15} /></button>
              <button className={styles.iconButton} aria-label="Reset code to starter" disabled={busy} onClick={() => setResetPrompt(true)}><RotateCcw size={15} /></button>
              <button className={styles.iconButton} aria-label={focusEditor ? 'Restore split layout' : 'Focus editor'} onClick={() => setFocusEditor(value => !value)}>{focusEditor ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button>
            </div>
          </header>
          <div className={styles.editorHost}><CodeEditor key={`${question.id}:${language}`} commandsRef={editorCommands} onFormatNotice={setFormatNotice} onFormattingChange={setFormatting} autoFormatInitial={coding && source === question.coding.starter_code[language]} dialect={sql ? question.sql.engine : undefined} label={`Answer for ${question.title}`} readOnly={busy} language={language} value={source} defaultOpen fill theme={dark ? 'vs-dark' : 'vs'} fontSize={fontSize}
            clipboardRef={secureContext?.clipboard === 'internal_editor' ? clipboard : undefined} onChange={value => { setFormatNotice(''); change(question.id, { language, source: value }); }} /></div>
          <div className={styles.editorStatus}><span role="status"><span className={styles.liveDot} />{saving ? 'Saving…' : dirty ? 'Unsaved changes' : formatNotice || 'Saved'}</span><span>{source.split('\n').length} lines · UTF-8 · {fontSize}px</span></div>
          <section className={`${styles.resultsPanel} ${!resultsOpen ? styles.resultsCollapsed : ''}`} aria-label="Run output">
            <div className={styles.resultsHeader}><button onClick={() => setResultsOpen(value => !value)} aria-expanded={resultsOpen}><Terminal size={15} />Test results<ChevronDown size={15} /></button>
              <div className={styles.runActions}>{coding && <button className={styles.secondary} disabled={busy || pendingRun} onClick={() => { setResultsOpen(true); setResultTab('results'); runCode(question, true); }}>Run custom input</button>}<button className={styles.runButton} disabled={busy || pendingRun} onClick={() => { setResultsOpen(true); setResultTab('results'); runCode(question); }}>{pendingRun ? <Loader2 className={styles.spin} size={15} /> : <Play size={15} />}Run public example</button></div></div>
            {resultsOpen && <><div className={styles.resultTabs} role="tablist" aria-label="Execution panel"><button role="tab" aria-selected={resultTab === 'results'} onClick={() => setResultTab('results')}>Output{currentRun?.result && <span className={currentRun.result.status === 'ok' ? styles.successDot : styles.unsavedDot} />}</button>{coding && <button role="tab" aria-selected={resultTab === 'input'} onClick={() => setResultTab('input')}>Custom input</button>}</div>
              <div className={styles.resultContent}>{resultTab === 'input' && coding ? <label>{question.coding.contract === 'function' ? 'Custom input (JSON object keyed by parameter names)' : 'Custom standard input'}<textarea value={custom[question.id] || ''} spellCheck={false} onChange={event => setCustom(previous => ({ ...previous, [question.id]: event.target.value }))} /></label>
                : currentRun ? <><div className={styles.runVerdict}><span className={currentRun.result?.status === 'ok' ? styles.successText : styles.subtle}>{currentRun.result?.status === 'ok' ? <CheckCircle2 size={16} /> : <Terminal size={16} />}{(currentRun.result?.status || currentRun.state).replaceAll('_', ' ')}</span>{currentRun.result?.time_ms !== undefined && <small>{Math.round(currentRun.result.time_ms)} ms</small>}</div>
                  {currentRun.result?.stdout !== undefined && <pre>{currentRun.result.stdout || '(no output)'}</pre>}
                  {currentRun.result?.diagnostics && <pre aria-label="Compiler or runtime diagnostics" className={styles.diagnostics}>{currentRun.result.diagnostics}</pre>}
                  {currentRun.result?.columns && <ResultTable columns={currentRun.result.columns} rows={currentRun.result.rows || []} />}
                  {['dispatch_unknown', 'blocked'].includes(currentRun.state) && <p>This run needs operator reconciliation. You can still save answers and submit.</p>}
                  <p className={styles.outputNote}>Public run only. Final marks use the assessment’s validated grading cases.</p>
                </> : <div className={styles.emptyOutput}><Terminal size={24} /><p>Run your solution to see the output here.</p><small>Public examples help you test. Final submission evaluates the hidden cases.</small></div>}</div>
            </>}
          </section>
        </section>
      </>}
    </div>
    <footer className={styles.workspaceFooter}><span><ShieldCheck size={13} />{developerPreview ? 'Local developer session' : 'GenHire assessment'}<i />{count} of {questions.length} answered{flagged.size > 0 && <><i /><Flag size={12} />{flagged.size} for review</>}</span><div><button disabled={saving || !dirty} onClick={save}>Retry / save answers</button><button disabled={busy || saving} onClick={reload}>Reload server answers</button></div></footer>
    <ConfirmDialog isOpen={resetPrompt} title="Reset your code?" message="This replaces the current answer with starter code. Your current edits will be replaced." confirmText="Reset code" cancelText="Keep editing" onClose={() => setResetPrompt(false)} onConfirm={() => { change(question.id, { language, source: coding ? question.coding.starter_code[language] : '' }); setResetPrompt(false); }} />
  </main>;
}

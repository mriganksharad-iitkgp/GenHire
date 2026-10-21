import React,{useId} from 'react';
import { applyRoleTemplate, localInput, resizeSection, WIZARD_STEPS } from '../utils/jobSetup';
import { roleForTitle } from '../utils/jobTemplates';
import TermHelp from './TermHelp';
import styles from './HiringSetupWizard.module.css';

const languageNames = { python: 'Python', javascript: 'JavaScript', java: 'Java', cpp: 'C++' };
const sectionNames = { coding: 'Coding', mcq: 'MCQ', sql: 'SQL' };
const termHints={
  Applications:'Cohort: collect applications until one deadline, then screen the group. Rolling: candidates can apply continuously until the final deadline.',
  'Screening availability':'After applications close: screen the cohort together. Rolling screening: candidates can start during the configured screening window without waiting for applications to close.',
  'OA activation':'Scheduled uses the saved assessment window once content is ready. Manual means you decide when to activate the OA and send eligible invitations.',
  'Default coding format':'Standard input/output tasks read input and print an answer. Function tasks provide a named function or method for the candidate to implement.',
  'SQL engine':'The database dialect used to execute queries. PostgreSQL and MySQL differ in syntax and behavior; author and test the question for the selected engine.',
  'MCQ answer types':'Single correct: one answer. Multiple correct: candidates must select the exact set of correct options. Mixed allows both styles.',
  'Timer mode':'Shared gives one countdown for the whole assessment. Section timers assign a fixed time to each section; completed sections cannot be revisited.',
  'OA monitoring':'Basic uses Secure Browser integrity checks. Camera and dual-device options add configured camera evidence and may have extra quoted costs.',
};

function Numeric({ label, value, onChange, min = 0, max = 100, step = 1, fallback }) {
  return <label className={styles.field}>{label}<input type="number" min={min} max={max} step={step}
    value={value ?? ''} placeholder={fallback === undefined ? undefined : `Default: ${fallback}`}
    onBlur={e=>{if(e.target.value===''&&fallback!==undefined)onChange(fallback);}}
    onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))} /></label>;
}
function Select({ label, value, onChange, options, help }) {
  const id=useId();
  return <div className={styles.field}><span className={styles.fieldHeading}><label htmlFor={id}>{label}</label>{(help||termHints[label])&&<TermHelp term={label}>{help||termHints[label]}</TermHelp>}</span><select id={id} value={value} onChange={e => onChange(e.target.value)}>
    {options.map(option => <option key={option[0]} value={option[0]}>{option[1]}</option>)}
  </select></div>;
}
function Toggle({ label, value, onChange, disabled=false }) {
  return <label className={styles.toggle}><input type="checkbox" checked={value} disabled={disabled} onChange={e => onChange(e.target.checked)} />{label}</label>;
}

export function JobWizardNav({ enabled, step, setStep }) {
  if (!enabled) return null;
  return <nav className={styles.steps} aria-label="Job setup steps">
    {WIZARD_STEPS.map((name, index) => <button key={name} type="button" aria-current={step === index ? 'step' : undefined}
      className={step === index ? styles.currentStep : ''} onClick={() => setStep(index)}><span>{index + 1}</span>{name}</button>)}
  </nav>;
}

export function SetupNotice({ setup }) {
  return <>
    {setup.error && <div role="alert" className={styles.error}><p>Hiring settings could not be loaded. Your job details are still here.</p><p>{setup.error}</p><button type="button" onClick={setup.reload}>Retry hiring settings</button></div>}

  </>;
}

export function AssessmentSetupCard({setup,jobTitle,onConfigure}) {
  const role=roleForTitle(jobTitle), c=setup.configuration;
  const preset=setup.catalog?.templates?.find(t=>t.id===(c?.pipeline.oa_enabled?c.oa.template_id:role.oaTemplateId));
  return <section className={styles.assessmentEntry} aria-label="Online assessment setup">
    <div><span className={styles.eyebrow}>Your hiring process</span><h3>AI screening + optional online assessment</h3><p>Role-based coding, SQL and MCQs after screening. All settings are editable.</p></div>
    {setup.loading ? <p role="status">Loading hiring settings...</p> : !setup.enabled || !c ? <div><p>Assessment settings are currently unavailable for this workspace. Your job details remain editable.</p><button type="button" onClick={setup.reload}>Reload assessment options</button></div> : <>
      <Toggle label="Include an online assessment" value={c.pipeline.oa_enabled} onChange={setup.setAssessmentEnabled} disabled={!jobTitle.trim()&&!c.pipeline.oa_enabled}/>
      {!jobTitle.trim()&&<p className={styles.hint}>Choose a role template or enter the job title below to load matching OA defaults.</p>}
      <p className={styles.hint}>{c.pipeline.oa_enabled?'OA included':'Suggested plan'}: {preset?.name || 'Custom role'}{preset && ` — ${preset.sections.map(s=>`${s.count} ${sectionNames[s.type]}`).join(' + ')}, ${preset.duration_minutes} minutes`}.</p>
      {c.pipeline.oa_enabled&&<div className={styles.entryActions}><button type="button" onClick={onConfigure}>Customize assessment</button><span>Questions are drafted and reviewed before activation.</span></div>}
    </>}
  </section>;
}

export function PricingNote({ setup, editing = false }) {
  const prices = setup.catalog?.prices;
  if (!prices) return <span>Pricing is loading or unavailable. AI drafting is available once its credit price is loaded.</span>;
  return <span>AI drafting: {prices.ai_jd} credits total per JD, including selected OA questions. Manual {editing ? 'edits' : 'creation'} are free.
    {' '}Screening: {prices.screening} credits per candidate, or {prices.screening_proctored} with monitoring.</span>;
}

export default function HiringSetupWizard({ setup, step, onSaveDraft, editing = false, questionEditor, onAuthoringMode, inline=false }) {
  if (!setup.enabled || step === 0) return null;
  const c = setup.configuration;
  if (!c) return <p role="status">Loading saved hiring configuration…</p>;
  const change = (group, key, value) => setup.setConfiguration(current => ({ ...current, [group]: { ...current[group], [key]: value } }));
  const oa = c.oa;
  const sectionChange = (type, transform) => change('oa', 'sections', oa.sections.map(s => s.type === type ? transform(s) : s));
  const dateLabels = { application_closes_at: 'Applications close', screening_opens_at: 'Screening opens',
    screening_closes_at: 'Screening must finish by', oa_opens_at: 'OA opens', oa_start_closes_at: 'Last time to start OA' };
  const price = setup.preview?.quote;

  return <section className={styles.panel} aria-label={WIZARD_STEPS[step]}>
    {step === 1 && <>
      <h3>Build your hiring pipeline</h3>
      <p>Application review → AI screening → optional online assessment → your company rounds.</p>
      {!inline&&<Toggle label="Include an online assessment" value={c.pipeline.oa_enabled} onChange={setup.setAssessmentEnabled} />}
      <Select label="After screening clearance" value={c.pipeline.advancement} onChange={v => change('pipeline', 'advancement', v)}
        help="Manual means you choose who receives the next invitation. Automatic means eligible candidates are invited only once the OA is ready and activated. Clearing screening alone does not guarantee an invitation."
        options={[[ 'manual', 'Recruiter approves the next-round invitation' ], [ 'automatic', 'Automatically invite eligible candidates when OA is active' ]]} />
      <p className={styles.hint}>Screening clearance and a next-round invitation are separate. Integrity concerns and required missing evidence go to recruiter review.</p>
      <div className={styles.grid}>
        <Numeric label="Minimum screening interview score (%)" value={c.qualification.interview_minimum} fallback={60} onChange={v => change('qualification', 'interview_minimum', v)} />
        <Numeric label="Minimum proctoring score (%)" value={c.qualification.proctoring_minimum} fallback={70} onChange={v => change('qualification', 'proctoring_minimum', v)} />
        {c.pipeline.oa_enabled&&<Numeric label="OA qualification score (%) — optional" value={c.qualification.oa_minimum} onChange={v => change('qualification', 'oa_minimum', v)} />}
      </div>
      <p className={styles.hint}>Defaults: interview 60%, proctoring 70%. The proctoring minimum applies when the requirement below is enabled.</p>
      <Toggle label="Require a usable proctoring score for screening qualification" value={c.qualification.require_proctoring}
        onChange={v => change('qualification', 'require_proctoring', v)} />
      <h4>Company-managed rounds</h4>
      <p className={styles.hint}>Your team conducts these interviews. Names and order are editable.</p>
      {c.pipeline.company_stages.map((stage, index) => <div key={stage.id} className={styles.round}>
        <label className={styles.field}>Round {index + 1} name<input maxLength={80} value={stage.name} onChange={e => change('pipeline', 'company_stages',
          c.pipeline.company_stages.map(s => s.id === stage.id ? { ...s, name: e.target.value } : s))} /></label>
        <button type="button" disabled={index === 0} aria-label={`Move ${stage.name} earlier`} onClick={() => {
          const rounds = [...c.pipeline.company_stages]; [rounds[index - 1], rounds[index]] = [rounds[index], rounds[index - 1]];
          change('pipeline', 'company_stages', rounds);
        }}>↑</button>
        <button type="button" aria-label={`Remove ${stage.name}`} onClick={() => change('pipeline', 'company_stages', c.pipeline.company_stages.filter(s => s.id !== stage.id))}>Remove</button>
      </div>)}
      <button type="button" disabled={c.pipeline.company_stages.length >= 8} onClick={() => change('pipeline', 'company_stages',
        [...c.pipeline.company_stages, { id: `company_${crypto.randomUUID().replaceAll('-', '').slice(0, 12)}`, name: 'Company interview' }])}>Add company round</button>
    </>}

    {step === 2 && <>
      <h3>Configure your online assessment</h3>
      {!c.pipeline.oa_enabled ? <p className={styles.notice}>OA is optional and currently off. You can add it later for eligible candidates. Choose Include an online assessment above to configure it.</p> : <>
        <div className={styles.notice}><p>Apply matching counts, marks and timing. This replaces your OA plan settings.</p><button type="button" onClick={setup.resetRoleAssessment}>Use current role defaults</button></div>
        <div key={setup.actionNotice?.id} role="status" className={styles.hint}>{setup.actionNotice?.text}</div>
        <div className={styles.grid}>
          <Select label="Role template" value={oa.template_id} onChange={id => setup.setConfiguration(current => applyRoleTemplate(current, setup.catalog.templates.find(t => t.id === id)))}
            options={setup.catalog.templates.map(t => [t.id, t.name])} />
          {oa.template_id === 'web_developer' && <Select label="Developer specialization" value={oa.specialization} onChange={v => change('oa', 'specialization', v)}
            options={[[ 'general', 'General' ], [ 'frontend', 'Frontend' ], [ 'backend', 'Backend' ], [ 'full_stack', 'Full-stack' ]]} />}
          <Select label="Question creation method" value={oa.source} onChange={v => { change('oa', 'source', v); onAuthoringMode?.(v==='ai'?'ai':'manual'); }}
            help="AI drafts questions for your review. Recruiter-authored means you enter questions and answers yourself. Existing mixed assessments may contain both manual and generated drafts. The complete AI draft costs the amount shown in Fill with AI."
            options={[[ 'ai', 'AI drafts JD and questions together' ], [ 'manual', 'Fill all questions manually' ], ...(oa.source==='hybrid'?[[ 'hybrid', 'Existing mixed assessment' ]]:[])]} />
        </div>
        
        <p className={styles.hint}>{oa.source==='manual'?'Enter your complete questions below. No AI is used.':'Open Fill with AI below to fill the JD and all selected question types in one paid action. Generated questions appear below for review.'}</p>
        {questionEditor}
        {oa.source!=='manual'&&<label className={styles.field}>Instructions for assessment generation<textarea rows={2} maxLength={4000} value={oa.instructions}
          placeholder="Skills, topics, scenarios and question requirements…" onChange={e => change('oa', 'instructions', e.target.value)} /></label>}
        {['coding', 'mcq', 'sql'].map(kind => {
          const item = oa.sections.find(s => s.type === kind);
          return <details key={kind} className={styles.accordion}><summary>{sectionNames[kind]} plan - {item?.count||0} questions</summary>
            {!item ? <button type="button" onClick={() => change('oa', 'sections', [...oa.sections, {
              type: kind, count: 0, difficulty: { easy: 0, medium: 0, hard: 0 }, marks: [], weight: 0, duration_minutes: 0,
            }])}>Add {sectionNames[kind]} section</button> : <>
              <div className={styles.grid}>
                <Numeric label={`${sectionNames[kind]} question count`} value={item.count} max={kind === 'mcq' ? 100 : 10}
                  onChange={v => sectionChange(kind, s => resizeSection(s, v ?? 0))} />
                <Numeric label={`${sectionNames[kind]} score weight (%)`} value={item.weight} onChange={v => sectionChange(kind, s => ({ ...s, weight: v }))} />
                <Numeric label={`${sectionNames[kind]} section minutes`} value={item.duration_minutes} max={300}
                  onChange={v => sectionChange(kind, s => ({ ...s, duration_minutes: v }))} />
              </div>
              <div className={styles.grid}>{['easy', 'medium', 'hard'].map(d => <Numeric key={d} label={`${sectionNames[kind]} ${d} questions`}
                value={item.difficulty[d]} onChange={v => sectionChange(kind, s => ({ ...s, difficulty: { ...s.difficulty, [d]: v } }))} />)}</div>
              <details><summary>Marks per question ({item.count})</summary><div className={styles.marks}>
                {item.marks.map((mark, i) => <Numeric key={i} label={`${sectionNames[kind]} question ${i + 1} marks`} value={mark} min={0.01} max={1000} step={0.01}
                  onChange={v => sectionChange(kind, s => ({ ...s, marks: s.marks.map((m, index) => index === i ? v : m) }))} />)}
              </div></details>
            </>}
          </details>;
        })}
        <div className={styles.grid}>
          <Select label="Default coding format" value={oa.coding_contract} onChange={v => change('oa', 'coding_contract', v)}
            options={[[ 'stdin_stdout', 'Standard input / output' ], [ 'function', 'Function signature (LeetCode-style)' ]]} />
          <Select label="SQL engine" value={oa.sql_engine} onChange={v => change('oa', 'sql_engine', v)} options={[[ 'postgresql', 'PostgreSQL' ], [ 'mysql', 'MySQL' ]]} />
          <Select label="MCQ answer types" value={oa.mcq_mode} onChange={v => change('oa', 'mcq_mode', v)}
            options={[[ 'single', 'Single correct' ], [ 'multiple', 'Multiple correct' ], [ 'mixed', 'Both types' ]]} />
        </div>
        <details className={styles.accordion}><summary>Allowed coding languages</summary><div className={styles.languageChoices}>
          {setup.catalog.languages.map(language => <Toggle key={language} label={languageNames[language]} value={oa.languages.includes(language)} onChange={checked =>
            change('oa', 'languages', checked ? [...oa.languages, language] : oa.languages.filter(l => l !== language))} />)}
        </div></details>
        <p className={styles.hint}>Coding earns weighted test-case partial credit. MCQs have no negative marking; multiple-correct answers use exact matching. SQL is graded on returned results.</p>
      </>}
    </>}

    {step === 3 && <>
      <h3>Schedule, review and save</h3>
      <div className={styles.grid}>
        <label className={styles.field}>Job timezone (IANA)<input value={c.schedule.timezone} placeholder="Asia/Kolkata" maxLength={80} onChange={e => change('schedule', 'timezone', e.target.value)} /></label>
        <Select label="Applications" value={c.schedule.application_mode} onChange={v => change('schedule', 'application_mode', v)} options={[[ 'cohort', 'Cohort deadline' ], [ 'rolling', 'Rolling, until deadline' ]]} />
        <Select label="Screening availability" value={c.schedule.screening_mode} onChange={v => change('schedule', 'screening_mode', v)} options={[[ 'cohort', 'After applications close' ], [ 'rolling', 'Rolling screening' ]]} />
        {c.pipeline.oa_enabled&&<Select label="OA activation" value={c.schedule.oa_activation} onChange={v => change('schedule', 'oa_activation', v)} options={[[ 'scheduled', 'Configured schedule' ], [ 'manual', 'Recruiter activates later' ]]} />}
      </div>
      <div className={styles.grid}>{Object.entries(dateLabels).filter(([key])=>c.pipeline.oa_enabled||!key.startsWith('oa_')).map(([key, label]) => <label className={styles.field} key={key}>{label}
        <input type="datetime-local" value={localInput(c.schedule[key], c.schedule.timezone)} onChange={e => change('schedule', key, e.target.value)} /></label>)}</div>
      <p className={styles.hint}>Defaults: applications 7 days, screening 3 days, then OA at 09:00 the next day with a 24-hour start window. Screening must finish by its close. A candidate who starts OA in time receives the full attempt duration, even after entry closes.</p>
      {c.pipeline.oa_enabled && <>
        <div className={styles.grid}>
          <Numeric label="Total OA minutes" value={oa.duration_minutes} min={5} max={300} onChange={v => change('oa', 'duration_minutes', v)} />
          <Select label="Timer mode" value={oa.timer_mode} onChange={v => setup.setConfiguration(current => ({ ...current, oa: { ...current.oa, timer_mode: v, revisit_allowed: v === 'shared' } }))}
            options={[[ 'shared', 'One shared countdown' ], [ 'section', 'Fixed section countdowns' ]]} />
          <Select label="OA monitoring" value={oa.proctoring_level} onChange={v => change('oa', 'proctoring_level', v)}
            options={[[ 'basic', 'Basic secure-browser checks' ], [ 'camera', 'Camera monitoring' ], [ 'dual', 'Dual-device monitoring' ]]} />
          <Numeric label="Validated question variants" value={oa.variant_count} min={1} max={5} onChange={v => change('oa', 'variant_count', v)} />
        </div>
        {oa.timer_mode==='section'&&<fieldset className={styles.sectionCard}>
          <legend>Section timing & score weights</legend>
          <p className={styles.hint}>Role defaults are prefilled. Times must total the OA duration; score weights must total 100%.</p>
          <div className={styles.grid}>{oa.sections.filter(s=>s.count>0).map(item=><fieldset key={item.type} className={styles.sectionCard}>
            <legend>{sectionNames[item.type]}</legend>
            <Numeric label={`${sectionNames[item.type]} countdown minutes`} value={item.duration_minutes} min={1} max={300}
              onChange={v=>sectionChange(item.type,s=>({...s,duration_minutes:v}))}/>
            <Numeric label={`${sectionNames[item.type]} contribution to final score (%)`} value={item.weight} min={0.01} max={100} step={0.01}
              onChange={v=>sectionChange(item.type,s=>({...s,weight:v}))}/>
          </fieldset>)}</div>
          <p role="status" className={styles.hint}>Total score weight: {oa.sections.reduce((sum,s)=>sum+(s.weight||0),0)}% · Section time: {oa.sections.reduce((sum,s)=>sum+(s.duration_minutes||0),0)}/{oa.duration_minutes} minutes</p>
        </fieldset>}
        <Toggle label="Allow revisiting questions while their section remains open" value={oa.revisit_allowed} onChange={v => change('oa', 'revisit_allowed', v)} />
        <p>Recruitment similarity reports are separately quoted after evaluation from candidate review. Enriched analytics and AI authorship detection are unavailable and cannot be purchased.</p>
        {(oa.advanced_analytics || oa.plagiarism_check) && <button type="button" onClick={() => setup.setConfiguration(current => ({...current,oa:{...current.oa,advanced_analytics:false,plagiarism_check:false}}))}>Remove deferred extras from this draft</button>}
      </>}
      <div className={styles.review}>
        <h4>Planned candidate journey</h4>
        <p>Application review → AI screening{c.pipeline.oa_enabled ? ' → Online assessment' : ''}{c.pipeline.company_stages.map(s => ` → ${s.name}`).join('')}</p>
        <p>{c.pipeline.advancement === 'manual' ? 'Cleared candidates await your next-round decision.' : 'Eligible candidates can be invited automatically when the assessment is activated.'}</p>
        {c.pipeline.oa_enabled && <p>{oa.sections.reduce((total, s) => total + s.count, 0)} questions · {oa.duration_minutes} minutes · {oa.source} authoring · {oa.coding_contract === 'function' ? 'Function tasks' : 'Input/output tasks'} · {oa.sql_engine === 'mysql' ? 'MySQL' : 'PostgreSQL'}</p>}
        <h4>Credit preview</h4>
        {price ? <>
          <p>Due now for saving configuration: <strong>{price.charges_now} credits</strong>.</p>
          <PricingNote setup={setup} editing={editing} />
          {price.line_items.length > 0 && <details className={styles.compactHelp}><summary>Future OA charges and when they apply</summary><div className={styles.tableScroll}><table><caption>Prospective OA charges — units are separate</caption><thead><tr><th>Feature</th><th>Credits</th><th>When charged</th></tr></thead><tbody>
            {price.line_items.map(line => <tr key={line.code}><td>{line.label}{line.quantity > 1 ? ` × ${line.quantity}` : ''}</td><td>{line.subtotal ?? 'Not configured'}</td><td>{line.unit.replaceAll('_', ' ')}</td></tr>)}
          </tbody></table></div></details>}
          <p className={styles.hint}>Basic scores, section reports, objective grading, autosave and required security are included. This preview expires after 15 minutes; final charges require a fresh confirmation.</p>
        </> : <p>Validating configuration and loading its credit preview…</p>}
        <p className={styles.hint}>Publish this job now to accept applications. Your OA questions stay private to your recruiting team. Assessment delivery is configured separately; existing candidates keep their current workflow.</p>
      </div>
    </>}
    {setup.previewPending && <p role="status" className={styles.hint}>Checking configuration…</p>}
    {setup.previewError && <p role="alert" className={styles.error}>{setup.previewError}</p>}
    {(!inline || step===3)&&<div className={styles.draftActions}>
      <button type="button" onClick={onSaveDraft} disabled={setup.saving || !setup.ready}>{setup.saving ? 'Saving…' : 'Save hiring draft'}</button>
      {setup.savedAt && <span role="status">Draft saved. You can resume it later.</span>}
    </div>}
  </section>;
}

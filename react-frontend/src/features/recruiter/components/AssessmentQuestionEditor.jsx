import React, { useLayoutEffect, useRef } from 'react';
import styles from './HiringSetupWizard.module.css';
import QuestionAccordionGroup from './QuestionAccordionGroup';
import CodeEditor from 'shared/components/ui/CodeEditor';

const TYPES = ['integer', 'number', 'string', 'boolean', 'integer[]', 'number[]', 'string[]', 'boolean[]'];
const languageNames = { python: 'Python', javascript: 'JavaScript', java: 'Java', cpp: 'C++', c: 'C', nodejs: 'Node.js' };
function Text({ label, value, change, multiline = false, rows = 2 }) {
  const input = useRef(null);
  useLayoutEffect(() => { if (input.current) { input.current.style.height = 'auto'; input.current.style.height = `${Math.min(220, Math.max(56, input.current.scrollHeight))}px`; } }, [value]);
  return <label className={styles.field}>{label}{multiline ? <textarea ref={input} rows={rows} value={value} onChange={e => change(e.target.value)} /> : <input value={value} onChange={e => change(e.target.value)} />}</label>;
}
function NumberField({ label, value, change, min = 0, max = 1000, step = 1 }) {
  return <label className={styles.field}>{label}<input type="number" min={min} max={max} step={step} value={value ?? ''} onChange={e => change(e.target.value === '' ? null : Number(e.target.value))} /></label>;
}
function Select({ label, value, options, change }) {
  return <label className={styles.field}>{label}<select value={value} onChange={e => change(e.target.value)}>{options.map(o => <option key={o} value={o}>{o}</option>)}</select></label>;
}

export default function AssessmentQuestionEditor({ value: q, onChange, onSave, busy }) {
  if (!q) return null;
  const set = (key, value) => onChange({ ...q, [key]: value });
  const nested = (group, key, value) => set(group, { ...q[group], [key]: value });
  const editTest = (group, index, key, value) => nested(group, group === 'sql' ? 'datasets' : 'tests',
    q[group][group === 'sql' ? 'datasets' : 'tests'].map((t, i) => i === index ? { ...t, [key]: value } : t));
  return <fieldset disabled={busy} className={`${styles.sectionCard} ${styles.questionEditor}`}><legend>{q.type.toUpperCase()} question editor</legend>
    <Text label="Question title" value={q.title} change={v => set('title', v)} />
    <Text label="Problem statement" value={q.statement} change={v => set('statement', v)} multiline rows={3} />
    <div className={styles.grid}>
      <Select label="Difficulty" value={q.difficulty} options={['easy', 'medium', 'hard']} change={v => set('difficulty', v)} />
      <NumberField label="Maximum marks" value={q.marks} change={v => set('marks', v)} min={0.01} step={0.01} />
      <Text label="Topics, separated by commas" value={q.topics} change={v => set('topics', v)} />
    </div>
    <Text label="Private answer explanation and reviewer notes" value={q.explanation} change={v => set('explanation', v)} multiline />
    {q.mcq && <>
      <Select label="Answer selection" value={q.mcq.selection} options={['single', 'multiple']} change={v => set('mcq', { ...q.mcq, selection: v, correct_option_ids: [] })} />
      {q.mcq.options.map((o, i) => <div key={o.id} className={styles.optionRow}>
        <Text label={`Option ${i + 1}`} value={o.text} change={v => nested('mcq', 'options', q.mcq.options.map(option => option.id === o.id ? { ...option, text: v } : option))} />
        <label className={styles.toggle}><input type={q.mcq.selection === 'single' ? 'radio' : 'checkbox'} name="answer-key"
          checked={q.mcq.correct_option_ids.includes(o.id)} onChange={e => nested('mcq', 'correct_option_ids', q.mcq.selection === 'single' ? [o.id] :
            e.target.checked ? [...q.mcq.correct_option_ids, o.id] : q.mcq.correct_option_ids.filter(id => id !== o.id))} />Correct option {i + 1}</label>
        <button type="button" disabled={q.mcq.options.length <= 2} onClick={() => set('mcq', { ...q.mcq,
          options: q.mcq.options.filter(option => option.id !== o.id), correct_option_ids: q.mcq.correct_option_ids.filter(id => id !== o.id) })}>Remove option {i + 1}</button>
      </div>)}
      <button type="button" disabled={q.mcq.options.length >= 8} onClick={() => nested('mcq', 'options', [...q.mcq.options, { id: `option${crypto.randomUUID().replaceAll('-', '').slice(0, 12)}`, text: '' }])}>Add answer option</button>
      <p className={styles.hint}>No negative marking. Multiple-correct answers require an exact match. Review the explanation and ambiguity before approving.</p>
    </>}
    {q.coding && <>
      <p>Format: {q.coding.contract === 'function' ? 'Function signature' : 'Standard input/output'} · harness {q.coding.harness_version}. Matches the saved OA blueprint.</p>
      {q.coding.signature && <fieldset className={styles.sectionCard}><legend>Typed function contract</legend>
        <Text label="Function name" value={q.coding.signature.name} change={v => nested('coding', 'signature', { ...q.coding.signature, name: v })} />
        <Select label="Return type" value={q.coding.signature.return_type} options={TYPES} change={v => nested('coding', 'signature', { ...q.coding.signature, return_type: v })} />
        {q.coding.signature.parameters.map((p, i) => <div className={styles.grid} key={i}>
          <Text label={`Parameter ${i + 1} name`} value={p.name} change={v => nested('coding', 'signature', { ...q.coding.signature,
            parameters: q.coding.signature.parameters.map((param, n) => n === i ? { ...param, name: v } : param) })} />
          <Select label={`Parameter ${i + 1} type`} value={p.type} options={TYPES} change={v => nested('coding', 'signature', { ...q.coding.signature,
            parameters: q.coding.signature.parameters.map((param, n) => n === i ? { ...param, type: v } : param) })} />
          <button type="button" disabled={q.coding.signature.parameters.length <= 1} onClick={() => nested('coding', 'signature', { ...q.coding.signature,
            parameters: q.coding.signature.parameters.filter((_, n) => n !== i) })}>Remove parameter {i + 1}</button>
        </div>)}
        <button type="button" disabled={q.coding.signature.parameters.length >= 8} onClick={() => nested('coding', 'signature', { ...q.coding.signature,
          parameters: [...q.coding.signature.parameters, { name: `parameter${q.coding.signature.parameters.length + 1}`, type: 'integer' }] })}>Add parameter</button>
      </fieldset>}
      {['input_format', 'output_format', 'constraints'].map(key => <Text key={key} label={key.replaceAll('_', ' ')} value={q.coding[key]} change={v => nested('coding', key, v)} multiline />)}
      <div className={styles.grid}>
        <NumberField label="Time limit (ms)" min={100} max={10000} value={q.coding.limits.time_ms} change={v => nested('coding', 'limits', { ...q.coding.limits, time_ms: v })} />
        <NumberField label="Memory limit (MiB)" min={64} max={512} value={q.coding.limits.memory_mb} change={v => nested('coding', 'limits', { ...q.coding.limits, memory_mb: v })} />
        <NumberField label="Output limit (KiB)" min={1} max={64} value={q.coding.limits.output_kb} change={v => nested('coding', 'limits', { ...q.coding.limits, output_kb: v })} />
        <Select label="Output comparison" value={q.coding.comparison} options={['exact', 'trim_trailing_whitespace']} change={v => nested('coding', 'comparison', v)} />
      </div>
      {q.coding.languages.map(language => <details key={language} className={styles.sectionCard}><summary>{languageNames[language]} source and runtime profile</summary>
        <Text label={`${languageNames[language]} runtime profile`} value={q.coding.runtime_versions[language]} change={v => nested('coding', 'runtime_versions', { ...q.coding.runtime_versions, [language]: v })} />
        <CodeEditor readOnly={busy} label={`${languageNames[language]} starter code`} language={language} value={q.coding.starter_code[language]} onChange={v => nested('coding', 'starter_code', { ...q.coding.starter_code, [language]: v })} />
        <CodeEditor readOnly={busy} label={`${languageNames[language]} private reference solution`} language={language} value={q.coding.reference_solutions[language]} onChange={v => nested('coding', 'reference_solutions', { ...q.coding.reference_solutions, [language]: v })} />
      </details>)}
      <p className={styles.hint}>Function references: Python/JavaScript define the named function; Java/C++ define a Solution class with an instance method. Test inputs are JSON objects keyed by parameter name; expected values use the return type.</p>
      {<QuestionAccordionGroup label="Testcases" items={q.coding.tests} title={(t,i)=>`Test ${i+1} - ${t.visibility}`} render={(t,i)=><fieldset className={styles.sectionCard}><legend>Test {i + 1}</legend>
        <Text label={`Test ${i + 1} ID`} value={t.id} change={v => editTest('coding', i, 'id', v)} />
        <Select label={`Test ${i + 1} visibility`} value={t.visibility} options={['sample', 'hidden']} change={v => editTest('coding', i, 'visibility', v)} />
        <Text label={`Test ${i + 1} input${q.coding.contract === 'function' ? ' JSON' : ''}`} value={t.input} change={v => editTest('coding', i, 'input', v)} multiline />
        <Text label={`Test ${i + 1} expected output${q.coding.contract === 'function' ? ' JSON' : ''}`} value={t.expected} change={v => editTest('coding', i, 'expected', v)} multiline />
        <NumberField label={`Test ${i + 1} weight`} value={t.weight} change={v => editTest('coding', i, 'weight', v)} min={0.01} step={0.01} />
        <Text label={`Test ${i + 1} explanation`} value={t.explanation} change={v => editTest('coding', i, 'explanation', v)} multiline />
        <button type="button" disabled={q.coding.tests.length <= 15} onClick={() => nested('coding', 'tests', q.coding.tests.filter((_, n) => n !== i))}>Remove test {i + 1}</button>
      </fieldset>}/>}
      <p className={styles.hint}>Use 15-20 cases, including sample, edge and large performance cases. Validate reference solutions before publishing.</p>
      <button type="button" disabled={q.coding.tests.length >= 20} onClick={() => nested('coding', 'tests', [...q.coding.tests, { id: `test${crypto.randomUUID().replaceAll('-','').slice(0,12)}`, visibility: 'hidden', input: q.coding.contract === 'function' ? '{}' : '', expected: q.coding.contract === 'function' ? '0' : '', weight: 1, explanation: '' }])}>Add test case</button>
    </>}
    {q.sql && <>
      <p>SQL dialect: {q.sql.engine}. Each dataset is a separate disposable fixture; never use production data.</p>
      <Text label="SQL engine version" value={q.sql.engine_version} change={v => nested('sql', 'engine_version', v)} />
      <CodeEditor readOnly={busy} label="Public schema SQL" language="sql" value={q.sql.schema_sql} onChange={v => nested('sql', 'schema_sql', v)} />
      <CodeEditor readOnly={busy} label="Private reference query" language="sql" value={q.sql.reference_query} onChange={v => nested('sql', 'reference_query', v)} />
      <label className={styles.toggle}><input type="checkbox" checked={q.sql.ordered} onChange={e => nested('sql', 'ordered', e.target.checked)} />Require result row order</label>
      <div className={styles.grid}>
        <NumberField label="SQL numeric tolerance (absolute)" value={q.sql.numeric_tolerance} max={0.001} step={0.000001} change={v => nested('sql', 'numeric_tolerance', v)} />
        <NumberField label="SQL time limit (ms)" value={q.sql.time_ms} min={100} max={10000} change={v => nested('sql', 'time_ms', v)} />
      </div>
      {<QuestionAccordionGroup label="SQL datasets" items={q.sql.datasets} title={(d,i)=>`Dataset ${i+1} - ${d.visibility}`} render={(d,i)=><fieldset className={styles.sectionCard}><legend>Dataset {i + 1}</legend>
        <Text label={`Dataset ${i + 1} ID`} value={d.id} change={v => editTest('sql', i, 'id', v)} />
        <Select label={`Dataset ${i + 1} visibility`} value={d.visibility} options={['sample', 'hidden']} change={v => editTest('sql', i, 'visibility', v)} />
        <CodeEditor readOnly={busy} label={`Dataset ${i + 1} seed SQL`} language="sql" value={d.seed_sql} onChange={v => editTest('sql', i, 'seed_sql', v)} />
        <Text label={`Dataset ${i + 1} result columns (one per line)`} value={d.columns.join('\n')} change={v => editTest('sql', i, 'columns', v.split('\n'))} multiline />
        <Text label={`Dataset ${i + 1} expected rows JSON`} value={d.expected_rows} change={v => editTest('sql', i, 'expected_rows', v)} multiline rows={5} />
        <NumberField label={`Dataset ${i + 1} weight`} value={d.weight} min={0.01} step={0.01} change={v => editTest('sql', i, 'weight', v)} />
        <Text label={`Dataset ${i + 1} explanation`} value={d.explanation} change={v => editTest('sql', i, 'explanation', v)} multiline />
        <button type="button" disabled={q.sql.datasets.length <= 2} onClick={() => nested('sql', 'datasets', q.sql.datasets.filter((_, n) => n !== i))}>Remove dataset {i + 1}</button>
      </fieldset>}/>}
      <button type="button" disabled={q.sql.datasets.length >= 20} onClick={() => nested('sql', 'datasets', [...q.sql.datasets, { id: `dataset${crypto.randomUUID().replaceAll('-','').slice(0,12)}`, visibility: 'hidden', seed_sql: '', columns: [...q.sql.datasets[0].columns], expected_rows: '[]', weight: 1, explanation: '' }])}>Add SQL dataset</button>
    </>}
    <p className={styles.notice}>Saving creates a private, immutable question version. Validation and explicit review are required before content publication.</p>
    <button type="button" onClick={onSave}>Save private question version</button>
  </fieldset>;
}

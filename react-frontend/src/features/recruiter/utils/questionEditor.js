const runtimeProfiles = { python: 'python-3.14', javascript: 'nodejs-24', nodejs: 'nodejs-24', java: 'openjdk-25', cpp: 'g++-15', c: 'gcc-15' };
const sqlProfiles = { sqlite: 'sqlite-3', duckdb: 'duckdb-1.5', postgresql: '18' };
const testCase = (id, visibility, contract) => ({ id, visibility, input: contract === 'function' ? '{"value":0}' : '',
  expected: contract === 'function' ? '0' : '', weight: 1, explanation: '' });

export function newQuestion(kind, oa) {
  const section = oa.sections.find(s => s.type === kind);
  const contract = oa.coding_contract;
  const value = { schema_version: 1, type: kind, title: '', statement: '', difficulty: 'medium', topics: '',
    marks: section?.marks[0] ?? 1, explanation: '' };
  if (kind === 'mcq') value.mcq = { selection: oa.mcq_mode === 'multiple' ? 'multiple' : 'single',
    options: [{ id: 'optionA', text: '' }, { id: 'optionB', text: '' }], correct_option_ids: [] };
  if (kind === 'coding') value.coding = { contract, signature: contract === 'function' ? {
    name: 'solve', parameters: [{ name: 'value', type: 'integer' }], return_type: 'integer' } : null,
    harness_version: 'genhire_fn_v1', input_format: '', output_format: '', constraints: '', languages: [...oa.languages],
    runtime_versions: Object.fromEntries(oa.languages.map(l => [l, runtimeProfiles[l]])), starter_code: Object.fromEntries(oa.languages.map(l => [l, ''])),
    reference_solutions: Object.fromEntries(oa.languages.map(l => [l, ''])), limits: { time_ms: 2000, memory_mb: 512, output_kb: 64 },
    comparison: 'trim_trailing_whitespace', tests: Array.from({length:16},(_,i)=>testCase(`test${i+1}`,i<2?'sample':'hidden',contract)) };
  if (kind === 'sql') value.sql = { engine: oa.sql_engine, engine_version: sqlProfiles[oa.sql_engine] || '', schema_sql: '', reference_query: '',
    ordered: false, numeric_tolerance: 0, time_ms: 2000, datasets: ['sample', 'hidden'].map((visibility, i) => ({
      id: `dataset${i + 1}`, visibility, seed_sql: '', columns: ['value'], expected_rows: '[[0]]', weight: 1, explanation: '',
    })) };
  return value;
}

export function editQuestion(content) {
  const value = structuredClone(content);
  value.topics = content.topics.join(', ');
  if (value.coding?.contract === 'function') value.coding.tests = value.coding.tests.map(t => ({ ...t,
    input: JSON.stringify(t.input, null, 2), expected: JSON.stringify(t.expected, null, 2) }));
  if (value.sql) value.sql.datasets = value.sql.datasets.map(d => ({ ...d, expected_rows: JSON.stringify(d.expected_rows, null, 2) }));
  return value;
}

export function prepareQuestion(editor) {
  const value = structuredClone(editor);
  if(value.coding && (value.coding.tests.length<15||value.coding.tests.length>20))throw new Error('Coding questions need 15-20 testcases before saving.');
  value.topics = value.topics.split(',').map(s => s.trim()).filter(Boolean);
  if (value.coding?.contract === 'function') value.coding.tests = value.coding.tests.map(t => ({ ...t,
    input: JSON.parse(t.input), expected: JSON.parse(t.expected) }));
  if (value.sql) value.sql.datasets = value.sql.datasets.map(d => ({ ...d, expected_rows: JSON.parse(d.expected_rows) }));
  return value;
}

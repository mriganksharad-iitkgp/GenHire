// Real React authoring interactions against offline API fixtures. This does not
// claim browser geometry, Monaco worker execution, AI or cloud execution tests.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';

const cwd = process.cwd(), backend = path.resolve(cwd, '../python-backend');
const python = process.env.GENHIRE_TEST_PYTHON || path.join(backend, process.platform === 'win32' ? 'venv/Scripts/python.exe' : 'venv/bin/python');
const fixture = JSON.parse(execFileSync(python, ['-c', 'import json,sys; sys.path.insert(0,"tests"); from models.job_setup import default_setup; from assessment_test_fixtures import mcq,coding,sql; print(json.dumps(dict(configuration=default_setup(),mcq=mcq(),coding=coding("function"),sql=sql("duckdb"))))'], { cwd: backend, encoding: 'utf8' }));
const tmp = await mkdtemp(path.join(cwd, '.assessment-smoke-'));
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost:3000' });
for (const key of ['window', 'document', 'navigator', 'sessionStorage', 'localStorage', 'HTMLElement', 'Element', 'Node', 'Event', 'MouseEvent', 'CustomEvent'])
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const React = await import('react'), { act } = React;
const { createRoot } = await import('react-dom/client');
let root, compiled, questions = new Map(), revision = 0, ids = [], calls = [], counter = 0, failSave = false, generationEnabled = false, published = 0;
let oa = fixture.configuration.oa;
const clone = value => structuredClone(value);
const newId = () => (++counter).toString(16).padStart(24, '0');
const record = (content, previous) => ({ _id: newId(), question_id: previous?.question_id || newId(), revision: (previous?.revision || 0) + 1,
  content: clone(content), validation: null, review: null, source: 'manual' });
globalThis.fetch = async (url, options = {}) => {
  const pathname = new URL(url, 'http://localhost').pathname;
  const body = options.body ? JSON.parse(options.body) : null;
  calls.push({ pathname, options, body });
  let payload, status = 200;
  if (pathname.endsWith('/content') && options.method === 'PUT') {
    assert.equal(body.expected_revision, revision); revision++; ids = body.question_version_ids;
    payload = { workspace: { revision, question_version_ids: ids } };
  } else if (pathname.endsWith('/content')) payload = { revision, question_version_ids: ids, questions: ids.map(id => clone(questions.get(id))),
    blueprint: { configuration: oa }, validator: { available: false, reason: 'Live execution validation is pending.' }, generation: { enabled: generationEnabled } };
  else if (pathname.endsWith('/question-bank')) payload = { items: [...questions.values()].map(q => ({ ...q, content: { title: q.content.title, type: q.content.type } })), next_cursor: null };
  else if (pathname.endsWith('/question-bank/versions') && options.method === 'POST') {
    if (failSave) { payload = { error: 'Simulated version save failure' }; status = 503; }
    else { const q = record(body.content, questions.get(body.previous_version_id)); questions.set(q._id, q); payload = { question: clone(q) }; }
  } else if (pathname.endsWith('/validate')) {
    const id = pathname.split('/').at(-2), q = questions.get(id);
    q.validation = { _id: newId(), passed: true, evidence: { note: 'Structural checks only. Independently review correctness.' } };
    payload = { validation: q.validation };
  } else if (pathname.endsWith('/review')) {
    const id = pathname.split('/').at(-2), q = questions.get(id);
    q.review = { _id: newId(), decision: body.decision, reason: body.reason }; payload = { review: q.review };
  } else if (pathname.includes('/question-bank/versions/')) payload = { question: clone(questions.get(pathname.split('/').at(-1))) };
  else if (pathname.endsWith('/publish')) { assert.equal(body.approved, true); published++; payload = { version: { _id: newId(), state: 'published' } }; }
  else if (pathname.endsWith('/generation-quotes')) payload = { quote: { _id: newId(), total_to_reserve: 30, setup_hold_credits: 30, regeneration_credits: 0, expires_at: new Date(Date.now() + 600000).toISOString() } };
  else if (pathname.endsWith('/assessment-generation-jobs')) payload = { job: { id: 'generation-test', state: 'queued', question_version_ids: [] } };
  else if (pathname.endsWith('/assessment-generation-jobs/generation-test')) {
    const q = [...questions.values()][0]; payload = { job: { id: 'generation-test', state: 'completed', question_version_ids: [q._id] } };
  } else if (pathname.endsWith('/release-setup-hold')) payload = { job: { id: null, state: 'completed', question_version_ids: [] } };
  else throw new Error('Unexpected fixture request: ' + pathname);
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } });
};
const tick = async (ms = 30) => act(async () => { await new Promise(resolve => setTimeout(resolve, ms)); });
const button = text => [...document.querySelectorAll('button')].find(n => n.textContent.trim() === text);
const field = label => [...document.querySelectorAll('label')].find(n => n.textContent.startsWith(label))?.querySelector('input,select,textarea') || document.querySelector(`[aria-label="${label}"]`);
async function click(node) { assert.ok(node, 'Expected control'); await act(async () => node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))); await tick(); }
async function input(node, value) {
  assert.ok(node, 'Expected field');
  await act(async () => {
    const proto = node.tagName === 'SELECT' ? dom.window.HTMLSelectElement.prototype : node.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(node, value);
    node.dispatchEvent(new Event(node.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  }); await tick();
}
async function mount() {
  if (root) await act(async () => root.unmount());
  root = createRoot(document.getElementById('root'));
  sessionStorage.setItem('companyxyz-token', 'fixture-token');
  await act(async () => root.render(React.createElement(compiled.Panel, { blueprintId: 'fixture-blueprint' })));
  await tick();
}
try {
  const result = await build({ stdin: { contents: `export {default as Panel} from ${JSON.stringify(path.join(cwd, 'src/features/recruiter/components/AssessmentAuthoringPanel.jsx'))};`, resolveDir: cwd, loader: 'jsx' },
    outfile: path.join(tmp, 'bundle.mjs'), bundle: true, write: false, platform: 'node', format: 'esm', packages: 'external',
    alias: { shared: path.join(cwd, 'src/shared') }, loader: { '.js': 'jsx' }, define: { 'process.env': JSON.stringify({ NODE_ENV: 'test', REACT_APP_API_URL: 'http://localhost:5000' }) } });
  await writeFile(path.join(tmp, 'bundle.mjs'), result.outputFiles.find(f => f.path.endsWith('.mjs')).text);
  compiled = await import(pathToFileURL(path.join(tmp, 'bundle.mjs')).href);
  oa = { ...fixture.configuration.oa, source: 'hybrid', sections: [{ type: 'mcq', count: 1, marks: [1], weight: 100 }] };
  await mount(); await click(button('Add MCQ question'));
  await input(field('Question title'), 'Even number'); await input(field('Problem statement'), 'Choose an even number.');
  await input(field('Private answer explanation'), 'Two is divisible by two.');
  await input(field('Option 1'), '2'); await input(field('Option 2'), '3'); await click(field('Correct option 1'));
  await input(field('Difficulty'), 'easy'); await click(button('Save private question version'));
  const saved = calls.find(c => c.pathname.endsWith('/versions') && c.options.method === 'POST');
  assert.equal(saved.body.content.mcq.correct_option_ids.length, 1);
  assert.equal(saved.body.content.explanation, 'Two is divisible by two.');
  assert.equal(saved.options.headers.Authorization, 'Bearer fixture-token');
  await click(button('Validate saved question'));
  assert.ok(document.body.textContent.includes('Independently review correctness'));
  assert.equal(button('Approve saved question').disabled, true);
  await input(field('Review rationale'), 'Checked the answer and all alternatives.'); await click(field('I checked the statement'));
  await click(button('Approve saved question')); await click(button('Save assessment selection'));
  await click(field('I approve this saved assessment content')); await click(button('Publish reviewed content'));
  assert.equal(published, 1); assert.ok(document.body.textContent.includes('does not activate the OA'));
  console.log('PASS real MCQ editor, stable keys, authenticated save, independent review and content publication sequence');
  await click(button('Add MCQ question')); await input(field('Question title'), 'Retain my unsaved work');
  failSave = true; await click(button('Save private question version'));
  assert.equal(field('Question title').value, 'Retain my unsaved work');
  assert.ok(document.body.textContent.includes('Simulated version save failure')); failSave = false;
  console.log('PASS failed version save retains editor contents');
  questions = new Map(); ids = []; revision = 0;
  fixture.coding.coding.tests=Array.from({length:16},(_,i)=>({...structuredClone(fixture.coding.coding.tests[i%2]),id:`test${i+1}`}));
  const code = record(fixture.coding); questions.set(code._id, code);
  oa = { ...fixture.configuration.oa, coding_contract: 'function' };
  await mount(); await click(button(`Edit ${code.content.title}`));
  await input(field('Test 1 input JSON'), '{"value":17}'); await input(field('Test 1 expected output JSON'), '17');
  const ideButton = button('Open coding IDE'); await click(ideButton);
  assert.ok(button('Use text editor'));
  await click(button('Save private question version'));
  const codeCall = calls.filter(c => c.pathname.endsWith('/versions') && c.body?.content?.type === 'coding').at(-1);
  assert.deepEqual(codeCall.body.content.coding.tests[0].input, { value: 17 });
  assert.equal(codeCall.body.previous_version_id, code._id);
  assert.equal(codeCall.body.content.coding.runtime_versions.java, '21');
  assert.equal(button('Validate saved question').disabled, true);
  console.log('PASS typed function editor, all-language source, IDE fallback and unavailable-executor gate');
  questions = new Map(); ids = []; revision = 0;
  const sql = record(fixture.sql); questions.set(sql._id, sql);
  oa = { ...fixture.configuration.oa, sql_engine: 'duckdb' };
  await mount(); await click(button(`Edit ${sql.content.title}`));
  await input(field('Dataset 1 expected rows JSON'), '[[3],[4]]'); await click(button('Save private question version'));
  const sqlCall = calls.filter(c => c.pathname.endsWith('/versions') && c.body?.content?.type === 'sql').at(-1);
  assert.equal(sqlCall.body.content.sql.engine_version, 'duckdb-1.5');
  assert.deepEqual(sqlCall.body.content.sql.datasets[0].expected_rows, [[3], [4]]);
  assert.ok(field('Private reference query'));
  console.log('PASS MySQL editor keeps private query, separate datasets and parsed result rows');
  questions = new Map(); ids = []; revision = 0; generationEnabled = true;
  const generated = record(fixture.mcq); questions.set(generated._id, generated);
  oa = { ...fixture.configuration.oa, source: 'hybrid', sections: [{ type: 'mcq', count: 1, marks: [1], weight: 100 }] };
  await mount(); await click(button('Preview generation credits'));
  assert.ok(document.body.textContent.includes('Reserve now: 30 credits'));
  assert.equal(button('Start quoted generation').disabled, true);
  await click(field('I approve this credit reservation')); await click(button('Start quoted generation')); await tick(2100);
  assert.ok(document.body.textContent.includes('Generation job: completed'));
  assert.ok(document.body.textContent.includes('Questions selected for this assessment (1)'));
  assert.equal(calls.filter(c => c.pathname.endsWith('/assessment-generation-jobs') && c.options.method === 'POST').length, 1);
  console.log('PASS binding quote approval, durable job progress and generated versions added without auto-publication');
  await click(button('Release unactivated setup hold'));
  assert.ok(calls.some(c => c.pathname.endsWith('/release-setup-hold')));
  console.log('PASS explicit unactivated hold release');
  await click(field('Use a pasted problem'));
  await input(field('Problem link'),'https://example.test/problem');
  assert.equal(button('Preview conversion credits').disabled,true);
  await input(field('Paste problem statement'),'Choose the even number from the supplied options.');
  await input(field('How should testcases'),'use_provided_cases');
  assert.equal(button('Preview conversion credits').disabled,true);
  await input(field('Your sample/testcase guidance'),'Two is even. Three is odd.');
  await click(button('Copy statement to manual question form'));
  assert.equal(field('Problem statement').value,'Choose the even number from the supplied options.');
  await click(button('Preview conversion credits'));
  const conversion=calls.filter(c=>c.pathname.endsWith('/generation-quotes')).at(-1).body;
  assert.equal(conversion.problem_source.reference_url,'https://example.test/problem');
  assert.equal(conversion.problem_source.test_strategy,'use_provided_cases');
  assert.equal(conversion.requests.length,1);
  assert.equal(calls.filter(c=>c.pathname.endsWith('/assessment-generation-jobs')&&c.options.method==='POST').length,1);
  console.log('PASS pasted-problem conversion requires text/cases, prefills the manual form and previews without automatic paid dispatch');

} finally {
  if (root) await act(async () => root.unmount());
  dom.window.close(); await rm(tmp, { recursive: true, force: true });
}

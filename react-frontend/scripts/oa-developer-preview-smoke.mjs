// Offline rendering of the real developer controls + candidate Assessment page.
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
const cwd = process.cwd();
const questions = [
  ...Array.from({ length: 3 }, (_, i) => ({ type: 'coding', title: `Developer coding ${i + 1}`, statement: 'Echo an integer.', marks: 1,
    coding: { contract: 'stdin_stdout', languages: ['python'], runtime_versions: { python: 'python-3.14' }, starter_code: { python: 'print(input())' }, examples: [{ input: '2', expected: '2' }], input_format: 'Integer', output_format: 'Integer', constraints: '32-bit integer' } })),
  ...Array.from({ length: 2 }, (_, i) => ({ type: 'sql', title: `Developer SQL ${i + 1}`, statement: 'List values.', marks: 1, sql: { engine: 'sqlite', engine_version: 'sqlite-3', schema_sql: 'CREATE TABLE t(n INT);', examples: [] } })),
  ...Array.from({ length: 20 }, (_, i) => ({ type: 'mcq', title: `Developer MCQ ${i + 1}`, statement: 'Which number is even?', marks: 1, mcq: { selection: 'single', options: [{ id: 'even', text: '2' }, { id: 'odd', text: '3' }] } })),
];
const tmp = await mkdtemp(path.join(cwd, '.oa-developer-smoke-'));
const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:3000/dev/oa#token=synthetic-local-token&port=5011' });
for (const key of ['window', 'document', 'navigator', 'sessionStorage', 'HTMLElement', 'Element', 'Node', 'Event', 'MouseEvent', 'CustomEvent'])
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { default: React, act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { MemoryRouter } = await import('react-router-dom');
let root, sequence = 1, calls = [], status = { invitation_id: 'dev-1', attempt_id: 'attempt-1', engine: 'sqlite', contract: 'stdin_stdout', state: 'editable', tasks: [], provider_usage: [] };
globalThis.fetch = async (url, options = {}) => {
  const parsed = new URL(url), body = options.body ? JSON.parse(options.body) : null;
  assert.equal(parsed.hostname, '127.0.0.1'); assert.equal(options.credentials, 'omit');
  assert.equal(options.headers['X-GenHire-Dev-Token'], 'synthetic-local-token');
  calls.push({ path: parsed.pathname, body }); let value;
  if (parsed.pathname === '/dev/reset') {
    sequence++; status = { ...status, invitation_id: `dev-${sequence}`, attempt_id: `attempt-${sequence}`, ...body,
      state: body.submit ? 'complete' : 'editable', report: body.submit ? { score: body.scenario === 'wrong' ? 0 : 100, sections: [] } : null };
    value = status;
  } else if (parsed.pathname === '/dev/status') value = status;
  else if (parsed.pathname.startsWith('/api/assessment-invitations/')) value = { state: 'accepted', security_required: false, pool: 'practice', attempt_id: status.attempt_id };
  else if (parsed.pathname.startsWith('/api/assessment-attempts/')) value = { attempt_id: status.attempt_id, state: 'in_progress', revision: 1, server_now: new Date().toISOString(), deadline: new Date(Date.now() + 86400000).toISOString(), timer_mode: 'shared', sections: [], questions: questions.map((q, i) => ({ ...q, id: `question-${i}` })), answers: {} };
  else throw new Error('Unexpected offline preview request');
  return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
};
const tick = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 40)); });
const button = text => [...document.querySelectorAll('button')].find(node => node.textContent.trim() === text);
const click = async text => { const node = button(text); assert.ok(node); assert.equal(node.disabled, false); await act(async () => node.dispatchEvent(new MouseEvent('click', { bubbles: true }))); await tick(); };
try {
  const output = await build({ entryPoints: ['src/features/assessment/dev/DeveloperAssessmentPreview.jsx'], outfile: path.join(tmp, 'bundle.mjs'),
    bundle: true, write: false, platform: 'node', format: 'esm', packages: 'external', alias: { shared: path.join(cwd, 'src/shared') }, loader: { '.js': 'jsx' }, define: { 'process.env': JSON.stringify({ NODE_ENV: 'test' }) } });
  await writeFile(path.join(tmp, 'bundle.mjs'), output.outputFiles.find(file => file.path.endsWith('.mjs')).text);
  const Page = (await import(pathToFileURL(path.join(tmp, 'bundle.mjs')).href)).default;
  root = createRoot(document.getElementById('root'));
  await act(async () => root.render(React.createElement(MemoryRouter, null, React.createElement(Page)))); await tick(); await tick();
  assert.ok(document.body.textContent.includes('Before you begin'));
  await click('Enter developer workspace');
  assert.equal(document.querySelectorAll('[aria-label^="Go to question"]').length, 25);
  assert.equal(document.querySelectorAll('[id^="oa-question-"]').length, 1);
  assert.equal(document.querySelector('[role="timer"]'), null);
  assert.ok(button('Test final submission')); assert.ok(button('Run public example'));
  await act(async () => document.querySelector('[aria-label="Use dark theme"]').click());
  assert.ok(document.querySelector('[aria-label="Use light theme"]'));
  const splitter = document.querySelector('[aria-label="Problem panel width"]');
  await act(async () => splitter.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })));
  assert.equal(splitter.getAttribute('aria-valuenow'), '45');
  await act(async () => document.querySelector('[aria-label="Focus editor"]').click());
  assert.ok(document.querySelector('[aria-label="Restore split layout"]'));
  await act(async () => document.querySelector('[aria-label="Restore split layout"]').click());
  await act(async () => document.querySelector('[aria-label="Mark question for review"]').click());
  assert.equal(document.querySelector('[aria-label="Mark question for review"]').getAttribute('aria-pressed'), 'true');
  await act(async () => document.querySelector('[aria-label="Go to question 6: Developer MCQ 1"]').click());
  assert.equal(document.querySelectorAll('input[type="radio"]').length, 2);
  assert.equal(document.querySelector('[aria-label="Coding workspace"]'), null);
  await act(async () => document.querySelector('[aria-label="Go to question 4: Developer SQL 1"]').click());
  await click('Schema');
  assert.ok(document.querySelector('[aria-label="Database schema"]').textContent.includes('CREATE TABLE'));
  assert.equal(sessionStorage.getItem('companyxyz-token'), null);
  console.log('PASS local preview renders the real 25-question workspace without login, countdown or token mutation');
  console.log('PASS theme, keyboard resizing, editor focus, review marking, MCQ navigation and SQL schema controls');
  await click('Check correct submission');
  assert.ok(document.body.textContent.includes('Actual graded score: 100%'));
  assert.deepEqual(calls.find(call => call.path === '/dev/reset').body, { engine: 'sqlite', contract: 'stdin_stdout', scenario: 'correct', submit: true });
  await click('Check wrong submission'); assert.ok(document.body.textContent.includes('Actual graded score: 0%'));
  await click('Load editable preview'); assert.equal(document.querySelector('[aria-label="Developer grading result"]'), null);
  console.log('PASS one-click correct/wrong checks and reset use only the authenticated loopback harness');
} finally {
  if (root) await act(async () => root.unmount()); dom.window.close(); await rm(tmp, { recursive: true, force: true });
}

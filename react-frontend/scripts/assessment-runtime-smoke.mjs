// Real React rendering with offline HTTP fixtures; no vendor, browser or wallet calls.
import assert from 'node:assert/strict';
import { assertNamedControls } from './oa-accessibility.mjs';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
const cwd = process.cwd(), tmp = await mkdtemp(path.join(cwd, '.oa-runtime-smoke-'));
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost:3000' });
for (const key of ['window', 'document', 'navigator', 'sessionStorage', 'HTMLElement', 'Element', 'Node', 'Event', 'MouseEvent', 'CustomEvent'])
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
window.confirm = () => true;
const { default: React, act } = await import('react');
const { createRoot } = await import('react-dom/client');
const { MemoryRouter, Routes, Route } = await import('react-router-dom');
let root, calls = [], accepted = false, failSave = false, failLoad = false, holdSave = null, releaseSave, server;
const questions = [
  { id: 'q1', type: 'mcq', title: 'Select an even number', statement: 'Which is even?', marks: 1, mcq: { selection: 'single', options: [{ id: 'a', text: '2' }, { id: 'b', text: '3' }] } },
  { id: 'q2', type: 'coding', title: 'Echo stdin', statement: 'Echo your input.', marks: 2, coding: { contract: 'stdin_stdout', signature: null,
    input_format: 'A string', output_format: 'The string', constraints: '100 characters', languages: ['python', 'javascript'], runtime_versions: { python: '3.12', javascript: '22' },
    starter_code: { python: 'print(input())', javascript: 'console.log("hi")' }, examples: [{ input: 'hi', expected: 'hi', explanation: 'Echo' }] } },
  { id: 'q3', type: 'sql', title: 'List rows', statement: 'Select all rows.', marks: 2, sql: { engine: 'postgresql', engine_version: '17', schema_sql: 'CREATE TABLE t (n INT);', examples: [{ seed_sql: 'INSERT INTO t VALUES (1)', columns: ['n'], expected_rows: [[1]] }] } }
];
function reset() {
  calls = []; accepted = false; failSave = false; sessionStorage.clear();
  server = { attempt_id: 'attempt-one', state: 'in_progress', revision: 0, server_now: new Date().toISOString(), deadline: new Date(Date.now()+300000).toISOString(),
    timer_mode: 'shared', sections: [], questions: structuredClone(questions), answers: {} };
}
globalThis.fetch = async (url, options = {}) => {
  const pathname = new URL(url, 'http://localhost').pathname, body = options.body ? JSON.parse(options.body) : null;
  calls.push({ pathname, body }); let payload, status = 200;
  if (pathname === '/api/assessment-invitations/invite-one') payload = { invitation_id: 'invite-one', state: accepted ? 'accepted' : 'invited', attempt_id: accepted ? 'attempt-one' : null,
    runtime_ready: true, opens_at: new Date(Date.now()-10000).toISOString(), start_closes_at: new Date(Date.now()+60000).toISOString(), duration_minutes: 5 };
  else if (pathname.endsWith('/start')) { accepted = true; assert.equal(body.consent_version, 'oa-v1'); payload = { attempt_id: 'attempt-one', access_token: 'extended-token' }; }
  else if (pathname.endsWith('/answers')) {
    if (holdSave) await holdSave;
    if (failSave) { status = 503; payload = { error: 'Simulated offline save' }; }
    else { Object.assign(server.answers, body.answers); server.revision++; payload = { revision: server.revision }; }
  } else if (pathname.endsWith('/submit')) {
    assert.equal(body.expected_revision, server.revision); server.state = 'submitted'; server.revision++; payload = { state: 'submitted', revision: server.revision };
  } else if (pathname.endsWith('/runs')) payload = { run_id: 'run-one' };
  else if (pathname.endsWith('/runs/run-one')) payload = { run_id: 'run-one', state: 'complete', result: { status: 'ok', stdout: 'hi' } };
  else if (pathname === '/api/assessment-attempts/attempt-one') {if(failLoad){status=503;payload={error:'Simulated reload failure'};}else payload = server;}
  else throw new Error('Unexpected fixture request '+pathname);
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } });
};
const tick = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 30)); });
const button = text => [...document.querySelectorAll('button')].find(n => n.textContent.trim() === text);
async function click(node) { assert.ok(node); assert.equal(node.disabled, false); await act(async () => node.dispatchEvent(new MouseEvent('click', { bubbles: true }))); await tick(); }
let Page;
async function mount() {
  if (root) await act(async () => root.unmount());
  root = createRoot(document.getElementById('root'));
  await act(async () => root.render(React.createElement(MemoryRouter, { initialEntries: ['/assessments/invite-one'] },
    React.createElement(Routes, null, React.createElement(Route, { path: '/assessments/:invitationId', element: React.createElement(Page) })))));
  await tick();
}
try {
  const output = await build({ entryPoints: ['src/features/assessment/pages/Assessment.jsx'], outfile: path.join(tmp, 'bundle.mjs'),
    bundle: true, write: false, platform: 'node', format: 'esm', packages: 'external', alias: { shared: path.join(cwd, 'src/shared') },
    loader: { '.js': 'jsx' }, define: { 'process.env': JSON.stringify({ NODE_ENV: 'test' }) } });
  await writeFile(path.join(tmp, 'bundle.mjs'), output.outputFiles.find(f => f.path.endsWith('.mjs')).text);
  Page = (await import(pathToFileURL(path.join(tmp, 'bundle.mjs')).href)).default;
  reset(); await mount(); assertNamedControls(document);
  assert.equal(button('Start assessment').disabled, true);
  await click(document.querySelector('input[type=checkbox]')); await click(button('Start assessment'));
  assert.equal(sessionStorage.getItem('companyxyz-token'), 'extended-token');
  await click(document.querySelector('[aria-label="Go to question 3: List rows"]'));
  assert.ok(document.querySelector('[aria-label="Database schema"]').textContent.includes('CREATE TABLE t (n INT);'));
  await click(document.querySelector('[aria-label="Go to question 2: Echo stdin"]'));
  assert.ok(document.querySelector('textarea[aria-label="Answer for Echo stdin"]'));
  assertNamedControls(document);
  await click(document.querySelector('[aria-label="Go to question 2: Echo stdin"]'));assert.equal(document.activeElement.textContent,'Echo stdin');
  await click(document.querySelector('[aria-label="Go to question 1: Select an even number"]'));
  console.log('PASS preflight requires consent, starts once and renders MCQ/coding/SQL with accessible editor fallback');

  await click(document.querySelector('input[type=radio]')); failSave = true;
  await click(button('Retry / save answers'));
  assert.ok(document.body.textContent.includes('local draft is retained'));
  assert.ok(sessionStorage.getItem('oa-draft:attempt-one'));
  const first = calls.find(c => c.pathname.endsWith('/answers'));
  failSave = false; await click(button('Retry / save answers'));
  const retries = calls.filter(c => c.pathname.endsWith('/answers'));
  assert.deepEqual(retries[1].body, first.body);
  assert.ok(document.body.textContent.includes('All changes acknowledged by server'));
  console.log('PASS failed save retains local work and retries the same revision and operation key');

  await click(document.querySelector('[aria-label="Go to question 2: Echo stdin"]'));
  await click(button('Run custom input'));
  assert.equal(calls.find(c => c.pathname.endsWith('/runs')).body.custom_input, '');
  assert.equal(calls.find(c => c.pathname.endsWith('/runs')).body.answer.source, 'print(input())');
  console.log('PASS empty custom stdin is sent explicitly and public runs remain separate from final submission');

  await click(document.querySelector('[aria-label="Go to question 1: Select an even number"]'));
  await click(document.querySelectorAll('input[type=radio]')[1]);
  await click(button('Submit and lock assessment'));
  assert.ok(button('Keep working'));
  assert.equal(calls.filter(c=>c.pathname.endsWith('/submit')).length,0);
  await click(button('Save and submit'));
  const lastSave = calls.findLastIndex(c => c.pathname.endsWith('/answers')), submit = calls.findIndex(c => c.pathname.endsWith('/submit'));
  assert.ok(lastSave < submit); assert.ok(document.body.textContent.includes('Assessment submitted'));
  assert.equal(sessionStorage.getItem('oa-draft:attempt-one'), null);
  console.log('PASS submission flushes and acknowledges pending edits before locking the attempt');

  const starts = calls.filter(c => c.pathname.endsWith('/start')).length;
  await mount();
  assert.ok(document.body.textContent.includes('Assessment submitted'));
  assert.equal(calls.filter(c => c.pathname.endsWith('/start')).length, starts);
  console.log('PASS accepted attempt resumes by scoped server ID without starting or resetting its deadline');

  reset(); accepted = true;
  sessionStorage.setItem('oa-draft:attempt-one', JSON.stringify({ answers: { q1: { option_ids: ['b'] } }, pending: {
    expected_revision: 0, operation_key: 'recovered-stable-key', answers: { q1: { option_ids: ['b'] } }
  } }));
  await mount();
  assert.equal(document.querySelectorAll('input[type=radio]')[1].checked, true);
  assert.ok(document.body.textContent.includes('Unsaved local changes'));
  await click(button('Retry / save answers'));
  assert.equal(calls.find(c => c.pathname.endsWith('/answers')).body.operation_key, 'recovered-stable-key');
  console.log('PASS tab refresh recovers an unsent draft and the original pending save key');
  await click(document.querySelectorAll('input[type=radio]')[0]);failLoad=true;
  await click(button('Reload server answers'));assert.ok(button('Keep local answers'));
  await click(button('Reload saved answers'));
  assert.ok(document.body.textContent.includes('Your local answers are retained'));
  assert.ok(document.body.textContent.includes('Unsaved local changes'));
  assert.equal(document.querySelectorAll('input[type=radio]')[0].checked,true);
  assert.ok(sessionStorage.getItem('oa-draft:attempt-one'));failLoad=false;
  console.log('PASS failed server reload preserves unsaved answers and recovery storage');


  await click(document.querySelectorAll('input[type=radio]')[0]);
  holdSave = new Promise(resolve => { releaseSave = resolve; });
  await click(button('Retry / save answers'));
  await click(document.querySelector('[aria-label="Go to question 2: Echo stdin"]'));
  await act(async () => {
    const editor = document.querySelector('textarea[aria-label="Answer for Echo stdin"]');
    Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, 'value').set.call(editor, 'print("edited during save")');
    editor.dispatchEvent(new Event('input', { bubbles: true })); editor.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await act(async () => { holdSave = null; releaseSave(); }); await tick();
  assert.ok(document.body.textContent.includes('Unsaved local changes'));
  await click(button('Retry / save answers'));
  assert.equal(server.answers.q2.source, 'print("edited during save")');
  console.log('PASS editing another question during an in-flight save retains the new unsaved answer');

  server.state = 'completed'; await mount();
  assert.ok(document.body.textContent.includes('Check your application for any recruiter-released result'));
  assert.equal(document.body.textContent.includes('Objective score'), false);
  console.log('PASS completed recruitment evaluation stays withheld until recruiter release');
  server.state = 'unavailable'; await mount();
  assert.ok(document.body.textContent.includes('No final score has been assigned'));
  console.log('PASS unavailable evaluation is described as technical review without an invented score');
} finally {
  if (root) await act(async () => root.unmount());
  dom.window.close();
  await rm(tmp, { recursive: true, force: true });
}

// Rendered local fixture checks; no Electron/device/storage attestation is made.
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
const cwd = process.cwd(), tmp = await mkdtemp(path.join(cwd, '.oa-integrity-smoke-'));
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost:3000' });
for (const key of ['window', 'document', 'navigator', 'sessionStorage', 'localStorage', 'HTMLElement', 'Element', 'Node', 'Event', 'MouseEvent', 'CustomEvent'])
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { default: React, act } = await import('react'); const { createRoot } = await import('react-dom/client');
const { MemoryRouter } = await import('react-router-dom');
let root, calls = [], active = false, clipboardBlocked = 0;
const policy = { version: 'oa-integrity-v1', consent_version: 'oa-integrity-v1', tier: 'basic', mode: 'kiosk', raw_retention_days: 30, summary_retention_days: 180, clipboard: 'internal_editor', extra_minutes: 15 };
window.electronAPI = { enableKiosk: () => { active = true; }, getAssessmentRuntime: async () => ({ release_id: '1.3.0', kiosk_active: active }), disableKiosk: () => {}, quitApp: () => {}, onAppSwitched: () => {} };
globalThis.fetch = async (url, options = {}) => {
  const pathname = new URL(url, 'http://localhost').pathname, body = options.body ? JSON.parse(options.body) : null;
  calls.push({ pathname, body, headers: options.headers }); let value;
  if (pathname.endsWith('/redeem')) {
    assert.equal(body.launch_code, 'one-time-code-fixture'); assert.equal(body.runtime_info.kiosk_active, true);
    assert.equal(options.headers.Authorization, undefined); value = { access_token: 'scoped-token', policy };
  } else {
    assert.ok(['OA scoped-token', 'OA renewed-scoped-token'].includes(options.headers.Authorization));
    if (pathname.endsWith('/preflight')) { assert.equal(body.consent_version, 'oa-integrity-v1'); value = { ready: true }; }
    else if (pathname.endsWith('/start')) value = { attempt_id: 'attempt-one', access_token: 'renewed-scoped-token' };
    else if (pathname.endsWith('/assessment-attempts/attempt-one')) value = { attempt_id: 'attempt-one', state: 'in_progress', revision: 0, server_now: new Date().toISOString(), deadline: new Date(Date.now()+600000).toISOString(), timer_mode: 'shared', sections: [], questions: [], answers: {} };
    else if (pathname.endsWith('/assessment-invitations/invite-one')) value = { state: 'invited', security_required: true, runtime_ready: true, integrity_policy: policy, duration_minutes: 5, opens_at: new Date().toISOString(), start_closes_at: new Date(Date.now()+60000).toISOString() };
    else throw new Error('Unexpected request '+pathname);
  }
  return new Response(JSON.stringify(value), { status: 200 });
};
const tick = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 25)); });
const button = text => [...document.querySelectorAll('button')].find(node => node.textContent === text);
async function click(node) { assert.ok(node); assert.equal(node.disabled, false); await act(async () => node.dispatchEvent(new MouseEvent('click', { bubbles: true }))); await tick(); }
try {
  const out = await build({ stdin: { contents: `export {default as Scoped} from './src/features/assessment/components/ScopedAssessment.jsx'; export {default as Editor} from './src/shared/components/ui/CodeEditor.jsx';`, resolveDir: cwd, loader: 'jsx' },
    outfile: path.join(tmp, 'bundle.mjs'), bundle: true, write: false, platform: 'node', format: 'esm', packages: 'external', alias: { shared: path.join(cwd, 'src/shared') }, loader: { '.js': 'jsx' }, define: { 'process.env': JSON.stringify({ NODE_ENV: 'test' }) } });
  await writeFile(path.join(tmp, 'bundle.mjs'), out.outputFiles.find(f => f.path.endsWith('.mjs')).text);
  const compiled = await import(pathToFileURL(path.join(tmp, 'bundle.mjs')).href);
  sessionStorage.setItem('companyxyz-token', 'dashboard-account-token'); root = createRoot(document.getElementById('root'));
  const launch = { mode: 'oa', launchCode: 'one-time-code-fixture', invitationId: 'invite-one', apiUrl: 'http://localhost:5000', webOrigin: 'http://localhost:3000', returnToExistingTab: true };
  await act(async () => root.render(React.createElement(MemoryRouter, null, React.createElement(compiled.Scoped, { launch })))); await tick();
  assert.equal(button('Confirm devices and continue').disabled, true);
  assert.equal(calls.some(call => call.pathname.endsWith('/start')), false);
  assert.ok(document.body.textContent.includes('not continuous audio or screen recordings'));
  assert.ok(document.body.textContent.includes('Approved extra time: 15 minutes'));
  console.log('PASS scoped launch redeems only an opaque code and discloses monitoring, retention and extra time before start');
  await click(document.querySelector('input[type=checkbox]')); await click(button('Confirm devices and continue'));
  assert.equal(calls.some(call => call.pathname.endsWith('/preflight')), true);
  assert.equal(calls.some(call => call.pathname.endsWith('/start')), false);
  console.log('PASS explicit monitoring consent and device preflight do not start the assessment timer');
  await click(document.querySelector('input[type=checkbox]')); await click(button('Start assessment'));
  assert.equal(sessionStorage.getItem('companyxyz-token'), 'dashboard-account-token');
  assert.ok(JSON.parse(sessionStorage.getItem('genhire:oa:invite-one')).access_token === 'renewed-scoped-token');
  assert.ok(document.body.textContent.includes('All changes acknowledged by server'));
  console.log('PASS accepted OA uses a scoped token while the launching dashboard account session remains unchanged');
  await act(async () => root.unmount()); root = createRoot(document.getElementById('root'));
  const clipboard = { current: '' };
  window.addEventListener('oa:paste-blocked', () => clipboardBlocked++);
  await act(async () => root.render(React.createElement(compiled.Editor, { label: 'Fixture code', value: 'answer', onChange: () => {}, clipboardRef: clipboard })));
  const editor = document.querySelector('textarea'); editor.setSelectionRange(0, 6);
  const copy = new Event('copy', { bubbles: true, cancelable: true }); Object.defineProperty(copy, 'clipboardData', { value: { setData: () => {} } });
  await act(async () => editor.dispatchEvent(copy)); assert.equal(clipboard.current, 'answer');
  const paste = value => { const event = new Event('paste', { bubbles: true, cancelable: true }); Object.defineProperty(event, 'clipboardData', { value: { getData: () => value } }); editor.dispatchEvent(event); return event.defaultPrevented; };
  assert.equal(paste('external secret text'), true); assert.equal(clipboardBlocked, 1);
  assert.equal(paste('answer'), false);
  console.log('PASS editor allows internal copy/paste and reports blocked external paste without collecting its contents');
} finally { if (root) await act(async () => root.unmount()); dom.window.close(); await rm(tmp, { recursive: true, force: true }); }

import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
const cwd = process.cwd(), tmp = await mkdtemp(path.join(cwd, '.oa-evaluation-smoke-'));
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost:3000' });
for (const key of ['window', 'document', 'navigator', 'sessionStorage', 'HTMLElement', 'Element', 'Node', 'Event', 'MouseEvent', 'CustomEvent'])
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { default: React, act } = await import('react');
const { createRoot } = await import('react-dom/client');
let root, payload = { state: 'waiting', report: null }, fail = false, requests = 0;
globalThis.fetch = async (url, options) => {
  assert.ok(url.endsWith('/assessment-attempts/attempt-fixture/evaluation'));
  assert.equal(options.headers.Authorization, 'Bearer fixture-token'); requests++;
  return new Response(JSON.stringify(fail ? { error: 'Simulated evaluation outage' } : payload), { status: fail ? 503 : 200 });
};
const tick = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
async function click() {
  await act(async () => document.querySelector('button').dispatchEvent(new MouseEvent('click', { bubbles: true })));
  await tick();
}
try {
  const out = await build({ entryPoints: ['src/features/recruiter/components/AssessmentEvaluationReport.jsx'], outfile: path.join(tmp, 'bundle.mjs'),
    bundle: true, write: false, platform: 'node', format: 'esm', packages: 'external', alias: { shared: path.join(cwd, 'src/shared') },
    loader: { '.js': 'jsx' }, define: { 'process.env': JSON.stringify({ NODE_ENV: 'test' }) } });
  await writeFile(path.join(tmp, 'bundle.mjs'), out.outputFiles.find(f => f.path.endsWith('.mjs')).text);
  const Page = (await import(pathToFileURL(path.join(tmp, 'bundle.mjs')).href)).default;
  sessionStorage.setItem('companyxyz-token', 'fixture-token'); root = createRoot(document.getElementById('root'));
  await act(async () => root.render(React.createElement(Page, { attemptId: 'attempt-fixture' })));
  assert.equal(requests, 0); await click();
  assert.ok(document.body.textContent.includes('waiting')); assert.equal(document.body.textContent.includes('Objective score'), false);
  console.log('PASS recruiter report loads through authenticated API and pending work has no fabricated score');
  payload = { state: 'complete', report: { score: 0, recommendation: 'not_cleared', released: false, billing_action: 'capture', sections: [{ type: 'mcq', earned: 0, possible: 20, weight: 100 }] } };
  await click(); assert.ok(document.body.textContent.includes('Objective score: 0%'));
  assert.ok(document.body.textContent.includes('withheld until recruiter release'));
  assert.ok(document.body.textContent.includes('require recruiter action'));
  console.log('PASS zero section/overall marks remain visible and qualification does not trigger company advancement');
  fail = true; await click(); assert.ok(document.body.textContent.includes('Simulated evaluation outage'));
  assert.ok(document.body.textContent.includes('Objective score: 0%'));
  fail = false; payload = { state: 'unavailable', report: { ...payload.report, score: null, billing_action: 'release' } };
  await click(); assert.ok(document.body.textContent.includes('Unavailable; no final score assigned'));
  assert.ok(document.body.textContent.includes('reservation returned'));
  console.log('PASS refresh failures retain the prior report and unavailable execution is distinguished from zero marks');
} finally {
  if (root) await act(async () => root.unmount()); dom.window.close(); await rm(tmp, { recursive: true, force: true });
}

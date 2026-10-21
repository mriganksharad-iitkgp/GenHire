import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
const cwd = process.cwd(), tmp = await mkdtemp(path.join(cwd, '.company-hiring-smoke-'));
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost:3000' });
for (const key of ['window', 'document', 'navigator', 'sessionStorage', 'HTMLElement', 'Element', 'Node', 'Event', 'MouseEvent', 'CustomEvent'])
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { default: React, act } = await import('react');
const { createRoot } = await import('react-dom/client');
let root, calls = [], resultReleased = false, hold = true, revision = 7, summaryError = false;
const review = () => ({ enabled: true, objective_recommendation: 'cleared', integrity_hold: hold, released: false, decision: null });
const row = { application_id: 'candidate-fixture', name: 'Fixture Candidate', email: 'candidate@example.test', revision: 7, stage_id: 'oa', label: 'OA evaluated', interview_score: 78, oa_score: 0, oa_recommendation: 'not_cleared', integrity_hold: true, recruiter_decision: 'pending' };
globalThis.fetch = async (url, options = {}) => {
  assert.equal(options.headers.Authorization, 'Bearer fixture-token');
  const body = options.body ? JSON.parse(options.body) : null; calls.push({ url, body });
  let payload;
  if (url.includes('/company-review')) payload = review();
  else if (url.endsWith('/stages')) payload = { workflow: { revision, lifecycle: 'active', current_stage_id: 'oa', workflow_label: 'OA evaluated', stages: [{ stage_id: 'oa', type: 'oa', state: 'completed' }] }, events: [{ revision: 7, action: 'oa_evaluated', occurred_at: '2027-01-01T00:00:00Z', reason: 'Durable evaluation completed.' }], has_more: false };
  else if (url.endsWith('/company-actions')) { assert.equal(body.expected_revision, 7); assert.ok(body.operation_key); revision++; payload = { revision }; }
  else if (url.includes('/company-candidates?')) payload = { rows: [row], funnel: [{ _id: { stage: 'oa', lifecycle: 'active' }, count: 1 }], has_more: false };
  else if (url.endsWith('/bulk-stage-actions')) payload = { outcomes: [{ application_id: row.application_id, ok: false, error: 'Application changed; reload before acting.' }] };
  else if (url.endsWith('/communications/preview')) payload = { preview_id: 'preview-fixture', subject: body.subject, message: body.message, recipients: [row], skipped: [], expires_at: '2027-01-01T00:10:00Z' };
  else if (url.endsWith('/communications')) { assert.equal(body.accepted, true); payload = { batch_id: 'batch-fixture', queued: 1 }; }
  else if (url.endsWith('/communications/batch-fixture')) payload = { messages: [{ _id: 'message-fixture', email: row.email, state: 'delivery_unknown' }] };
  else if (url.endsWith('/company-communications/message-fixture/reconcile')) { assert.equal(body.disposition, 'confirmed_sent'); assert.ok(body.reason.length >= 20); payload = { state: 'sent' }; }
  else if (url.endsWith('/evaluation')) {
    if (summaryError) return new Response(JSON.stringify({ error: 'Simulated report outage' }), { status: 503 });
    payload = resultReleased ? { result_available: true, summary: { score: 0, outcome: 'not_cleared', sections: [{ type: 'mcq', earned: 0, possible: 20, weight: 100 }] } } : { result_available: false, message: 'The recruiter will confirm the result and next step.' };
  } else throw new Error('Unexpected fixture URL '+url);
  return new Response(JSON.stringify(payload), { status: 200 });
};
const tick = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 15)); });
const findButton = text => [...document.querySelectorAll('button')].find(el => el.textContent.includes(text));
const label = text => [...document.querySelectorAll('label')].find(el => el.textContent.startsWith(text)).querySelector('input,textarea,select');
async function click(text) { const el = findButton(text); assert.ok(el, text); assert.equal(el.disabled, false, text); await act(async () => el.dispatchEvent(new MouseEvent('click', { bubbles: true }))); await tick(); }
async function input(el, value) {
  const proto = el.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype;
  await act(async () => { Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value); el.dispatchEvent(new Event('input', { bubbles: true })); });
}
async function render(Page, props) { if (root) await act(async () => root.unmount()); root = createRoot(document.getElementById('root')); await act(async () => root.render(React.createElement(Page, props))); }
try {
  const result = await build({ stdin: { contents: "export {default as Review} from './src/features/recruiter/components/CompanyReviewPanel.jsx'; export {default as Pipeline} from './src/features/recruiter/components/CompanyPipelinePanel.jsx'; export {default as Summary} from './src/features/candidate/components/ReleasedAssessmentSummary.jsx'; export {default as Inspector} from './src/features/admin/components/CompanyDeliveryInspector.jsx'; export {default as Overview} from './src/features/recruiter/components/OverviewMetrics.jsx';", resolveDir: cwd },
    outfile: path.join(tmp, 'bundle.mjs'), bundle: true, write: false, platform: 'node', format: 'esm', packages: 'external', alias: { shared: path.join(cwd, 'src/shared'), features: path.join(cwd, 'src/features') }, loader: { '.js': 'jsx' }, define: { 'process.env': JSON.stringify({ NODE_ENV: 'test' }) } });
  await writeFile(path.join(tmp, 'bundle.mjs'), result.outputFiles.find(file => file.path.endsWith('.mjs')).text);
  const { Review, Pipeline, Summary, Inspector, Overview } = await import(pathToFileURL(path.join(tmp, 'bundle.mjs')).href);
  sessionStorage.setItem('companyxyz-token', 'fixture-token');
  await render(Review, { applicationId: 'candidate-fixture' }); assert.equal(calls.length, 0); await click('Load / refresh');
  assert.ok(document.body.textContent.includes('Durable evaluation completed.')); assert.equal(findButton('Approve OA qualification').disabled, true);
  await input(label('Decision reason'), 'Reviewed candidate results and resolved evidence.'); assert.equal(findButton('Approve OA qualification').disabled, true);
  console.log('PASS company review loads recorded history and blocks qualification while integrity review remains unresolved');
  hold = false; await click('Load / refresh'); await click('Approve OA qualification');
  assert.equal(calls.filter(c => c.url.endsWith('/company-actions'))[0].body.action, 'qualify');
  assert.equal(calls.some(c => c.body?.action === 'release'), false);
  console.log('PASS reasoned qualification uses current revision and does not implicitly release results');
  await render(Pipeline, { jobId: 'job-fixture' }); await click('Load / refresh company candidates');
  assert.ok(document.body.textContent.includes('0%')); assert.ok(document.body.textContent.includes('oa / active: 1'));
  await act(async () => document.querySelector('input[type="checkbox"]').click());
  await input(label('Private decision reason'), 'Company approved this next-stage shortlist.'); await click('Apply selected decision');
  assert.ok(document.body.textContent.includes('Application changed; reload before acting.'));
  console.log('PASS comparison preserves zero marks and bulk decisions show per-candidate conflicts');
  await act(async () => document.querySelector('input[type="checkbox"]').click());
  await input(label('Email subject'), 'Company interview invitation'); await input(label('Email message'), 'Please contact our company to arrange the interview.');
  await click('Preview recipients'); assert.ok(document.body.textContent.includes('Fixture Candidate: candidate@example.test'));
  assert.equal(findButton('Queue approved').disabled, true); assert.equal(calls.filter(c => c.url.endsWith('/communications')).length, 0);
  await act(async () => label('I approve').click()); await click('Queue approved');
  assert.ok(document.body.textContent.includes('Queued does not mean delivered'));
  console.log('PASS email requires exact recipient/content preview and explicit approval before queueing');
  await render(Summary, { attemptId: 'attempt-fixture' }); await click('Check released');
  assert.equal(document.body.textContent.includes('OA score:'), false); resultReleased = true; await click('Check released');
  assert.ok(document.body.textContent.includes('OA score: 0%')); assert.ok(document.body.textContent.includes('mcq: 0/20'));
  console.log('PASS candidate summary stays withheld before release and renders released zero/section marks');
  summaryError = true; await click('Check released'); assert.ok(document.body.textContent.includes('Simulated report outage')); assert.equal(document.body.textContent.includes('OA score:'), false);
  console.log('PASS failed candidate refresh clears the displayed snapshot instead of presenting stale release as current');
  await render(Inspector, { jobId: 'job-fixture' }); await input(label('Batch ID'), 'batch-fixture'); await click('Inspect delivery batch');
  assert.ok(document.body.textContent.includes('delivery_unknown')); assert.equal(findButton('Confirm provider accepted').disabled, true);
  await input(label('Provider evidence'), 'Provider audit record explicitly confirms accepted send 123.'); await click('Confirm provider accepted');
  console.log('PASS admin delivery inspection requires provider evidence and explicit disposition without a resend action');
  await render(Overview, { applications: [{ status: 'rejected' }, { status: 'screening_cleared', workflow_version_id: 'workflow-fixture', workflow: { lifecycle: 'hired', stages: [{ type: 'screening', state: 'completed', outcome: 'cleared' }] } }] });
  const metric = text => [...document.querySelectorAll('p')].find(el => el.textContent === text).previousElementSibling.textContent;
  assert.equal(metric('Interviews Completed'), '1'); assert.equal(metric('Screening Cleared'), '1'); assert.equal(metric('In Company Rounds'), '0'); assert.equal(metric('Hired'), '1');
  console.log('PASS dashboard metrics use recorded screening/lifecycle facts and do not count pre-screening rejection as a completed interview');
} finally { if (root) await act(async () => root.unmount()); dom.window.close(); await rm(tmp, { recursive: true, force: true }); }

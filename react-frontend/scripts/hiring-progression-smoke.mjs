// Offline rendered UI/API-contract checks. No accounts, email or wallets used.
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';

const cwd = process.cwd(), tmp = await mkdtemp(path.join(cwd, '.hiring-smoke-'));
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost:3000' });
for (const key of ['window', 'document', 'navigator', 'sessionStorage', 'localStorage', 'HTMLElement', 'Element', 'Node', 'Event', 'MouseEvent', 'CustomEvent'])
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { default: React, act } = await import('react');
const { createRoot } = await import('react-dom/client');
let root, compiled, calls = [], failActivation = false, failProgress = false, activated = 0;
const setup = { _id: 'setup-one', configuration: { pipeline: { oa_enabled: true } } };
const job = { _id: 'job-one', hiring_setup_version_id: setup._id };
const dates = { screening_opens_at: '2027-01-02T09:00:00Z', screening_closes_at: '2027-01-05T09:00:00Z',
  oa_opens_at: '2027-01-06T09:00:00Z', oa_start_closes_at: '2027-01-07T09:00:00Z', oa_activation: 'manual' };
const makeOverview = () => ({ scheduling_enabled: true, active_version_id: null, active_oa_enabled: false, active_setup_version_id: null,
  published_content: [{ _id: 'content-one', workspace_revision: 1, created_at: '2027-01-01T00:00:00Z' }],
  stage_counts: [], existing_application_count: 3, impact: 'Existing candidates require explicit enrollment.', window_revision: 0 });
let overview = makeOverview();
const makeProgress = state => ({ scheduling_enabled: true, application_id: 'app-one', screening_result_reason: state === 'evaluating' ? 'evaluation_pending' : 'recruiter_decision_required',
  workflow: { workflow_version_id: 'version-one', revision: 3, lifecycle: 'active', current_stage_id: 'screening', workflow_label: 'Screening awaiting review', stages: [
    { stage_id: 'screening', type: 'screening', state, outcome: state === 'evaluating' ? 'pending' : 'review_required', enabled: true },
    { stage_id: 'oa', type: 'oa', state: 'not_ready', outcome: 'pending', enabled: true }] }, schedule: dates, invitation: null });
let progress = makeProgress('completed');
const clone = value => structuredClone(value);
globalThis.fetch = async (url, options = {}) => {
  const pathname = new URL(url, 'http://localhost').pathname, body = options.body ? JSON.parse(options.body) : null;
  calls.push({ pathname, options, body });
  let payload, status = 200;
  if (pathname.endsWith('/hiring-operations')) payload = overview;
  else if (pathname.endsWith('/hiring-activation-quotes')) payload = { quote: { _id: 'quote-one', setup_credits: 30, attempt_credits: 5, expires_at: new Date(Date.now()+600000).toISOString() } };
  else if (pathname.endsWith('/hiring-activations')) {
    if (failActivation) { status = 503; payload = { error: 'Simulated activation failure' }; }
    else { activated++; overview = { ...overview, active_version_id: 'version-one', active_oa_enabled: true, active_setup_version_id: setup._id, active_schedule: dates }; payload = { setup_credits_captured: 30 }; }
  } else if (pathname.endsWith('/hiring-progress')) {
    if (failProgress) { status = 503; payload = { error: 'Progress temporarily unavailable' }; } else payload = progress;
  } else if (pathname.endsWith('/stage-actions')) {
    assert.equal(body.expected_revision, progress.workflow.revision);
    progress.workflow.revision++; progress.workflow.stages[0].outcome = 'cleared'; progress.workflow.workflow_label = 'Screening cleared — awaiting recruiter decision'; payload = progress.workflow;
  } else if (pathname.endsWith('/oa-invitations')) {
    assert.equal(body.expected_revision, progress.workflow.revision);
    progress.workflow.revision++; progress.workflow.stages[1].state = 'invited'; progress.workflow.current_stage_id = 'oa'; progress.workflow.workflow_label = 'Invited to online assessment';
    progress.invitation = { invitation_id: 'invite-one', state: 'invited', opens_at: dates.oa_opens_at, start_closes_at: dates.oa_start_closes_at, duration_minutes: 60, runtime_ready: false };
    payload = { invitation_id: 'invite-one', state: 'invited' };
  } else if (pathname.endsWith('/oa-window')) {
    assert.equal(body.expected_revision, overview.window_revision); overview.window_revision++;
    if (body.opens_at) overview.active_schedule = { ...dates, oa_opens_at: body.opens_at, oa_start_closes_at: body.closes_at };
    else overview.manual_oa_authorized = true;
    payload = { window_revision: overview.window_revision, unstarted_invitations_changed: 1, active_attempts_changed: 0 };
  } else throw new Error('Unexpected fixture request: '+pathname);
  return new Response(JSON.stringify(clone(payload)), { status, headers: { 'Content-Type': 'application/json' } });
};
const tick = () => act(async () => { await new Promise(resolve => setTimeout(resolve, 25)); });
const button = text => [...document.querySelectorAll('button')].find(n => n.textContent.trim() === text);
const field = text => [...document.querySelectorAll('label')].find(n => n.textContent.startsWith(text))?.querySelector('input,select,textarea');
async function click(node) { assert.ok(node); assert.equal(node.disabled, false); await act(async () => node.dispatchEvent(new MouseEvent('click', { bubbles: true }))); await tick(); }
async function input(node, value) {
  assert.ok(node);
  await act(async () => {
    const proto = node.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(node, value);
    node.dispatchEvent(new Event('input', { bubbles: true })); node.dispatchEvent(new Event('change', { bubbles: true }));
  }); await tick();
}
async function mount(Component, props) {
  if (root) await act(async () => root.unmount());
  root = createRoot(document.getElementById('root')); sessionStorage.setItem('companyxyz-token', 'fixture-token');
  await act(async () => root.render(React.createElement(Component, props))); await tick();
}
try {
  const output = await build({ stdin: { contents: `export {default as Activation} from './src/features/recruiter/components/HiringActivationPanel.jsx'; export {default as Actions} from './src/features/recruiter/components/HiringCandidateActions.jsx'; export {default as Notice} from './src/features/candidate/components/HiringProgressNotice.jsx';`, resolveDir: cwd, loader: 'jsx' },
    outfile: path.join(tmp, 'bundle.mjs'), bundle: true, write: false, platform: 'node', format: 'esm', packages: 'external', alias: { shared: path.join(cwd, 'src/shared') },
    loader: { '.js': 'jsx' }, define: { 'process.env': JSON.stringify({ NODE_ENV: 'test', REACT_APP_API_URL: 'http://localhost:5000' }) } });
  await writeFile(path.join(tmp, 'bundle.mjs'), output.outputFiles.find(f => f.path.endsWith('.mjs')).text);
  compiled = await import(pathToFileURL(path.join(tmp, 'bundle.mjs')).href);
  await mount(compiled.Activation, { job, setup });
  assert.equal(activated, 0); await click(button('Preview activation credits'));
  assert.equal(button('Activate approved hiring version').disabled, true);
  await click(field('I approve this activation')); await click(button('Activate approved hiring version'));
  assert.equal(activated, 1); assert.ok(document.body.textContent.includes('Existing candidates were not changed'));
  const activation = calls.find(c => c.pathname.endsWith('/hiring-activations'));
  assert.equal(activation.body.accepted, true); assert.equal(activation.options.headers.Authorization, 'Bearer fixture-token');
  console.log('PASS explicit priced activation reuses authenticated API and preserves existing candidates');

  overview = makeOverview(); failActivation = true; calls = [];
  await mount(compiled.Activation, { job, setup }); await click(button('Preview activation credits')); await click(field('I approve this activation'));
  await click(button('Activate approved hiring version')); assert.ok(document.body.textContent.includes('Simulated activation failure'));
  failActivation = false; await click(button('Activate approved hiring version'));
  const retries = calls.filter(c => c.pathname.endsWith('/hiring-activations'));
  assert.equal(retries[0].body.operation_key, retries[1].body.operation_key);
  console.log('PASS failed activation preserves approved quote and retries with the same operation key');

  await input(field('Reason for OA window action'), 'Reschedule this cohort entry window.');
  await click(button('Authorize configured OA window'));
  await input(field('New OA entry opening'), '2027-01-07T09:00'); await input(field('New OA entry cutoff'), '2027-01-08T09:00');
  await click(button('Reschedule unstarted OA entries'));
  assert.ok(document.body.textContent.includes('Accepted attempt deadlines were preserved'));
  console.log('PASS reasoned manual window authorization and rescheduling preserve accepted attempts');

  calls = []; progress = makeProgress('completed');
  await mount(compiled.Actions, { application: { _id: 'app-one', workflow_version_id: 'version-one', workflow: progress.workflow } });
  assert.equal(button('Record cleared decision').disabled, true);
  await input(field('Decision or invitation reason'), 'Reviewed the retained screening evidence.'); await click(button('Record cleared decision'));
  assert.equal(calls.filter(c => c.pathname.endsWith('/oa-invitations')).length, 0);
  await click(button('Invite to online assessment'));
  assert.equal(calls.filter(c => c.pathname.endsWith('/oa-invitations')).length, 1);
  console.log('PASS screening clearance and explicit OA invitation remain separate revisioned actions');

  progress = makeProgress('evaluating'); calls = [];
  await mount(compiled.Actions, { application: { _id: 'app-one', workflow_version_id: 'version-one', workflow: progress.workflow } });
  assert.equal(button('Record cleared decision'), undefined); assert.equal(button('Invite to online assessment'), undefined);
  assert.equal(calls.some(c => c.options.method === 'POST'), false);
  console.log('PASS pending evaluation cannot be cleared or invited from recruiter controls');

  progress = makeProgress('completed'); progress.workflow.stages[0].outcome = 'cleared'; progress.workflow.workflow_label = 'Screening cleared';
  await mount(compiled.Notice, { applicationId: 'app-one', enabled: true });
  assert.ok(document.body.textContent.includes('The recruiter will confirm the next hiring step'));
  progress.invitation = { state: 'invited', opens_at: dates.oa_opens_at, start_closes_at: dates.oa_start_closes_at, duration_minutes: 60, runtime_ready: false };
  await click(button('Refresh hiring progress'));
  assert.ok(document.body.textContent.includes('full 60 minutes')); assert.ok(document.body.textContent.includes('OA workspace is not enabled yet'));
  failProgress = true; await click(button('Refresh hiring progress')); assert.ok(document.body.textContent.includes('Progress temporarily unavailable'));
  assert.ok(document.body.textContent.includes('full 60 minutes'));
  console.log('PASS candidate timeline distinguishes clearance and invitation and retains data after refresh failure');
} finally {
  if (root) await act(async () => root.unmount()); dom.window.close(); await rm(tmp, { recursive: true, force: true });
}

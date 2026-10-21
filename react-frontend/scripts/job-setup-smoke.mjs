// Offline rendered React integration checks. API fixtures use the actual Python catalog.
// This checks interactions/state, not browser layout, real AI, billing or delivery.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';

const cwd = process.cwd();
const backend = path.resolve(cwd, '../python-backend');
const python = process.env.GENHIRE_TEST_PYTHON || path.join(backend, process.platform === 'win32' ? 'venv/Scripts/python.exe' : 'venv/bin/python');
const fixture = JSON.parse(execFileSync(python, ['-c',
  'import json; import sys; sys.path.insert(0,"tests"); from assessment_test_fixtures import mcq,coding,sql; from services.job_setup_service import catalog, quote; c=catalog(); c["defaults"]["pipeline"]["oa_enabled"]=True; print(json.dumps(dict(catalog=c, quote=quote(c["defaults"]),questions=dict(mcq=mcq(),coding=coding(),sql=sql()))))'],
  { cwd: backend, encoding: 'utf8', env: { ...process.env, GENHIRE_WORKFLOW_ENABLED: 'true', RECRUITER_AI_JD_CREDITS: '10' } }));
fixture.catalog.defaults.pipeline.oa_enabled = false;
const tmp = await mkdtemp(path.join(cwd, '.job-setup-smoke-'));
const dom = new JSDOM('<!doctype html><div id="root"></div>', { url: 'http://localhost:3000' });
for (const key of ['window', 'document', 'navigator', 'sessionStorage', 'localStorage', 'HTMLElement', 'Element', 'Node', 'Event', 'MouseEvent', 'CustomEvent'])
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const React = await import('react');
const { act } = React;
const { createRoot } = await import('react-dom/client');
let questionCount=0, failAttach=false, workspaceIds=[], workspaceRevision=0, generationHold=false, generationPosts=0;
const generatedJobs=new Map(), privateQuestions=new Map();
let root, saved = null, enabled = true, loadFailure = false, attached = null, calls = [], closes = 0, submissions = [], notices = [];
const job = { _id: '507f1f77bcf86cd799439011', title: 'Software Engineer', department: 'Engineering', location: 'Remote',
  type: 'Full-time', experience: '2 years', salary: 'Competitive', description: 'Build products', skills: ['Python'],
  responsibilities: ['Build features'], requirements: ['Python'], benefits: ['Flexible work'], status: 'draft', deadline: '2030-01-08' };
globalThis.fetch = async (url, options = {}) => {
  const pathname = new URL(url, 'http://localhost').pathname;
  calls.push({ pathname, options });
  const body = options.body ? JSON.parse(options.body) : null;
  let payload, status = 200;
  if (pathname.endsWith('/job-setup/catalog')) payload = { ...fixture.catalog, workflow_enabled: enabled };
  else if(pathname.includes('/job-setup/templates/'))payload={oa:{...fixture.catalog.defaults.oa,...body,template_id:pathname.split('/').at(-2),sections:fixture.catalog.templates.find(t=>t.id===pathname.split('/').at(-2)).sections},questions:[]};
  else if (pathname.endsWith('/job-setup/preview')) payload = { configuration: body.configuration, quote: fixture.quote };
  else if (pathname.endsWith('/job-setup-drafts/latest')) {
    payload = loadFailure ? { error: 'Unavailable' } : { draft: saved }; status = loadFailure ? 503 : 200;
  } else if (pathname.endsWith('/hiring-setup')) payload = { version: attached, authoring_enabled:true, existing_application_count: 3, impact: 'Existing candidates keep their workflow.' };
  else if (pathname.includes('/job-setup-drafts')) {
    saved = { ...body, _id: saved?._id || '507f1f77bcf86cd799439012', revision: (body.expected_revision || 0) + 1, updated_at: '2030-01-01T00:00:00Z' };
    payload = { draft: saved };
  } else if (pathname.endsWith('/question-bank/versions')) {const question={_id:`private-${++questionCount}`,content:body.content};privateQuestions.set(question._id,question);payload={question};}
  else if(pathname.endsWith('/job-draft-generations')&&options.method==='POST') {
    generationPosts++;
    const questions=body.configuration.pipeline.oa_enabled?body.configuration.oa.sections.flatMap(section=>Array.from({length:section.count},(_,i)=>{
      const content=structuredClone(fixture.questions[section.type]);content.title=`${section.type} prepared ${i+1}`;content.marks=section.marks[i];content.difficulty='medium';
      const q={_id:`ai-${generationPosts}-${section.type}-${i}`,type:section.type,title:content.title,content};privateQuestions.set(q._id,q);return q;
    })):[];
    const result={id:`ai-job-${generationPosts}`,operation_key:body.operation_key,state:'queued',job_data:job,configuration:body.configuration,questions,credits:10,completed_questions:questions.length,total_questions:questions.length};
    generatedJobs.set(body.operation_key,result);payload={generation:result};
  }
  else if(pathname.includes('/job-draft-generations/')) {const item=generatedJobs.get(pathname.split('/').at(-1));payload={generation:{...item,state:generationHold?'queued':'completed',phase:generationHold?'waiting_provider':'saving'}};}

  else if (pathname.endsWith('/assessment-blueprints/bp-inline/content')) {
    if(options.method==='PUT') {
      if(failAttach){status=503;payload={error:'Attach temporarily unavailable'};}
      else {workspaceIds=body.question_version_ids;workspaceRevision++;payload={workspace:{question_version_ids:workspaceIds,revision:workspaceRevision}};}
    } else payload={question_version_ids:workspaceIds,revision:workspaceRevision,questions:workspaceIds.map(id=>privateQuestions.get(id)).filter(Boolean)};
  }
  else if (pathname.endsWith('/jobs/generate-ai')) payload = { job_data: job };
  else throw new Error('Unexpected API: ' + pathname);
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } });
};
const tick = async (ms = 30) => act(async () => { await new Promise(resolve => setTimeout(resolve, ms)); });
const button = text => [...document.querySelectorAll('button')].find(n => n.textContent.trim() === text);
const text = () => document.body.textContent;
const field = label => {const n=[...document.querySelectorAll('label')].find(n=>n.textContent.startsWith(label));return n?.querySelector('input,select,textarea')||(n?.htmlFor?document.getElementById(n.htmlFor):undefined);};
async function click(node) { assert.ok(node, 'Expected control'); await act(async () => node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))); await tick(); }
async function input(node, value) {
  assert.ok(node, 'Expected field');
  await act(async () => {
    const proto = node.tagName === 'SELECT' ? dom.window.HTMLSelectElement.prototype : node.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(node, value);
    node.dispatchEvent(new Event(node.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  });
  await tick();
}
async function step(index) {
  const name=['description','pipeline','oa','schedule'][index];
  const details=document.querySelector(`[data-job-section="${name}"]`);
  if(details&&!details.open)await act(async()=>{details.open=true;});
  await tick();
}
async function mount(Component, props = {}) {
  if (root) await act(async () => root.unmount());
  root = createRoot(document.getElementById('root'));
  sessionStorage.setItem('companyxyz-token', 'fixture-token');
  await act(async () => root.render(React.createElement(Component, { isOpen: true, onClose: () => closes++,
    onJobCreate: async payload => { submissions.push(payload); return true; }, showToast: message => notices.push(message), ...props })));
  await tick(); await tick(350);
}
async function submit() {
  await act(async () => document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  await tick();
}
try {
  const entry = ['JobCreationModal', 'JobEditModal', 'HiringSetupSummary'].map(name => `export {default as ${name}} from ${JSON.stringify(path.join(cwd, 'src/features/recruiter/components', name + '.jsx'))};`).join('\n');
  const output = await build({ stdin: { contents: entry, resolveDir: cwd, loader: 'jsx' }, bundle: true, write: false,
    outfile: path.join(tmp, 'bundle.mjs'), platform: 'node', format: 'esm', packages: 'external',
    alias: { shared: path.join(cwd, 'src/shared') }, loader: { '.js': 'jsx', '.png': 'dataurl', '.svg': 'dataurl' },
    define: { 'process.env': JSON.stringify({ NODE_ENV: 'test', REACT_APP_API_URL: 'http://localhost:5000' }) } });
  await writeFile(path.join(tmp, 'bundle.mjs'), output.outputFiles.find(f => f.path.endsWith('.mjs')).text);
  const compiled = await import(pathToFileURL(path.join(tmp, 'bundle.mjs')).href);
  sessionStorage.setItem('companyxyz-user',JSON.stringify({_id:'recruiter-recovery',user_type:'recruiter'}));
  await mount(compiled.JobCreationModal);
  await input(document.querySelector('input[name="title"]'),'Recovery Engineer');
  await click(button('Create with AI · 10 credits total'));
  await input(field('Describe the job and assessment'),'Recover my AI drafting prompt');
  await click(field('Include an online assessment'));await step(2);
  await input(field('Instructions for assessment generation'),'Keep recovered OA requirements');
  await tick(650);await mount(compiled.JobCreationModal);
  assert.ok(button('Resume device draft'));await click(button('Resume device draft'));
  assert.equal(field('Instructions for assessment generation').value,'Keep recovered OA requirements');
  await step(0);assert.equal(document.querySelector('input[name="title"]').value,'Recovery Engineer');
  assert.equal(field('Describe the job and assessment').value,'Recover my AI drafting prompt');
  await mount(compiled.JobEditModal,{jobData:job});
  await input(document.querySelector('input[name="title"]'),'Recovered editing progress');await step(1);
  await input(field('Minimum screening interview score'),'68');
  await mount(compiled.JobEditModal,{jobData:job});
  assert.ok(button('Resume device draft'));await click(button('Resume device draft'));
  assert.equal(field('Minimum screening interview score').value,'68');await step(0);
  assert.equal(document.querySelector('input[name="title"]').value,'Recovered editing progress');
  await mount(compiled.JobEditModal,{jobData:{...job,_id:'507f1f77bcf86cd799439099'}});
  assert.ok(!button('Resume device draft'));
  console.log('PASS closing editing before debounce still recovers progress without crossing jobs');
  sessionStorage.setItem('companyxyz-user',JSON.stringify({_id:'another-recruiter',user_type:'recruiter'}));
  await mount(compiled.JobCreationModal);assert.ok(!button('Resume device draft'));
  await act(async()=>root.unmount());root=null;sessionStorage.removeItem('companyxyz-user');localStorage.clear();
  console.log('PASS automatic device recovery restores job, OA, AI prompt and step without crossing accounts');
  for (const [title, id, kind] of [['Data Analyst','data_analyst','sql'],['Product Manager','product','mcq'],['HR Specialist','hr','mcq']]) {
    saved=null; await mount(compiled.JobCreationModal);
    const ids=[...document.querySelectorAll('[id]')].map(n=>n.id);
    assert.equal(new Set(ids).size,ids.length,'Dialog and field IDs must be unique');
    assert.equal(document.querySelector('label[for="create-job-description"]').textContent.includes('Job Description'),true);
    assert.ok(document.querySelector('[data-job-section="oa"]'));
    assert.equal(document.querySelector('nav[aria-label="Job setup steps"]'),null);
    assert.equal(button('Next'),undefined);
    await click(document.querySelector('details summary'));
    await input(field('Find a role'),title);
    const template=[...document.querySelectorAll('button strong')].find(n=>n.textContent===title)?.closest('button');
    await click(template);
    assert.equal(document.querySelector('details').open,false);
    assert.ok(text().includes(title+' applied.'));
    assert.equal(document.querySelector('input[name="title"]').value,title);
    await click(field('Include an online assessment'));
    await step(2);
    assert.equal(field('Role template').value,id);
    assert.ok(field(kind==='sql'?'SQL question count':'MCQ question count').value>0);
    await input(field('Question creation method'),'ai');
    await input(field('Instructions for assessment generation'),'Keep my custom instructions');
    await step(1);await click(field('Include an online assessment'));await click(field('Include an online assessment'));await step(2);
    assert.equal(field('Instructions for assessment generation').value,'Keep my custom instructions');
  }
  console.log('PASS first-step OA role autofill for data, product and HR; disable/re-enable preserves customization');
  saved=null;
  await mount(compiled.JobCreationModal);
  assert.equal(document.querySelectorAll('nav[aria-label="Job setup steps"] button').length, 0);
  assert.ok(text().includes('10 credits total per JD'));
  await step(1); await click(field('Include an online assessment'));
  assert.equal(field('Minimum screening interview score').value,'60');
  assert.equal(field('Minimum proctoring score').value,'70');
  await input(field('Minimum screening interview score'),'');
  await act(async()=>field('Minimum screening interview score').dispatchEvent(new dom.window.FocusEvent('focusout',{bubbles:true})));
  assert.equal(field('Minimum screening interview score').value,'60');
  await input(field('Minimum screening interview score'), '72');
  await step(2); await input(field('Role template'), 'data_analyst');
  await input(field('Question creation method'), 'ai');
  await input(field('SQL engine'), 'mysql');
  await input(field('Default coding format'), 'function');
  await input(field('Instructions for assessment generation'), 'SQL joins and analytical reasoning');
  await step(3); await input(field('Timer mode'), 'section'); await tick(350);
  assert.ok(text().includes('Section timing & score weights'));
  assert.equal(field('SQL contribution to final score').value,'60');
  await input(field('SQL contribution to final score'),'55');await input(field('MCQ contribution to final score'),'45');
  await tick(350);
  assert.ok(text().includes('Total score weight: 100%'));
  assert.equal(field('Allow revisiting').checked, false);
  assert.ok(text().includes('24-hour start window'));
  assert.ok(text().includes('full attempt duration'));
  assert.ok(text().includes('Due now for saving configuration: 0 credits'));
  await click(button('Save hiring draft'));
  assert.equal(saved.configuration.oa.sql_engine, 'mysql');
  assert.equal(saved.configuration.oa.coding_contract, 'function');
  assert.equal(saved.configuration.oa.sections[0].type, 'sql');
  assert.equal(saved.configuration.qualification.interview_minimum, 72);
  assert.equal(saved.configuration.oa.timer_mode, 'section');
  assert.equal(saved.configuration.oa.sections.find(s=>s.type==='sql').weight,55);
  assert.equal(calls.find(c => c.pathname.endsWith('/job-setup-drafts')).options.headers.Authorization, 'Bearer fixture-token');
  console.log('PASS recruiter wizard templates, policy, dialect, coding format, timer, server price and draft persistence');
  // Manual job fields and independently configured OA save together without AI.
  await step(0);await click(button('Fill manually · free'));
  await click(document.querySelector('details summary'));
  await click([...document.querySelectorAll('button strong')].find(n=>n.textContent==='Software Engineer')?.closest('button'));
  await step(3);await tick(350);await submit();
  assert.equal(submissions.length, 1);
  assert.equal(submissions[0].title, job.title);
  assert.ok(submissions[0].setup_draft_id);
  assert.equal(saved.configuration.oa.instructions, 'SQL joins and analytical reasoning');
  console.log('PASS manual JD fields preserve configured OA and submit its saved revision without AI');
  await mount(compiled.JobCreationModal);
  assert.ok(button('Resume saved draft')); await click(button('Resume saved draft')); await step(2);
  assert.equal(field('SQL engine').value, 'mysql');
  assert.equal(field('Question creation method').value, 'manual');
  console.log('PASS saved draft resumes after reopening');
  // A device copy and server save are two stores for one working draft, not two prompts.
  sessionStorage.setItem('companyxyz-user',JSON.stringify({_id:'single-resume-owner',user_type:'recruiter'}));
  await input(document.querySelector('input[name="title"]'),'Most recent device draft');await tick(650);
  await mount(compiled.JobCreationModal);
  assert.equal([...document.querySelectorAll('button')].filter(n=>/^Resume (device|saved) draft$/.test(n.textContent.trim())).length,1);
  assert.ok(button('Resume device draft'));await click(button('Resume device draft'));
  assert.equal(button('Resume saved draft'),undefined);assert.equal(document.querySelector('input[name="title"]').value,'Most recent device draft');
  sessionStorage.removeItem('companyxyz-user');localStorage.clear();
  console.log('PASS device and server recovery offer one resume choice for one working draft');

  saved = null; closes = 0;
  await mount(compiled.JobEditModal, { jobData: job, onJobUpdate: async payload => { submissions.push(payload); return false; } });
  const editDialog=document.querySelector('[role="dialog"]');editDialog.scrollTop=900;
  await step(3);assert.equal(editDialog.scrollTop,900); await tick(350); await submit();
  assert.equal(closes, 0);
  assert.ok(document.querySelector('form'));
  assert.equal(saved.configuration.schedule.application_closes_at, '2030-01-08T23:59');
  const revision = saved.revision;
  const writes = calls.filter(c => c.options.method === 'POST' && c.pathname.endsWith('/job-setup-drafts') || c.options.method === 'PUT' && c.pathname.includes('/job-setup-drafts/')).length;
  await submit();
  assert.equal(saved.revision, revision);
  assert.equal(calls.filter(c => c.options.method === 'POST' && c.pathname.endsWith('/job-setup-drafts') || c.options.method === 'PUT' && c.pathname.includes('/job-setup-drafts/')).length, writes);
  assert.deepEqual(submissions.at(-1), submissions.at(-2));
  console.log('PASS legacy editing preserves deadline and failed job update keeps dialog open');
  console.log('PASS unchanged retry reuses the saved revision after a failed job request');
  saved = null; loadFailure = true;
  await mount(compiled.JobEditModal, { jobData: job, onJobUpdate: async () => true });
  await step(3);
  assert.ok(text().includes('Saved hiring settings could not be loaded'));
  assert.equal(button('Update Job').disabled, true);
  console.log('PASS unavailable saved settings block overwrite');
  loadFailure=false;await click(button('Retry hiring settings'));await tick(350);
  assert.ok(!text().includes('Saved hiring settings could not be loaded'));
  await step(0);assert.ok(document.querySelector('[data-job-section="oa"]'));
    assert.equal(document.querySelector('nav[aria-label="Job setup steps"]'),null);
    assert.equal(button('Next'),undefined);
  console.log('PASS saved-settings retry recovers editing without closing or losing job details');
  saved=null; attached={revision:2,configuration:structuredClone(fixture.catalog.defaults)};
  await mount(compiled.JobEditModal,{jobData:{...job,title:'HR Specialist'},onJobUpdate:async()=>true});
  await click(button('Fill manually · free'));
  await click(field('Include an online assessment'));await step(2);
  assert.equal(field('Role template').value,'hr');
  console.log('PASS an existing OA-off job initializes the current role rather than the legacy SDE default');
  attached=null;
  saved=null;localStorage.clear();
  sessionStorage.setItem('companyxyz-user',JSON.stringify({_id:'wizard-inline',user_type:'recruiter'}));
  await mount(compiled.JobCreationModal);
  await click(document.querySelector('details summary'));await click([...document.querySelectorAll('button strong')].find(n=>n.textContent==='Data Analyst')?.closest('button'));
  await click(field('Include an online assessment'));await step(2);
  const dialog=document.querySelector('[role="dialog"]');dialog.scrollTop=800;dialog.scrollLeft=120;
  await step(3);assert.equal(dialog.scrollTop,800);
  assert.equal(button('Next'),undefined);assert.equal(button('Back'),undefined);
  await step(2);
  await click(button('Use current role defaults'));
  assert.ok(text().includes('Role defaults applied for Data Analyst'));
  await input(field('Question creation method'),'ai');
  await input(field('Instructions for assessment generation'),'Custom instructions');
  await click(button('Use current role defaults'));assert.notEqual(field('Instructions for assessment generation').value,'Custom instructions');
  console.log('PASS single-page sections retain scroll without Next/Back; role reset confirms every click');
  await input(field('Question creation method'),'manual');
  await step(2);await click(button('Add MCQ question'));
  await input(field('Question title'),'Which value?');await input(field('Problem statement'),'Choose the correct value.');
  await input(field('Option 1'),'One');await input(field('Option 2'),'Two');await click(field('Correct option 1'));
  await mount(compiled.JobCreationModal);await click(button('Resume device draft'));await step(2);
  assert.equal(field('Question title').value,'Which value?');
  await click(button('Save private question version'));assert.ok(text().includes('Private question saved'));
  assert.equal(field('Question title'),undefined);
  await click(button('Add SQL question'));assert.ok(text().includes('Private reference query'));await click(button('Discard unsaved question'));
  await click(button('Add CODING question'));assert.ok(field('input format'));await click(button('Discard unsaved question'));
  attached={configuration:structuredClone(fixture.catalog.defaults),assessment_blueprint_id:'bp-inline'};
  let creates=0;failAttach=true;localStorage.clear();
  // Keep the same component instance while replacing the callback, as the dashboard does.
  await act(async()=>root.render(React.createElement(compiled.JobCreationModal,{isOpen:true,onClose:()=>closes++,
    showToast:m=>notices.push(m),onJobCreate:async()=>{creates++;return {_id:job._id};}})));
  await step(3);await submit();assert.equal(creates,1);assert.ok(button('Retry attaching questions'));
  await mount(compiled.JobCreationModal,{onJobCreate:async()=>{creates++;return {_id:job._id};}});
  await click(button('Resume device draft'));assert.ok(button('Retry attaching questions'));
  failAttach=false;await click(button('Retry attaching questions'));
  assert.equal(creates,1);assert.equal(workspaceIds.length,1);
  console.log('PASS inline MCQ editor recovers and saves privately; attachment failure survives reopening and retry never recreates job');
  attached=null;saved=null;localStorage.clear();generationHold=true;
  await mount(compiled.JobCreationModal);
  await click(button('Create with AI · 10 credits total'));
  await input(field('Describe the job and assessment'),'Data engineer with SQL, Python and reasoning questions');
  await click(field('Include an online assessment in this draft'));
  await input(field('MCQ questions'),'2');await input(field('CODING questions'),'1');await input(field('SQL questions'),'1');
  const beforePosts=generationPosts;await click(button('Generate JD + OA questions'));
  assert.equal(generationPosts,beforePosts+1);assert.ok(text().includes('Preparing your draft'));
  await tick(80);assert.ok(text().includes('resuming automatically. No extra credits.'));
  await step(1);await input(field('Minimum screening interview score'),'88');await step(3);await input(field('Job timezone'),'UTC');
  await mount(compiled.JobCreationModal);generationHold=false;await click(button('Resume device draft'));await tick(80);
  assert.equal(generationPosts,beforePosts+1);
  await step(1);assert.equal(field('Minimum screening interview score').value,'88');await step(3);assert.equal(field('Job timezone').value,'UTC');await step(2);
  assert.ok(document.querySelector('[aria-label="MCQ draft questions"]'));
  assert.ok(document.querySelector('[aria-label="CODING draft questions"]'));
  assert.ok(document.querySelector('[aria-label="SQL draft questions"]'));
  assert.ok(text().includes('mcq prepared 1'));assert.ok(!button('Add MCQ question'));
  await click(button('Edit prefilled question'));assert.equal(field('Question title').value,'mcq prepared 1');assert.equal(document.activeElement,field('Question title'));
  assert.equal(field('Option 1').value,'2');await click(button('Discard unsaved question'));
  await step(0);assert.equal(document.querySelector('input[name="title"]').value,job.title);
  const lastGeneration=calls.filter(c=>c.pathname.endsWith('/job-draft-generations')).at(-1);
  assert.equal(JSON.parse(lastGeneration.options.body).accepted_credits,10);
  assert.equal(calls.filter(c=>c.pathname.includes('generation-quotes')||c.pathname.endsWith('/jobs/generate-ai')).length,0);
  console.log('PASS one AI action selects all three question types and exact counts, restores progress and prefills JD and question editors for ten credits');
  localStorage.clear();saved=null;
  const oldQuestion=[...privateQuestions.values()].find(q=>q.type==='mcq');workspaceIds=[oldQuestion._id];
  const existingConfig=structuredClone(fixture.catalog.defaults);existingConfig.pipeline.oa_enabled=true;
  existingConfig.oa.sections=[{type:'mcq',count:1,difficulty:{easy:0,medium:1,hard:0},marks:[1],weight:100,duration_minutes:30}];
  attached={configuration:existingConfig,assessment_blueprint_id:'bp-inline'};
  await mount(compiled.JobEditModal,{jobData:job,onJobUpdate:async()=>true});
  await step(2);assert.ok(text().includes(oldQuestion.content.title));await step(0);
  await click(button('Create with AI · 10 credits total'));
  await input(field('Describe the job and assessment'),'Rewrite the role with one SQL question');
  if(!field('Include an online assessment in this draft').checked)await click(field('Include an online assessment in this draft'));
  await input(field('MCQ questions'),'0');await input(field('CODING questions'),'0');await input(field('SQL questions'),'1');
  await click(button('Generate JD + OA questions'));await tick(2100);
  assert.ok(document.querySelector('[aria-label="SQL draft questions"]'));
  assert.ok(!document.querySelector('[aria-label="MCQ draft questions"]'));
  await step(3);await tick(350);await submit();
  assert.equal(workspaceIds.length,1);assert.ok(workspaceIds[0].includes('-sql-'));
  console.log('PASS job editing loads existing questions and replaces the draft set with complete AI content without appending duplicates');
  await mount(compiled.JobEditModal,{jobData:job,onJobUpdate:async()=>true});
  await step(2);await click(button('Remove from this job'));await tick(350);await submit();
  assert.deepEqual(workspaceIds,[]);
  console.log('PASS removing the final selected question clears its saved working selection');

  attached=null;saved=null;localStorage.clear();
  loadFailure = false; enabled = false;
  await mount(compiled.JobCreationModal);
  assert.equal(document.querySelector('nav[aria-label="Job setup steps"]'), null);
  assert.ok(text().includes('10 credits total per JD'));
  assert.ok(text().includes('Default: 7 days'));
  assert.equal(calls.filter(c => /wallet|payment|charge/.test(c.pathname)).length, 0);
  assert.ok(text().includes('Assessment settings are currently unavailable'));
  assert.ok(button('Reload assessment options'));
  console.log('PASS disabled configuration stays discoverable instead of silently hiding OA');
  console.log('PASS default-off legacy form and server-driven prices without OA charges');
  enabled = true; attached = { revision: 2, configuration: fixture.catalog.defaults, assessment_blueprint_id:'bp-inline' };
  workspaceIds=[oldQuestion._id];
  const requestsBeforePreview=calls.length;
  await mount(compiled.HiringSetupSummary, { job: { ...job, hiring_setup_version_id: 'version-2' } });
  assert.ok(text().includes('version 2'));
  assert.ok(text().includes('3 existing applications'));
  assert.ok(!calls.slice(requestsBeforePreview).some(c=>c.pathname.endsWith('/question-bank')));
  assert.ok(!text().includes('Your private question bank'));
  await click(button('View OA questions (recruiter only)'));
  assert.ok(document.querySelector('[aria-label="Recruiter-only OA questions"]'));
  assert.ok(text().includes(oldQuestion.content.statement));
  assert.ok(text().includes('(correct)'));
  assert.ok(!text().includes('Your private question bank'));
  console.log('PASS private job details show configuration version and candidate impact');
} finally {
  if (root) await act(async () => root.unmount());
  dom.window.close();
  await rm(tmp, { recursive: true, force: true });
}

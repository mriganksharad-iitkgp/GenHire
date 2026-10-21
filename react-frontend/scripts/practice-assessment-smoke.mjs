import assert from 'node:assert/strict';
import { assertNamedControls } from './oa-accessibility.mjs';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import {JSDOM} from 'jsdom';
const cwd=process.cwd(),tmp=await mkdtemp(path.join(cwd,'.practice-oa-smoke-'));
const dom=new JSDOM('<!doctype html><div id="root"></div>',{url:'http://localhost:3000',pretendToBeVisual:true});
for(const name of ['window','document','navigator','sessionStorage','localStorage','HTMLElement','Element','Node','Event','MouseEvent','CustomEvent'])Object.defineProperty(globalThis,name,{value:dom.window[name],configurable:true,writable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;window.confirm=()=>true;
const {default:React,act}=await import('react');const {createRoot}=await import('react-dom/client');const {MemoryRouter}=await import('react-router-dom');
let root,calls=[],purchased=false,failPurchase=true,resultReady=false,priceFailure=false,executionReady=true;
const config={template_id:'custom',specialization:'general',source:'ai',instructions:'',languages:['python','javascript','java','cpp'],sql_engine:'postgresql',coding_contract:'stdin_stdout',mcq_mode:'single',sections:[{type:'mcq',count:1,difficulty:{easy:1,medium:0,hard:0},marks:[1],weight:100,duration_minutes:5}],timer_mode:'shared',duration_minutes:5,revisit_allowed:true,proctoring_level:'basic',variant_count:1,advanced_analytics:false,plagiarism_check:false};
const pricing={credits:{mock_oa:37,practice_interview:33,practice_interview_proctored:53,candidate_invite:3,signup_bonus:150,ai_jd:12,screening:31,screening_proctored:51,oa_setup:32,camera_proctoring:11,dual_proctoring:13},packs:{candidate_pro:{price_paise:62100,credits_allocated:789}},currency:'INR'};
const purchase={purchase_id:'purchase-fixture',configuration:config,state:'ready',price:{total_credits:37},invitation_id:'invitation-fixture',attempt_id:null};
globalThis.fetch=async(url,options={})=>{
  const pathname=new URL(url,'http://localhost').pathname,body=options.body?JSON.parse(options.body):null;calls.push({pathname,body,headers:options.headers});
  if(pathname.endsWith('/pricing/catalog')){assert.equal(options.headers.Authorization,undefined);return new Response(JSON.stringify(priceFailure?{error:'Simulated pricing outage'}:pricing),{status:priceFailure?503:200});}
  assert.equal(options.headers.Authorization,'Bearer fixture-token');let value;
  if(pathname.endsWith('/practice/assessments/catalog'))value={enabled:true,runtime_ready:true,media_ready:false,section_availability:{mcq:true,coding:executionReady,sql:executionReady},defaults:config,templates:[{id:'custom',name:'Custom practice',sections:config.sections,duration_minutes:5}],pricing};
  else if(pathname.endsWith('/practice/assessments/quotes'))value={quote_id:'quote-fixture',total_credits:37,line_items:[{code:'mock_oa',credits:37,unit:'one_generation_and_attempt'}],start_within_days:30};
  else if(pathname.endsWith('/practice/assessments')&&body){assert.equal(body.accepted,true);if(failPurchase)return new Response(JSON.stringify({error:'Simulated purchase outage'}),{status:503});purchased=true;value=purchase;}
  else if(pathname.endsWith('/practice/assessments'))value={purchases:purchased?[purchase]:[],next_cursor:null};
  else if(pathname.endsWith('/evaluation'))value=resultReady?{pool:'practice',result_available:true,score:0,sections:[{type:'mcq',earned:0,possible:1,weight:100}],questions:[{question_id:'q-fixture',title:'Learning question',earned:0,marks:1,question:{statement:'Choose the even number.',mcq:{options:[{id:'a',text:'2'},{id:'b',text:'3'}]}},correct_option_ids:['a'],explanation:'Even numbers are divisible by two.'}],ai_feedback:{state:'unavailable',label:'AI educational advice; objective marks unchanged.'}}:{result_available:false,message:'Evaluation is pending; no final score is invented.'};
  else if(pathname.endsWith('/billing-operations'))value={operations:[{operation_id:'operation-fixture',purpose:'mock_oa_purchase',credits:37,state:'refunded',refunded_credits:37,created_at:'2027-01-01T00:00:00Z',refunds:[{credits:37,reason:'Verified platform failure.'}]}],next_cursor:null};
  else if(pathname.includes('/admin/practice-assessments/'))value={purchases:[{...purchase,invitation:{invitation_id:'invitation-fixture',state:'invited'}}],next_cursor:null};
  else if(pathname.endsWith('/assessment-invitations/invitation-fixture'))value={integrity_policy:{accommodation_revision:0,mode:'kiosk'}};
  else if(pathname.endsWith('/secure-launch')){assert.equal(body.mode,'kiosk');value={launch_code:'opaque-practice-fixture'};}
  else if(pathname.endsWith('/accommodation')){assert.equal(body.browser_allowed,true);assert.equal(body.expected_revision,0);value={revision:1};}
  else throw new Error('Unexpected fixture request '+pathname);
  return new Response(JSON.stringify(value),{status:200});
};
const tick=()=>act(async()=>{await new Promise(resolve=>setTimeout(resolve,20));});
const button=text=>[...document.querySelectorAll('button')].find(el=>el.textContent.includes(text));
const label=text=>[...document.querySelectorAll('label')].find(el=>el.textContent.trim().startsWith(text)).querySelector('input,textarea,select');
async function click(text){const el=button(text);assert.ok(el,text);assert.equal(el.disabled,false,text);await act(async()=>el.dispatchEvent(new MouseEvent('click',{bubbles:true})));await tick();}
async function input(el,value){const prototype=el.tagName==='TEXTAREA'?dom.window.HTMLTextAreaElement.prototype:dom.window.HTMLInputElement.prototype;await act(async()=>{Object.getOwnPropertyDescriptor(prototype,'value').set.call(el,value);el.dispatchEvent(new Event('input',{bubbles:true}));});}
async function mount(Page,props={}){if(root)await act(async()=>root.unmount());root=createRoot(document.getElementById('root'));await act(async()=>root.render(React.createElement(MemoryRouter,null,React.createElement(Page,props))));await tick();}
try{
  const result=await build({stdin:{contents:"export {default as Mock} from './src/features/candidate/components/MockAssessmentPanel.jsx';export {default as Report} from './src/features/assessment/components/PracticeAssessmentReport.jsx';export {default as Billing} from './src/shared/components/billing/BillingOperationsPanel.jsx';export {default as Support} from './src/features/admin/components/PracticeAssessmentOperations.jsx';export {default as Landing} from './src/features/landing/pages/LandingPage.jsx';import React from 'react';import usePricing from './src/shared/hooks/usePricingCatalog.js';export function PriceProbe(){const {catalog,error,reload}=usePricing();return React.createElement('div',null,error||catalog?.credits.mock_oa||'loading',React.createElement('button',{onClick:reload},'Retry catalog'));}",resolveDir:cwd},outfile:path.join(tmp,'bundle.mjs'),bundle:true,write:false,platform:'node',format:'esm',packages:'external',alias:{shared:path.join(cwd,'src/shared'),features:path.join(cwd,'src/features')},loader:{'.js':'jsx'},define:{'process.env':JSON.stringify({NODE_ENV:'test'})}});
  await writeFile(path.join(tmp,'bundle.mjs'),result.outputFiles.find(f=>f.path.endsWith('.mjs')).text);const {Mock,Report,Billing,Support,Landing,PriceProbe}=await import(pathToFileURL(path.join(tmp,'bundle.mjs')).href);
  sessionStorage.setItem('companyxyz-token','fixture-token');await mount(Mock);assertNamedControls(document);
  assert.ok(document.body.textContent.includes('Base: 37 credits'));assert.equal(calls.some(c=>c.body),false);assert.equal(document.body.textContent.includes('Dual camera'),false);
  console.log('PASS role practice loads server prices without purchasing and hides unavailable paid monitoring');
  await click('Review price & generate OA');assert.equal(button('Generate OA \u00b7').disabled,true);
  await input(label('What should'), 'Focus on quantitative product reasoning.');assert.equal(button('Generate OA \u00b7'),undefined);await click('Review price & generate OA');
  console.log('PASS configuration edits invalidate the quote and explicit approval is required before purchase');
  await act(async()=>label('I approve').click());await click('Generate OA \u00b7');assert.ok(document.body.textContent.includes('Simulated purchase outage'));
  failPurchase=false;await click('Generate OA \u00b7');const buys=calls.filter(c=>c.pathname.endsWith('/practice/assessments')&&c.body);
  assert.equal(buys[0].body.operation_key,buys[1].body.operation_key);assert.ok(document.querySelector('a[href="/assessments/invitation-fixture"]'));
  console.log('PASS failed purchase preserves approval and retry key, then exposes the same paid practice resume link');
  purchase.state='generating';purchase.invitation_id=null;purchase.progress={ready_questions:0,total_questions:1,phase:'queued'};
  await mount(Mock);assert.ok(document.body.textContent.includes('0/1 questions ready'));assert.equal(button('Start / resume in Secure Browser'),undefined);
  purchase.state='ready';purchase.invitation_id='invitation-fixture';
  await act(async()=>window.dispatchEvent(new Event('focus')));await tick();
  assert.ok(document.querySelector('[role="dialog"]').textContent.includes('practice assessment'));
  await act(async()=>label('I have installed GenHire').click());await click('Open Secure Browser');
  const frame=document.querySelector('iframe[src^="secure-interview:"]');assert.ok(frame);
  const payload=JSON.parse(Buffer.from(new URL(frame.src).searchParams.get('initData'),'base64').toString());
  assert.equal(payload.mode,'oa');assert.equal(payload.practice,true);assert.equal(payload.launchCode,'opaque-practice-fixture');assert.equal(payload.token,undefined);
  assert.equal(calls.some(c=>c.pathname.endsWith('/start')),false);
  console.log('PASS queued generation resumes on return, prompts secure-browser launch once ready, and uses an opaque grant without starting the timer');
  executionReady=false;await mount(Mock);
  assert.equal(label('CODING questions').disabled,true);assert.equal(label('SQL questions').disabled,true);
  assert.equal([...document.querySelectorAll('summary')].find(el=>el.textContent.includes('Customize questions')).parentElement.open,false);
  await click('Custom practice');assert.equal([...document.querySelectorAll('summary')].find(el=>el.textContent.includes('Practice role:')).parentElement.open,false);
  await input(label('MCQ questions'),'5');await click('Review price & generate OA');
  const configured=calls.filter(c=>c.pathname.endsWith('/quotes')).at(-1).body.configuration;
  assert.equal(configured.sections[0].count,5);assert.equal(configured.sections[0].weight,100);assert.equal(configured.sections[0].marks.length,5);
  console.log('PASS compact role selection collapses, unavailable executable types are disabled, and quick question counts keep valid defaults');
  await mount(Report,{attemptId:'attempt-fixture'});await click('View / refresh practice feedback');assert.equal(document.body.textContent.includes('Objective practice score'),false);
  resultReady=true;await click('View / refresh practice feedback');assert.ok(document.body.textContent.includes('Objective practice score: 0%'));assert.ok(document.body.textContent.includes('Even numbers are divisible by two'));
  console.log('PASS pending evaluation has no guessed score and completed practice exposes zero marks and teaching explanations');
  assert.ok(document.body.textContent.includes('Advice: unavailable'));assert.ok(document.body.textContent.includes('AI educational advice; objective marks unchanged'));
  console.log('PASS unavailable AI advice remains separate from deterministic objective marks');
  await mount(Billing);await click('Load / refresh purchase history');assert.ok(document.body.textContent.includes('37 credits; refunded; 37 refunded'));assert.ok(document.body.textContent.includes('Verified platform failure'));
  console.log('PASS candidate billing history shows recorded captured/refunded outcomes without activity-based estimates');
  await mount(Support,{candidateId:'candidate-fixture'});await click('Inspect candidate mock OAs');assert.equal(button('Preview similarity'),undefined);
  await input(label('Reason for integrity'), 'Support approved assistive browser controls.');await act(async()=>label('Approve accessible browser').click());await click('Approve invitation accommodation');
  assert.ok(document.body.textContent.includes('Accommodation saved'));
  console.log('PASS support can approve revisioned practice accommodations while recruitment similarity remains absent');
  await mount(Landing);assert.ok(document.body.textContent.includes('37 credits base'));assert.ok(document.body.textContent.includes('150 one-time wallet credits'));assert.ok(document.body.textContent.includes('621.00'));assert.ok(document.body.textContent.includes('789 non-expiring wallet credits'));
  console.log('PASS public pricing and recharge cards display server values instead of hardcoded fees or signup bonuses');
  priceFailure=true;await mount(PriceProbe);assert.ok(document.body.textContent.includes('Simulated pricing outage'));assert.equal(sessionStorage.getItem('companyxyz-token'),'fixture-token');priceFailure=false;await click('Retry catalog');assert.ok(document.body.textContent.includes('37'));
  console.log('PASS pricing outage preserves account login and explicit retry reloads the current catalog');
}finally{if(root)await act(async()=>root.unmount());dom.window.close();await rm(tmp,{recursive:true,force:true});}

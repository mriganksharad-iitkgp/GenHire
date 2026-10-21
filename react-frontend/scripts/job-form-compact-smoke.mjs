// Offline behavior checks, not browser geometry or managed execution acceptance.
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm,readFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import {JSDOM} from 'jsdom';
const cwd=process.cwd(),tmp=await mkdtemp(path.join(cwd,'.compact-form-'));
const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost:3000'});
for(const k of ['window','document','navigator','sessionStorage','localStorage','HTMLElement','Element','Node','Event','MouseEvent'])Object.defineProperty(globalThis,k,{value:dom.window[k],configurable:true,writable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const React=await import('react'),{act}=React,{createRoot}=await import('react-dom/client');
const root=createRoot(document.getElementById('root'));
const click=async n=>act(async()=>{assert.ok(n);n.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,10));});
try{
 const entry=['QuestionAccordionGroup','TermHelp','RoleAssessmentTemplateControls','JobAIDraftBuilder'].map(n=>`export {default as ${n}} from './src/features/recruiter/components/${n}.jsx';`).join('\n')+"\nexport {default as Toast} from './src/shared/components/ui/Toast.jsx';";
 const bundle=await build({stdin:{contents:entry,resolveDir:cwd,loader:'jsx'},bundle:true,write:false,outfile:path.join(tmp,'bundle.mjs'),platform:'node',format:'esm',packages:'external',alias:{shared:path.join(cwd,'src/shared')},loader:{'.js':'jsx'},define:{'process.env':JSON.stringify({NODE_ENV:'test'})}});
 await writeFile(path.join(tmp,'bundle.mjs'),bundle.outputFiles.find(f=>f.path.endsWith('.mjs')).text);
 const c=await import(pathToFileURL(path.join(tmp,'bundle.mjs')).href);
 await act(async()=>root.render(React.createElement(c.QuestionAccordionGroup,{label:'MCQ questions',items:[{id:'a'},{id:'b'}],title:(_,i)=>'Question '+(i+1),render:(_,i)=>React.createElement('p',null,'Answer '+(i+1))})));
 let details=[...document.querySelectorAll('details')];assert.ok(details.every(d=>!d.open));
 await click(details[0].querySelector('summary'));await click(details[1].querySelector('summary'));assert.ok(details[1].open);
 await click(details[2].querySelector('summary'));assert.ok(details[2].open);assert.ok(!details[1].open);
 await click(document.querySelector('button'));assert.ok(details[1].open&&details[2].open);
 await click(document.querySelector('button'));assert.ok(!details[1].open&&!details[2].open);
 console.log('PASS collapsed type groups, one open question and expand/collapse all');
 await act(async()=>root.render(React.createElement(c.TermHelp,{term:'Cohort'},'Candidates apply until one shared deadline.')));
 const help=document.querySelector('button');await act(async()=>help.focus());
 assert.equal(document.querySelector('[role="tooltip"]').parentElement,document.body);
 assert.equal(document.querySelector('[role="tooltip"]').id,help.getAttribute('aria-describedby'));
 await act(async()=>window.dispatchEvent(new Event('resize')));assert.equal(document.querySelector('[role="tooltip"]'),null);
 console.log('PASS keyboard help uses a body portal and dismisses on resize');
 let closed=0;
 await act(async()=>root.render(React.createElement(c.Toast,{message:'Saved changes',duration:300,onClose:()=>closed++})));
 assert.equal(document.querySelector('[role="status"]').parentElement,document.body);
 await act(async()=>root.render(React.createElement(c.Toast,{message:'New message',duration:300,onClose:()=>closed++})));
 await click(document.querySelector('[aria-label="Close notification"]'));
 await act(async()=>new Promise(r=>setTimeout(r,650)));assert.equal(closed,1);
 const toastCss=await readFile('src/shared/components/ui/Toast.module.css','utf8');assert.match(toastCss,/z-index: 2147483000/);assert.match(toastCss,/calc\(100vw - 32px\)/);
 console.log('PASS toasts escape dialog stacking contexts, fit narrow screens and close once');
 const fields={configuration:{pipeline:{oa_enabled:false},oa:{sql_engine:'postgresql',languages:['python']}}};let calls=0,changed;
 const setup={...fields,setAssessmentEnabled:v=>{fields.configuration.pipeline.oa_enabled=v;},setConfiguration:fn=>{fields.configuration=fn(fields.configuration);}};
 globalThis.fetch=async()=>{calls++;return new Response(JSON.stringify({oa:{...fields.configuration.oa,source:'manual'},questions:[{_id:'private',content:{title:'SQL draft',type:'sql'}}]}),{status:200});};
 await act(async()=>root.render(React.createElement(c.RoleAssessmentTemplateControls,{setup,jobTitle:'Data Analyst',value:{questions:[],editor:null},onChange:v=>changed=v,onBusy:()=>{}})));
 await click(document.querySelector('input'));assert.equal(calls,1);assert.equal(changed.questions.length,1);assert.ok(changed.replaceSelection);
 console.log('PASS explicit OA opt-in loads complete private template with replace-selection semantics');
 await act(async()=>root.render(React.createElement(c.RoleAssessmentTemplateControls,{setup,jobTitle:'Data Analyst',value:{questions:changed.questions,editor:null},onChange:v=>changed=v,onBusy:()=>{}})));
 const templateButton=()=>[...document.querySelectorAll('button')].find(n=>n.textContent.includes('OA template')||n.textContent.includes('Confirm replacement'));
 await click(templateButton());assert.equal(calls,1);assert.ok(templateButton().textContent.includes('Confirm replacement'));
 await click(templateButton());assert.equal(calls,2);
 console.log('PASS replacing an existing selection requires a deliberate second click');
 const css=await readFile('src/shared/styles/portal-theme.css','utf8');
 assert.match(css,/a\[href\],summary/);assert.match(css,/:active \{ filter:brightness\(\.85\)/);
 assert.match(css,/:focus-visible/);assert.match(css,/-webkit-tap-highlight-color/);
 console.log('PASS shared mouse, touch, keyboard and pressed feedback covers site controls');
 let generationGets=0,resolvePost,readyCount=0;
 const aiSetup={configuration:{pipeline:{oa_enabled:false},oa:{sections:[]}},catalog:{prices:{ai_jd:10,oa_setup:0}}};
 function DraftHarness(){const [generation,setGeneration]=React.useState(null);return React.createElement(c.JobAIDraftBuilder,{mode:'ai',onMode:()=>{},setup:aiSetup,prompt:'Synthetic test role',onPrompt:()=>{},generation,onGeneration:setGeneration,onReady:()=>readyCount++,onBusy:()=>{},isOpen:true});}
 globalThis.fetch=async(url,options={})=>{
   if(options.method==='POST')return new Promise(resolve=>resolvePost=()=>resolve(new Response(JSON.stringify({generation:{id:'draft-ack',state:'queued'}}),{status:200})));
   generationGets++;return new Response(JSON.stringify({generation:{id:'draft-ack',state:'completed',questions:[],job_data:{},configuration:aiSetup.configuration}}),{status:200});
 };
 await act(async()=>root.render(React.createElement(DraftHarness)));
 await click([...document.querySelectorAll('button')].find(n=>n.textContent==='Generate JD'));
 assert.equal(generationGets,0,'Status polling must wait for POST acknowledgement');
 await act(async()=>{resolvePost();await new Promise(r=>setTimeout(r,30));});
 assert.equal(readyCount,1);assert.ok(generationGets>=1);
 console.log('PASS generation does not poll before acknowledgement and applies a completed draft once');
 globalThis.fetch=async()=>new Response(JSON.stringify({generation:{id:'draft-failed',state:'failed',error_code:'providers_unavailable',credits_released:true}}),{status:200});
 await act(async()=>root.render(React.createElement(DraftHarness,{key:'failure'})));
 await click([...document.querySelectorAll('button')].find(n=>n.textContent==='Generate JD'));
 assert.ok(document.querySelector('[role="alert"]').textContent.includes('funding'));
 assert.ok(![...document.querySelectorAll('[role="status"]')].some(n=>n.textContent.includes('Preparing JD')));
 console.log('PASS failed generation shows provider guidance without stale progress');



}finally{await act(async()=>root.unmount());dom.window.close();await rm(tmp,{recursive:true,force:true});}

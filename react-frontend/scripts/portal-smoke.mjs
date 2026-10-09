// Offline regression checks: real React components and compiled CSS, with fixture APIs.
// jsdom checks rendering/state/styles; it cannot verify browser layout geometry.
import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "esbuild";
import { JSDOM } from "jsdom";
import postcss from "postcss";

const cwd = process.cwd();
const tmp = await mkdtemp(path.join(cwd, ".portal-smoke-"));
assert.ok(path.resolve(tmp).startsWith(path.resolve(cwd) + path.sep) && path.basename(tmp).startsWith(".portal-smoke-"));
const dom = new JSDOM('<!doctype html><html><head></head><body><div id="root"></div></body></html>', {url:"http://localhost:3000"});
const win = dom.window;
for (const key of ["window","document","navigator","sessionStorage","localStorage","HTMLElement","Element","Node","Event","MouseEvent","CustomEvent","getComputedStyle"]) Object.defineProperty(globalThis,key,{value:win[key],configurable:true,writable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
win.matchMedia = () => ({matches:false,addEventListener(){},removeEventListener(){},addListener(){},removeListener(){}});
win.scrollTo=()=>{}; win.open=()=>{}; win.HTMLElement.prototype.scrollIntoView=()=>{};
globalThis.ResizeObserver=class {observe(){} unobserve(){} disconnect(){}};
const React = await import("react");
const {act} = React;
const {createRoot} = await import("react-dom/client");
const {MemoryRouter,useNavigate,useLocation,Routes,Route} = await import("react-router-dom");
const axios = (await import("axios")).default;
const e = React.createElement;
const originalLog = console.log, originalError = console.error;
let errors=[]; console.log=()=>{}; console.error=(...args)=>errors.push(args.map(String).join(" "));
let interviewTerminal=false;
let role="candidate", meStatus=200, costFailure=false, applicationsFailure=false, profileFailure=false, profileSaveFailure=false, previewFailure=false, appStatus="interviewed", apiCalls=[];
win.URL.createObjectURL=()=>"blob:http://localhost:3000/fixture-cv";win.URL.revokeObjectURL=()=>{};
const job={_id:"job-1",title:"Software Engineer",department:"Engineering",location:"Remote",type:"Full-time",experience:"2-4 years",salary:"Competitive",status:"active",deadline:"2027-01-01",skills:["React"],description:"Build reliable products.",responsibilities:["Build features"],requirements:["React experience"],benefits:["Flexible work"]};
const application={_id:"application-1",job_id:job._id,job_title:job.title,student_name:"Fixture Candidate",student_email:"fixture@example.test",status:"interviewed",applied_at:"2026-10-01T10:00:00Z",cv_score:0,interview_score:0,proctoring_score:0,report_available:true,job_details:{...job,company:"Fixture Company"}};
function fixture(url) {
  const pathname=new URL(String(url),"http://localhost:5000").pathname;
  if (/\/interviews\/[^/]+\/session$/.test(pathname)) return {session_id:"fixture-interview",current_question:"Describe a recent project.",max_questions:10,question_count:1,dual_proctoring_required:true,...(interviewTerminal?{status:"completed",interview_complete:true,interview_score:0,cv_score:0,proctoring_score:0}:{})};
  if (pathname.endsWith("/me") || pathname.endsWith("/profile")) return {name:"Fixture User",email:"fixture@example.test",user_type:role,is_verified:true,company_name:"Fixture Company",company_industry:"Technology",company_location:"Remote",company_size:"1-10 employees",company_description:"Build products.",education:[],work_experience:[],skills:[]};
  if (pathname.endsWith("/jobs")) return [job];
  if (pathname.endsWith("/applications")) return [{...application,status:appStatus}];
  if (pathname.endsWith("/jobs/job-1")) return job;
  if (pathname.endsWith("/applications/application-1")) return application;
  if (pathname.includes("interview-report")) return {interview_score:0,cv_score:0,proctoring_score:0,evaluation:"Fixture feedback"};
  if (pathname.endsWith("/saved-jobs")) return {saved_jobs:[],jobs:[]};
  if (pathname.endsWith("/practice-sessions")) return [];
  if (pathname.endsWith("/cv/list")) return {cvs:[]};
  if (pathname.endsWith("/cv-details")) return {};
  if (pathname.includes("subscription")) return {subscription:null};
  if (pathname.includes("wallet")) return {success:true,wallet:{credits_remaining:0,credits_balance:0},balance:0};
  if (pathname.includes("cost-statistics")) return costFailure ? {success:false} : {success:true,data:{recruiter:{name:"Fixture Recruiter",joinedDate:"2026-10-01"},plan:{name:"Recruiter Wallet",credits_remaining:100,credits_allocated:100,credits_used:0},usageHistory:[],recentActivity:[],rechargeHistory:[],summary:{totalJobs:1,totalApplicants:1,totalInterviews:1,activeJobs:1},monthlyPipeline:[]}};
  return {};
}
globalThis.fetch=win.fetch=async (url,options={})=>{
  apiCalls.push({url:String(url),options});
  const pathname=new URL(String(url),"http://localhost:5000").pathname;
  const status=pathname.endsWith("/me")?meStatus:applicationsFailure&&pathname.endsWith("/applications")?503:(profileFailure || profileSaveFailure&&options.method==="PUT")&&pathname.endsWith("/profile")?503:previewFailure&&pathname.endsWith("/cv")?503:200;
  return new Response(JSON.stringify(fixture(url)),{status,headers:{"Content-Type":"application/json"}});
};
axios.defaults.adapter=async config=>({data:fixture(config.url),status:200,statusText:"OK",headers:{},config});
function session(nextRole="candidate") { interviewTerminal=false; role=nextRole; meStatus=200; costFailure=false; applicationsFailure=false; profileFailure=false; profileSaveFailure=false; previewFailure=false; appStatus="interviewed"; apiCalls=[]; sessionStorage.clear(); sessionStorage.setItem("companyxyz-token","fixture-token"); sessionStorage.setItem("companyxyz-user",JSON.stringify({userType:role,user_type:role,name:"Fixture User",is_verified:true})); }
let root, navigation, currentLocation, passes=0;
function Probe(){ navigation=useNavigate(); currentLocation=useLocation(); return null; }
let compiled;
async function mount(component,route="/",options={}) {
  if(root) await act(async()=>root.unmount());
  errors=[]; session(options.role || "candidate"); if(options.interviewTerminal)interviewTerminal=true; if(options.status) meStatus=options.status; if(options.costFailure)costFailure=true; if(options.applicationsFailure)applicationsFailure=true; if(options.profileFailure)profileFailure=true; if(options.appStatus)appStatus=options.appStatus;
  document.getElementById("root").innerHTML="";
  root=createRoot(document.getElementById("root"));
  await act(async()=>root.render(e(compiled.AppProviders,null,e(MemoryRouter,{initialEntries:[route]},e(Probe),component))));
  await settle();
  if(options.applicationsFailure)errors=errors.filter(msg=>!msg.startsWith("Error loading applications:"));
  if(options.profileFailure)errors=errors.filter(msg=>!msg.startsWith("Error loading profile:"));
  assert.equal(errors.filter(msg=>!msg.includes("not wrapped in act")).length,0,errors.join("\n"));
}
async function settle(){ await act(async()=>{await new Promise(resolve=>setTimeout(resolve,90));}); }
function text(){return document.body.textContent;}
function button(label){return [...document.querySelectorAll("button")].find(node=>node.textContent.trim()===label);}
async function click(node){assert.ok(node,"Expected clickable control");await act(async()=>node.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true})));await settle();}
async function go(to){await act(async()=>navigation(to));await settle();}
async function check(name,fn,{expectedFailure=false}={}){ if(process.env.PORTAL_SMOKE_FILTER && !new RegExp(process.env.PORTAL_SMOKE_FILTER).test(name))return; await fn(); if(!expectedFailure)assert.equal(errors.filter(msg=>!msg.includes("not wrapped in act")).length,0,errors.join("\n")); passes++;originalLog(`PASS ${name}`); }
let css;
function mediaMatches(query,width,height) {
  if(query.includes("prefers-reduced-motion: reduce") || query.includes("prefers-color-scheme: dark")) return false;
  return [...query.matchAll(/\((min|max)-(width|height):\s*([\d.]+)(px|rem)\)/g)].every(([,type,axis,value,unit])=>{const size=axis==="width"?width:height;const bound=+value*(unit==="rem"?16:1);return type==="min"?size>=bound:size<=bound;});
}
function styles(width=1366,height=768) {
  const tree=postcss.parse(css), vars={};
  tree.walkRules(rule=>{if(rule.selector===":root")rule.walkDecls(decl=>{if(decl.prop.startsWith("--"))vars[decl.prop]=decl.value;});});
  tree.walkAtRules(rule=>{if(rule.name==="media"){if(mediaMatches(rule.params,width,height))rule.replaceWith(...rule.nodes);else rule.remove();}else if(["import","font-face","charset","keyframes"].includes(rule.name))rule.remove();});
  tree.walkDecls(decl=>{for(let i=0;i<5;i++)decl.value=decl.value.replace(/var\((--[\w-]+)(?:,\s*([^()]+))?\)/g,(_,key,fallback)=>vars[key]||fallback||"inherit");});
  tree.walkRules(rule=>rule.selector=rule.selector.replace(/:hover/g,'[data-style-hover]').replace(/:focus-visible/g,'[data-style-focus]'));
  document.querySelector("#smoke-css")?.remove();const style=document.createElement("style");style.id="smoke-css";style.textContent=tree.toString();document.head.append(style);
}
function rgb(value){return (value.match(/[\d.]+/g)||[]).slice(0,3).map(Number);}
function luminance(values){return values.map(value=>{value/=255;return value<=.04045?value/12.92:((value+.055)/1.055)**2.4;}).reduce((sum,value,index)=>sum+value*[.2126,.7152,.0722][index],0);}
function readable(node,bg=[255,255,255]) {const fg=luminance(rgb(getComputedStyle(node).color)),back=luminance(bg);assert.ok((Math.max(fg,back)+.05)/(Math.min(fg,back)+.05)>=4.5,`Low contrast: ${node.textContent} ${getComputedStyle(node).color}`);}
try {
  const exports={Chat:"features/interview/pages/Chat",MobileRecorder:"features/interview/pages/MobileRecorder",KioskLaunchGuide:"features/interview/components/KioskLaunchGuide",ForgotPassword:"features/auth/pages/ForgotPassword",ResetPassword:"features/auth/pages/ResetPassword",VerifyEmail:"features/auth/pages/VerifyEmail",PaymentSuccess:"features/payment/pages/PaymentSuccess",PaymentCancel:"features/payment/pages/PaymentCancel",SubscriptionPlans:"features/payment/pages/SubscriptionPlans",CandidateSubscriptionPlans:"features/payment/pages/CandidateSubscriptionPlans",AdminLayout:"features/admin/components/AdminLayout",AppProviders:"app/providers",AppRoutes:"app/routes",Login:"features/auth/pages/Login",Register:"features/auth/pages/Register",RecruiterOnboarding:"features/auth/pages/RecruiterOnboarding",CVDetailsForm:"features/candidate/components/CVDetailsForm",CVDetailsModal:"features/candidate/components/CVDetailsModal",CVSelectionModal:"features/candidate/components/CVSelectionModal",Profile:"features/candidate/pages/Profile",Applications:"features/candidate/pages/Applications",Dashboard:"features/candidate/pages/Dashboard",Practice:"features/candidate/pages/Practice",CandidateCostStatistics:"features/candidate/pages/CandidateCostStatistics",TeamPage:"features/recruiter/pages/TeamPage",RecruiterDashboard:"features/recruiter/pages/RecruiterDashboard",RecruiterCostStatistics:"features/recruiter/pages/RecruiterCostStatistics",RecruiterTeam:"features/recruiter/pages/RecruiterTeam",Navbar:"shared/components/layout/Navbar",Layout:"shared/components/layout/Layout",ErrorBoundary:"shared/components/ui/ErrorBoundary",InterviewReportModal:"features/interview/components/InterviewReportModal",CandidateCard:"features/recruiter/components/CandidateCard",JobCreationModal:"features/recruiter/components/JobCreationModal",JobEditModal:"features/recruiter/components/JobEditModal",JobDetailsModal:"features/recruiter/components/JobDetailsModal",JDDetailsModal:"features/recruiter/components/JDDetailsModal",InviteCandidatesModal:"features/recruiter/components/InviteCandidatesModal"};
  const entry=Object.entries(exports).map(([name,file])=>`export {${name==="AppProviders"?name:"default as "+name}} from ${JSON.stringify(file)};`).join("\n");
  const output=await build({stdin:{contents:entry,resolveDir:cwd,loader:"jsx"},bundle:true,write:false,outfile:path.join(tmp,"bundle.mjs"),platform:"node",format:"esm",packages:"external",alias:Object.fromEntries(["app","features","shared","assets"].map(name=>[name,path.join(cwd,"src",name)])),loader:{".js":"jsx",".png":"dataurl",".svg":"dataurl",".jpg":"dataurl",".jpeg":"dataurl",".webp":"dataurl"},define:{"process.env":JSON.stringify({NODE_ENV:"test",REACT_APP_API_URL:"http://localhost:5000",REACT_APP_GOOGLE_CLIENT_ID:"fixture-client"})},plugins:[{name:"fixtures",setup(plugin){plugin.onLoad({filter:/\.css$/},async({path:file})=>({contents:await readFile(file,"utf8"),loader:file.endsWith(".module.css")?"local-css":"css",resolveDir:path.dirname(file)}));plugin.onResolve({filter:/^(react-chartjs-2|socket.io-client)$/},args=>({path:args.path,namespace:"fixture"}));plugin.onLoad({filter:/.*/,namespace:"fixture"},args=>({contents:args.path==="socket.io-client"?`export const io=()=>({connected:false,on(){return this},off(){return this},emit(){return this},disconnect(){},connect(){}}); export default io;`:`import React from "react"; export const Line=()=>React.createElement("canvas");export const Bar=Line;export const Doughnut=Line;export const Pie=Line;`,loader:"js",resolveDir:cwd}));}}]});
  await writeFile(path.join(tmp,"bundle.mjs"),output.outputFiles.find(file=>file.path.endsWith(".mjs")).text);
  compiled=await import(pathToFileURL(path.join(tmp,"bundle.mjs")));
  css=(await readFile("src/shared/styles/portal-theme.css","utf8"))+(await readFile("src/App.css","utf8"))+output.outputFiles.find(file=>file.path.endsWith(".css")).text;
  await check("closed null report never crashes a parent page",async()=>{await mount(e(compiled.InterviewReportModal,{isOpen:false,report:null}));assert.equal(text(),"");});
  await check("legacy and structured reports render; zero scores are preserved",async()=>{
    for(const evaluation of [null,"null","[]","Legacy feedback",{qualitative_assessment:{summary:"Structured feedback"},per_question_evaluations:[null]},{qualitative_assessment:{summary:{feedback:"Structured nested feedback"}}}]){
      await mount(e(compiled.InterviewReportModal,{isOpen:true,onClose(){},report:{evaluation,interview_score:0,cv_score:0,proctoring_score:0,proctoring_report:{events:"legacy warning",missing_checks:"camera"}}}));assert.equal(document.querySelectorAll('[role="dialog"]').length,1);assert.equal((text().match(/0%/g)||[]).length,3);
      await click(button("Transcript"));await click(button("Proctoring"));await click(button("Report data"));
    }
  });
  await check("root error boundary works outside any router",async()=>{
    if(root)await act(async()=>root.unmount());root=createRoot(document.getElementById("root"));errors=[];
    function Broken(){throw new Error("Fixture render failure");}
    await act(async()=>root.render(e(compiled.ErrorBoundary,null,e(Broken))));assert.ok(text().includes("Something went wrong"));assert.equal(document.querySelector('a[href="/"]').textContent,"Go to Homepage");assert.ok(!errors.some(msg=>msg.includes("basename")));
  },{expectedFailure:true});
  await check("applications opens independently without profile or CV management",async()=>{
    await mount(e(compiled.AppRoutes),"/applications");assert.ok(text().includes("Software Engineer"));assert.ok(!text().includes("CV Information"));assert.ok(!text().includes("Personal details"));assert.ok(!text().includes("Change Photo"));assert.ok(!text().includes("Application overview"));assert.equal(document.querySelectorAll('nav[aria-label="Candidate sections"] a').length,6);assert.ok(!apiCalls.some(call=>call.url.includes("cv/list")));
  });
  await check("profile navbar and browser history preserve separate workflows",async()=>{
    await click(document.querySelector('nav a[href="/profile"]'));assert.ok(text().includes("Personal details"));assert.ok(text().includes("CV Information"));assert.ok(text().includes("Application overview"));assert.ok(!text().includes("Software Engineer"));assert.ok(!document.querySelector('[class*="tabNavigation"]'));assert.ok(document.querySelector('nav a[href="/profile"][aria-current="page"]'));
    await click(document.querySelector('nav a[href="/applications"]'));assert.ok(text().includes("Software Engineer"));await go(-1);assert.ok(text().includes("Personal details"));await go(1);assert.ok(text().includes("Software Engineer"));
  });
  await check("legacy candidate hash/query bookmarks redirect before mounting profile features",async()=>{
    for(const old of ["/profile#applications","/profile?tab=applications&source=email"]){await mount(e(compiled.AppRoutes),old);assert.equal(currentLocation.pathname,"/applications");assert.ok(text().includes("Software Engineer"));assert.ok(!apiCalls.some(call=>call.url.includes("cv/list")));}
    assert.equal(currentLocation.search,"?source=email");await go("/profile?tab=applications#bio");assert.equal(currentLocation.pathname,"/profile");assert.ok(text().includes("Personal details"));
  });
  await check("application filters, report and authenticated CV preview work independently",async()=>{
    await mount(e(compiled.AppRoutes),"/applications");const select=document.querySelector('#statusFilter');await act(async()=>{select.value="shortlisted";select.dispatchEvent(new Event("change",{bubbles:true}));});await settle();assert.ok(text().includes("No applications match"));await click(button("Clear Filters"));assert.ok(text().includes("Software Engineer"));assert.equal((text().match(/0%/g)||[]).length,3);await click(button("Report"));assert.ok(document.querySelector('[role="dialog"]'));await click(document.querySelector('button[aria-label="Close interview report"]'));await click(button("View CV"));assert.ok(document.querySelector('iframe[title="Uploaded CV"]'));const call=apiCalls.find(call=>call.url.endsWith("/applications/application-1/cv"));assert.equal(call.options.headers.Authorization,"Bearer fixture-token");assert.ok(!call.url.includes("token="));await click(button("Close"));assert.ok(!document.querySelector('iframe'));
  });
  await check("shortlisted candidates can open the kiosk setup guide",async()=>{await mount(e(compiled.AppRoutes),"/applications",{appStatus:"shortlisted"});await click(button("Give Interview"));assert.ok(text().includes("GenHire Secure Browser"));});
  await check("application load failure shows Retry instead of a false empty state",async()=>{await mount(e(compiled.Applications),"/applications",{applicationsFailure:true});assert.ok(text().includes("We could not load your applications"));assert.ok(!text().includes("No job applications yet"));applicationsFailure=false;await click(button("Retry"));assert.ok(text().includes("Software Engineer"));});
  await check("profile load failure prevents saving an empty profile and retry recovers",async()=>{await mount(e(compiled.Profile),"/profile",{profileFailure:true});assert.ok(!button("Update Profile"));assert.ok(text().includes("We could not load your profile"));profileFailure=false;await click(button("Retry"));assert.ok(button("Update Profile"));assert.ok(button("Upload CV").disabled);});
  await check("profile saves once for repeated submissions and retains fields on failure",async()=>{
    await mount(e(compiled.Profile),"/profile");const form=document.querySelector('input[id="profile-name"]').closest("form");await act(async()=>{form.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}));form.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}));});await settle();assert.equal(apiCalls.filter(call=>call.options.method==="PUT").length,1);assert.ok(text().includes("Profile updated successfully"));profileSaveFailure=true;await act(async()=>form.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true})));await settle();assert.ok(text().includes("Failed to update profile"));assert.equal(document.querySelector('#profile-name').value,"Fixture User");assert.ok(!button("Update Profile").disabled);
  });
  await check("failed CV preview can retry without leaving applications",async()=>{await mount(e(compiled.Applications),"/applications");previewFailure=true;await click(button("View CV"));assert.ok(text().includes("CV is unavailable"));assert.ok(!document.querySelector("iframe"));previewFailure=false;await click(button("Retry"));assert.ok(document.querySelector('iframe[title="Uploaded CV"]'));await click(button("Close"));});
  await check("candidate CV dialogs have compact readable headers",async()=>{
    for(const [name,props] of [["CVDetailsForm",{onSave:async()=>true,onClose(){}}],["CVDetailsModal",{isOpen:true,cvDetails:{},onClose(){}}],["CVSelectionModal",{isOpen:true,onClose(){},onSelect(){},onSubmit(){}}]]){await mount(e(compiled[name],props));styles();const heading=document.querySelector("h2");assert.ok(heading);readable(heading);assert.ok(parseFloat(getComputedStyle(heading).fontSize)<=22);styles(390,844);assert.ok(parseFloat(getComputedStyle(heading).fontSize)<=20);}
  });
  for(const [tab,title] of [["overview","Dashboard Overview"],["jobs","Job Postings"],["candidates","Candidate Management"],["profile","Company Profile"]]) await check(`recruiter ${tab} page renders`,async()=>{await mount(e(compiled.AppRoutes),`/recruiter/dashboard?tab=${tab}`,{role:"recruiter"});assert.ok(text().includes(title),text().slice(0,400));assert.equal(document.querySelectorAll('nav[aria-label="Recruiter sections"] a').length,6);assert.ok(document.querySelector(`nav a[href$="tab=${tab}"][aria-current="page"]`));});
  await check("recruiter navbar, history, default and legacy query select the right tab",async()=>{
    await click(document.querySelector('nav a[href$="tab=jobs"]'));assert.ok(text().includes("Job Postings"));await go(-1);assert.ok(text().includes("Company Profile"));await go("/recruiter/dashboard");assert.ok(text().includes("Dashboard Overview"));await go("/recruiter-dashboard?tab=candidates");assert.equal(currentLocation.search,"?tab=candidates");assert.ok(text().includes("Candidate Management"));
  });
  await check("View Candidates filters by exact job ID rather than title",async()=>{await mount(e(compiled.RecruiterDashboard),"/recruiter/dashboard?tab=jobs",{role:"recruiter"});await click([...document.querySelectorAll("button")].find(node=>node.textContent.includes("View Candidates")));assert.ok(text().includes("Fixture Candidate"));assert.ok([...document.querySelectorAll("select")].some(select=>select.value===job._id));});
  await check("mobile menu offers recruiter sections and closes on navigation",async()=>{await click(document.querySelector('button[aria-controls="workspace-menu"]'));assert.equal(document.getElementById("workspace-menu").hidden,false);assert.equal(document.querySelectorAll('#workspace-menu a').length>=6,true);await click(document.querySelector('#workspace-menu a[href$="tab=profile"]'));assert.equal(document.getElementById("workspace-menu").hidden,true);});
  await check("incomplete candidate cards keep actions safe and values honest",async()=>{await mount(e(compiled.CandidateCard,{application:{...application,student_name:null,applied_at:"invalid"},updateApplicationStatus(){},viewInterviewReport(){},viewProctoringReport(){}}));assert.ok(text().includes("Candidate"));assert.ok(text().includes("Not available"));assert.ok(button("View CV").disabled);assert.equal((text().match(/0%/g)||[]).length,3);});
  for(const [name,props] of [["InviteCandidatesModal",{isOpen:true,onClose(){},job}],["JobCreationModal",{isOpen:true,onClose(){},onJobCreate:async()=>true,showToast(){}}],["JobEditModal",{isOpen:true,onClose(){},job,onSave(){},showToast(){}}],["JobDetailsModal",{isOpen:true,onClose(){},job}],["JDDetailsModal",{isOpen:true,onClose(){},session:{job_details:job},getRoleName:()=>"Software Engineer",getRoleIcon:()=>"fa-code"}]]) await check(`${name} has a readable compact header`,async()=>{await mount(e(compiled[name],props),"/",{role:"recruiter"});styles();const heading=document.querySelector("h2");assert.ok(heading);readable(heading);assert.ok(parseFloat(getComputedStyle(heading).fontSize)<=26);});
  await check("recruiter cost and team pages open with the shared navbar",async()=>{for(const name of ["RecruiterCostStatistics","RecruiterTeam"]){await mount(e(compiled[name]),"/recruiter/"+(name==="RecruiterTeam"?"team":"cost-statistics"),{role:"recruiter"});assert.equal(document.querySelectorAll('nav[aria-label="Recruiter sections"] a').length,6);assert.ok(!text().includes("Something went wrong"));}});
  await check("login and both signups share font sizes, control heights and purple actions",async()=>{
    const sizes=[];
    for(const name of ["Login","Register","RecruiterOnboarding"]){await mount(e(compiled[name]));styles();const mobileBrand=document.querySelector('a[class*="mobileBrand"]');if(mobileBrand)assert.equal(getComputedStyle(mobileBrand).display,"none",`${name} desktop mobile logo`);const input=document.querySelector('input:not([type="checkbox"]):not([type="hidden"])');assert.ok(input);const size=getComputedStyle(input);sizes.push([size.fontSize,size.height]);assert.equal(size.fontSize,"14px");assert.equal(size.height,"49px",`${name} input height`);readable(input);const h2=document.querySelector("section h2")||document.querySelector("section h1");if(h2)readable(h2);const cta=document.querySelector('button[type="submit"]');if(cta&&!cta.disabled){cta.setAttribute("data-style-hover","");assert.deepEqual(rgb(getComputedStyle(cta).color),[255,255,255]);}
      for(const [width,height] of [[909,642],[390,844]]){styles(width,height);if(mobileBrand)assert.equal(getComputedStyle(mobileBrand).display,width<=760?"inline-flex":"none",`${name} responsive logo`);const panel=document.querySelector("aside");if(panel)assert.equal(getComputedStyle(panel).display,width<=760?"none":"flex");assert.equal(getComputedStyle(input).fontSize,width<=600?"16px":"14px");}
    }assert.deepEqual(sizes[0],sizes[1]);assert.deepEqual(sizes[0],sizes[2]);
  });
  await check("recruiter content uses one scale and responsive card structure",async()=>{await mount(e(compiled.RecruiterDashboard),"/recruiter/dashboard?tab=jobs",{role:"recruiter"});styles();const title=[...document.querySelectorAll("h1")].find(node=>node.textContent.includes("Job Postings"));readable(title);assert.equal(getComputedStyle(title).fontSize,"30px");const cta=button("Create New Job");assert.ok(cta);cta.setAttribute("data-style-hover","");assert.deepEqual(rgb(getComputedStyle(cta).color),[255,255,255]);await go("/recruiter/dashboard?tab=candidates");styles(390,844);const card=document.querySelector('[class*="candidateCard"]');assert.equal(getComputedStyle(card).display,"flex");});
  await check("company profile uses a readable summary and preserves edit/cancel",async()=>{await mount(e(compiled.RecruiterDashboard),"/recruiter/dashboard?tab=profile",{role:"recruiter"});assert.ok(document.querySelector("dl"));assert.equal(document.querySelectorAll("input").length,0);await click(button("Edit Profile"));assert.ok(document.querySelector('#company-companyName'));assert.ok(document.querySelector('#company-email').disabled);await click(button("Cancel"));assert.ok(document.querySelector("dl"));assert.ok(!document.querySelector('#company-companyName'));});
  await check("candidate jobs, profile, applications, practice and team share compact lavender headers",async()=>{
    for(const [name,route] of [["Dashboard","/dashboard"],["Profile","/profile"],["Applications","/applications"],["Practice","/practice"],["TeamPage","/team"]]){
      await mount(e(compiled[name]),route);for(const [width,height] of [[1366,768],[909,642],[390,844]]){styles(width,height);const header=document.querySelector('[class*="PortalPageHeader_header"]');assert.ok(header,`${name} header`);assert.ok(/#eef2ff|238,\s*242,\s*255/.test(getComputedStyle(header).backgroundImage),`${name} header background: ${getComputedStyle(header).backgroundImage}`);const heading=header.querySelector("h1");readable(heading);assert.equal(getComputedStyle(heading).fontSize,width<=700?"26px":"30px");if(["Dashboard","Practice"].includes(name)){const wrapper=document.querySelector('[class*="'+(name==="Dashboard"?"dashboardContainer":"practiceContainer")+'"]');assert.equal(getComputedStyle(wrapper).paddingTop,"0px");}}
      if(name==="Practice"){const roleCard=document.querySelector('[class*="roleCard"]');await act(async()=>roleCard.dispatchEvent(new win.KeyboardEvent("keydown",{key:"Enter",bubbles:true,cancelable:true})));assert.equal(roleCard.getAttribute("aria-pressed"),"true");}
    }
  });
  await check("candidate usage failures show Retry and preserve the wallet session",async()=>{await mount(e(compiled.CandidateCostStatistics),"/candidate/cost-statistics",{costFailure:true});assert.ok(text().includes("Unable to load usage"));assert.ok(!text().includes("Practice Credits Used"));costFailure=false;await click(button("Retry"));assert.ok(text().includes("Cost statistics"));assert.ok(sessionStorage.getItem("companyxyz-token"));});
  await check("candidate job/application details keep navbar context and return to applications",async()=>{await mount(e(compiled.AppRoutes),"/applications/application-1");assert.ok(text().includes("Application Submitted"));assert.ok(document.querySelector('nav a[href="/applications"][aria-current="page"]'));await click(button("Back to Applications"));assert.equal(currentLocation.pathname,"/applications");await go("/jobs/job-1");assert.ok(text().includes("Software Engineer"));assert.ok(document.querySelector('nav a[href="/dashboard"][aria-current="page"]'));});
  await check("temporary verification failure preserves the session and can retry",async()=>{await mount(e(Routes,null,e(Route,{element:e(compiled.Layout)},e(Route,{path:"/profile",element:e("div",null,"Workspace recovered")}))),"/profile",{status:503});assert.ok(text().includes("Unable to open your workspace"));assert.equal(sessionStorage.getItem("companyxyz-token"),"fixture-token");meStatus=200;await click(button("Retry"));assert.ok(text().includes("Workspace recovered"));});
  await check("usage API failure is shown honestly and retry recovers",async()=>{await mount(e(compiled.RecruiterCostStatistics),"/recruiter/cost-statistics",{role:"recruiter",costFailure:true});assert.ok(text().includes("Unable to load usage"));assert.ok(!text().includes("New Recruiter"));assert.ok(sessionStorage.getItem("companyxyz-token"));costFailure=false;await click(button("Retry"));assert.ok(text().includes("Cost statistics"));});
  await check("invalid session redirects to login and clears credentials",async()=>{await mount(e(Routes,null,e(Route,{element:e(compiled.Layout)},e(Route,{path:"/profile",element:e("div",null,"Protected")})),e(Route,{path:"/login",element:e("div",null,"Sign in here")})),"/profile",{status:401});assert.ok(text().includes("Sign in here"));assert.equal(sessionStorage.getItem("companyxyz-token"),null);});
  await check("interview preparation shares purple actions and handles unavailable media",async()=>{
    await mount(e(compiled.Chat,{interviewId:"fixture-interview"}),"/interviews/fixture-interview");assert.ok(text().includes("Check your devices"));assert.ok(text().includes("Connect your phone"));assert.ok(button("Enable camera and microphone"));assert.ok(button("Continue").disabled);
    styles(909,642);const shell=document.querySelector("main");assert.ok(getComputedStyle(shell).fontFamily.includes("Segoe UI"));const action=button("Enable camera and microphone");assert.equal(getComputedStyle(action).minHeight,"44px");await click(action);assert.ok(document.querySelector('[role="alert"]'));assert.ok(button("Continue").disabled);
  });
  await check("completed interview retains three zero scores and themed report",async()=>{
    await mount(e(compiled.Chat,{interviewId:"fixture-interview"}),"/interviews/fixture-interview",{interviewTerminal:true});assert.equal((text().match(/0%/g)||[]).length,3);await click(button("View evaluation and transcript"));styles(390,844);readable(document.querySelector('[role="dialog"] h2'));await click(document.querySelector('button[aria-label="Close interview report"]'));
  });
  await check("mobile companion rejects missing pairing token before camera access",async()=>{
    await mount(e(Routes,null,e(Route,{path:"/mobile-camera/:sessionId",element:e(compiled.MobileRecorder)})),"/mobile-camera/fixture-interview");assert.ok(text().includes("Scan the QR code"));assert.ok(document.querySelector('[role="alert"]'));assert.ok(!button("Enable camera and microphone"));styles(390,844);readable(document.querySelector("h1"));
  });
  await check("installation guide requires confirmation and supports keyboard close",async()=>{
    localStorage.removeItem("genhire:kiosk-installed:v1");let opens=0, closes=0;await mount(e(compiled.KioskLaunchGuide,{isOpen:true,onClose(){closes++;},onOpen(){opens++;}}));assert.ok(button("Open Secure Browser").disabled);await click(document.querySelector('input[type="checkbox"]'));assert.ok(!button("Open Secure Browser").disabled);await click(button("Open Secure Browser"));assert.equal(opens,1);await act(async()=>document.dispatchEvent(new win.KeyboardEvent("keydown",{key:"Escape",bubbles:true})));assert.equal(closes,1);
  });
  await check("account recovery pages use shared compact authentication controls",async()=>{
    for(const [name,route] of [["ForgotPassword","/forgot-password"],["ResetPassword","/reset-password?token=fixture"],["VerifyEmail","/verify-email"]]){await mount(e(compiled[name]),route);styles(1366,768);readable(document.querySelector("h1"));const input=document.querySelector('input');if(input)assert.equal(getComputedStyle(input).fontSize,"14px");}
    await mount(e(compiled.ResetPassword),"/reset-password");assert.ok(text().includes("Request a new link"));
  });
  await check("payment return pages avoid unverified financial claims and keep role navigation",async()=>{
    for(const role of ["candidate","recruiter"]){await mount(e(compiled.PaymentSuccess),"/payment/success?session_id=fixture-reference",{role});assert.ok(text().includes("Review your payment"));assert.ok(!text().includes("Payment Successful"));assert.equal(document.querySelectorAll('a[href="/support"]').length,0);await click(button("Review wallet history"));assert.equal(currentLocation.pathname,role==="recruiter"?"/recruiter/subscription":"/candidate/subscription");await mount(e(compiled.PaymentCancel),"/payment/cancel",{role});assert.ok(!text().includes("No charges have been made"));await click(button("Return to dashboard"));assert.equal(currentLocation.pathname,role==="recruiter"?"/recruiter/dashboard":"/dashboard");}
  });
  await check("create and edit job use matching accessible monitoring options",async()=>{
    for(const name of ["JobCreationModal","JobEditModal"]){await mount(e(compiled[name],{isOpen:true,onClose(){},onSubmit(){},onSave(){},job,jobDetails:job}));const toggles=[...document.querySelectorAll('input[type="checkbox"][aria-label]')];assert.equal(toggles.length,6);assert.ok(toggles.some(node=>node.getAttribute("aria-label")==="Require a second camera"));assert.ok(text().includes("This signal does not establish AI use"));assert.ok(!text().includes("Smart"));}
  });
  await check("admin navigation uses light readable surfaces and retains section routing",async()=>{
    await mount(e(compiled.AdminLayout,null,e("section",null,"Fixture admin content")),"/admin",{role:"admin"});styles(1366,768);const sidebar=document.querySelector('[class*="AdminLayout_sidebar__"]') || document.querySelector('aside');assert.ok(sidebar);assert.deepEqual(rgb(getComputedStyle(sidebar).backgroundColor),[255,255,255]);const navigationButton=[...document.querySelectorAll('button')].find(node=>node.textContent.trim()==="Candidates");readable(navigationButton);await click(navigationButton);assert.equal(currentLocation.pathname,"/admin/candidates");
  });

  await check("returning kiosk users open first and can reveal reinstall help above navigation",async()=>{
    localStorage.setItem("genhire:kiosk-installed:v1","confirmed");
    await mount(e(compiled.KioskLaunchGuide,{isOpen:true,onClose(){},onOpen(){}}));
    assert.ok(!button("Open Secure Browser").disabled);
    assert.equal(document.querySelectorAll('a[href*=".exe"]').length,0);
    assert.ok(!document.querySelector('input[type="checkbox"]'));
    const dialog=document.querySelector('[role="dialog"]');
    assert.equal(dialog.parentElement.parentElement,document.body);
    styles(390,844);
    assert.equal(getComputedStyle(dialog.parentElement).zIndex,"10060");
    assert.equal(getComputedStyle(dialog).overflowY,"auto");
    assert.equal(document.body.style.overflow,"hidden");
    await click(button("Need to install or reinstall?"));
    assert.ok(document.querySelector('input[type="checkbox"]').checked);
    assert.ok(text().includes("Download for Windows"));
    await click(document.querySelector('input[type="checkbox"]'));
    assert.ok(button("Open Secure Browser").disabled);
    assert.equal(localStorage.getItem("genhire:kiosk-installed:v1"),null);
  });
  await check("installation confirmation survives remount without retaining a session token",async()=>{
    localStorage.removeItem("genhire:kiosk-installed:v1");
    await mount(e(compiled.KioskLaunchGuide,{isOpen:true,onClose(){},onOpen(){}}));
    await click(document.querySelector('input[type="checkbox"]'));
    assert.equal(localStorage.getItem("genhire:kiosk-installed:v1"),"confirmed");
    await mount(e(compiled.KioskLaunchGuide,{isOpen:true,onClose(){},onOpen(){}}));
    assert.ok(text().includes("Open your interview"));
    assert.ok(!button("Open Secure Browser").disabled);
    localStorage.removeItem("genhire:kiosk-installed:v1");
  });
  await check("job description metadata remains readable and compact in the light theme",async()=>{
    await mount(e(compiled.AppRoutes),"/jobs/job-1");
    for(const [width,height] of [[1366,768],[909,642],[390,844]]){
      styles(width,height);
      for(const key of ["company","location","jobType"]){
        const node=[...document.querySelectorAll("h1 + div > span")][["company","location","jobType"].indexOf(key)];
        assert.ok(node,key);readable(node,[238,242,255]);
      }
      const info=document.querySelector('[class*="infoCard"]');assert.ok(info);assert.equal(getComputedStyle(info).padding,"16px");
    }
  });
  await check("create and edit jobs share purple submit controls and one gaze setting",async()=>{
    for(const name of ["JobCreationModal","JobEditModal"]){
      await mount(e(compiled[name],{isOpen:true,onClose(){},jobData:job,onJobCreate(){},onJobUpdate(){}}));
      styles(1366,768);
      const cta=document.querySelector('button[type="submit"]');assert.ok(cta);
      assert.ok(getComputedStyle(cta).backgroundImage.includes("99, 102, 241")||getComputedStyle(cta).backgroundImage.includes("#6366f1"));
      cta.setAttribute("data-style-hover","");assert.deepEqual(rgb(getComputedStyle(cta).color),[255,255,255]);
      assert.equal(document.querySelectorAll('input[name="gaze_proctoring"]').length,0);
      assert.equal(document.querySelectorAll('input[aria-label="Gaze heatmap"]').length,1);
      assert.ok(!text().includes("instantly"));
    }
  });
  originalLog(`\n${passes} portal regression checks passed. Fixture APIs only; no live accounts modified.`);
} finally {
  if(root)await act(async()=>root.unmount());console.log=originalLog;console.error=originalError;win.close();await rm(tmp,{recursive:true,force:true});
}

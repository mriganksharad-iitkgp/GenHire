import styles from './MockAssessmentPanel.module.css';
import {useNavigate} from 'react-router-dom';
import KioskLaunchGuide, {openKiosk} from 'features/interview/components/KioskLaunchGuide';
import {API_BASE} from 'shared/api/client';
import panelStyles from 'shared/styles/OperationalPanels.module.css';
import React,{useEffect,useRef,useState} from 'react';
import {request,post} from 'shared/api/client';
import PortalPageHeader from 'shared/components/ui/PortalPageHeader';
import BillingOperationsPanel from 'shared/components/billing/BillingOperationsPanel';
import PracticeAssessmentReport from 'features/assessment/components/PracticeAssessmentReport';

  const allowed=(value,type)=>value?.section_availability?.[type]??(type==='mcq'||value?.executor?.available!==false);
  const availablePreset=(value,preset)=>{
    const sections=preset.sections.filter(s=>allowed(value,s.type));
    if(!sections.length) return {sections:[{type:'mcq',count:10,difficulty:{easy:3,medium:5,hard:2},marks:Array(10).fill(1),weight:100,duration_minutes:20}],duration_minutes:20};
    if(sections.length===preset.sections.length) return {sections,duration_minutes:preset.duration_minutes};
    return {sections:sections.map(s=>({...s,weight:100})),duration_minutes:sections.reduce((n,s)=>n+s.duration_minutes,0)};
  };

export default function MockAssessmentPanel(){
  const [catalog,setCatalog]=useState(null),[oa,setOa]=useState(null),[quote,setQuote]=useState(null),[approved,setApproved]=useState(false);
  const [history,setHistory]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  const navigate=useNavigate();
  const [roleOpen,setRoleOpen]=useState(true),[showAllRoles,setShowAllRoles]=useState(false),[launchInvitation,setLaunchInvitation]=useState(null);
  const watched=useRef(null),readyPrompted=useRef(new Set());
  const keys=useRef(new Map());
  const load=async(after)=>{const page=await request(`/practice/assessments${after?`?after=${after}`:''}`);setHistory(old=>({...page,purchases:after?[...old.purchases,...page.purchases]:page.purchases}));};
  const run=async fn=>{setBusy(true);setError('');try{await fn();}catch(err){setError(err.message);}finally{setBusy(false);}};
  const init=async()=>{const value=await request('/practice/assessments/catalog');setCatalog(value);setOa(old=>old||{...value.defaults,...availablePreset(value,value.defaults)});await load();};
  useEffect(()=>{let active=true;Promise.all([request('/practice/assessments/catalog'),request('/practice/assessments')]).then(([c,h])=>{if(active){setCatalog(c);setOa({...c.defaults,...availablePreset(c,c.defaults)});setHistory(h);}}).catch(err=>{if(active)setError(err.message);});return()=>{active=false;};},[]);
  useEffect(()=>{
    const refresh=()=>{if(!document.hidden) load().catch(err=>setError(err.message));};
    window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);
    return()=>{window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh);};
  },[]);
  const pending=history?.purchases.some(p=>['generating','submitted','evaluating'].includes(p.state));
  useEffect(()=>{if(!pending)return;const timer=setInterval(()=>load().catch(err=>setError(err.message)),5000);return()=>clearInterval(timer);},[pending]);
  useEffect(()=>{
    const generating=history?.purchases.find(p=>p.state==='generating');
    if(generating) watched.current=generating.purchase_id;
    const ready=history?.purchases.find(p=>p.purchase_id===watched.current&&p.state==='ready'&&p.invitation_id);
    if(ready&&!readyPrompted.current.has(ready.purchase_id)) {readyPrompted.current.add(ready.purchase_id);setLaunchInvitation(ready.invitation_id);}
  },[history]);
  const launch=async()=>{
    setBusy(true);setError('');
    try {
      const invitation=await request(`/assessment-invitations/${launchInvitation}`);
      if(invitation.integrity_policy?.mode==='browser'){setLaunchInvitation(null);navigate(`/assessments/${launchInvitation}`);return;}
      const grant=await post(`/assessment-invitations/${launchInvitation}/secure-launch`,{operation_key:crypto.randomUUID(),mode:'kiosk'});
      openKiosk({mode:'oa',practice:true,launchCode:grant.launch_code,invitationId:launchInvitation,apiUrl:new URL(API_BASE,window.location.origin).href.replace(/\/api\/?$/,''),webOrigin:window.location.origin,returnToExistingTab:true});
    } catch(err){setError(err.message);throw err;} finally {setBusy(false);}
  };
  const change=patch=>{setOa(old=>({...old,...patch,...(patch.coding_contract==='function'?{languages:old.languages.filter(language=>language!=='c')}:{})}));setQuote(null);setApproved(false);};
  const rebalance=(sections,duration=oa.duration_minutes)=>{
    const n=sections.length;
    return sections.map((s,i)=>({...s,weight:Math.floor(100/n)+(i===0?100%n:0),duration_minutes:Math.floor(duration/n)+(i===0?duration%n:0)}));
  };
  const setCount=(type,value)=>{
    const count=Math.max(0,Math.min(type==='mcq'?100:10,Number(value)||0));
    const old=oa.sections.find(s=>s.type===type);
    const next=oa.sections.filter(s=>s.type!==type);
    if(count) next.push({...old,type,count,difficulty:{easy:Math.floor(count*.3),medium:count-Math.floor(count*.3)-Math.floor(count*.2),hard:Math.floor(count*.2)},marks:Array.from({length:count},(_,i)=>old?.marks[i]??(type==='mcq'?1:30))});
    change({sections:rebalance(next)});
  };
  const updateSection=(index,patch)=>change({sections:oa.sections.map((s,i)=>i===index?{...s,...patch}:s)});
  const difficulty=(index,name,value)=>{const s=oa.sections[index],d={...s.difficulty,[name]:Math.max(0,Number(value)||0)},count=Object.values(d).reduce((a,b)=>a+b,0);updateSection(index,{difficulty:d,count,marks:Array.from({length:Math.min(count,120)},(_,i)=>s.marks[i]??1)});};
  const chooseRole=id=>{const preset=catalog.templates.find(t=>t.id===id);change({template_id:id,...availablePreset(catalog,preset)});setRoleOpen(false);};
  const purchase=async()=>{const signature=quote.quote_id;if(!keys.current.has(signature))keys.current.set(signature,crypto.randomUUID());const p=await post('/practice/assessments',{quote_id:quote.quote_id,operation_key:keys.current.get(signature),accepted:true});watched.current=p.purchase_id;setNotice('Your OA is being prepared in the background. You can leave and return to this page.');setQuote(null);setApproved(false);await load();};
  return <section className={`${panelStyles.panel} ${panelStyles.practice}`} aria-label="Mock online assessments" aria-busy={busy}><PortalPageHeader title="Practice online assessments" eyebrow="Your career workspace" icon="fa-code" subtitle="Choose your role, customize a private OA and learn from objective results and educational feedback." />
    <ol className={styles.flow} aria-label="Practice OA steps"><li>1. Choose your practice</li><li>2. AI prepares questions</li><li>3. Start in Secure Browser</li></ol>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}<button className={styles.refresh} disabled={busy} onClick={()=>run(init)}>Refresh practice availability and history</button>
    {!catalog&&!error&&<p role="status">Loading practice options...</p>}
    {busy&&<p role="status">Updating practice options and history...</p>}
    {catalog&&oa&&<><div className={styles.setupCard}><p className={styles.price}>Base: {catalog.pricing.credits.mock_oa} credits for AI questions, one attempt and feedback. Optional camera costs appear before confirmation.</p>
      {(!catalog.enabled||!catalog.runtime_ready||catalog.purchase_ready===false)&&<p role="status">{catalog.unavailable_reason||'Practice generation is temporarily unavailable. Your settings remain editable.'}</p>}
      {catalog.section_availability?.coding===false&&<p className={styles.availability}>MCQ practice is available. Coding and SQL will appear once their execution services are ready.</p>}
      <details className={styles.rolePicker} open={roleOpen} onToggle={e=>setRoleOpen(e.currentTarget.open)}><summary>Practice role: {catalog.templates.find(t=>t.id===oa.template_id)?.name||oa.template_id}</summary>
        <div className={styles.roleGrid}>{catalog.templates.slice(0,showAllRoles?undefined:8).map(t=><button type="button" className={styles.roleCard} key={t.id} aria-pressed={oa.template_id===t.id} onClick={()=>chooseRole(t.id)}><span aria-hidden="true" className={styles.roleIcon}><i className="fa fa-code"/></span>{t.name}</button>)}</div>
        {catalog.templates.length>8&&<button onClick={()=>setShowAllRoles(!showAllRoles)}>{showAllRoles?'Fewer roles':'More roles'}</button>}
      </details>
      <label>What should the AI include?<textarea maxLength={4000} value={oa.instructions} onChange={e=>change({instructions:e.target.value})} placeholder="Topics, skills, question emphasis and role requirements" /></label>
      <div className={styles.overview}><strong>{oa.sections.map(s=>`${s.count} ${s.type.toUpperCase()}`).join(' + ')}</strong><span>{oa.duration_minutes} minutes · Secure Browser · Feedback included</span></div>
      <div className={panelStyles.grid} aria-label="Question counts">{['mcq','coding','sql'].map(type=><label key={type}>{type.toUpperCase()} questions<input type="number" min="0" max={type==='mcq'?100:10} disabled={!allowed(catalog,type)} value={oa.sections.find(s=>s.type===type)?.count||0} onChange={e=>setCount(type,e.target.value)}/></label>)}</div>
      <details className={styles.customize}><summary>Customize questions and timing</summary><div className={panelStyles.grid}>
      <label>Specialization<select value={oa.specialization} onChange={e=>change({specialization:e.target.value})}>{['general','frontend','backend','full_stack'].map(v=><option key={v}>{v}</option>)}</select></label>
      <label>Timer<select value={oa.timer_mode} onChange={e=>change({timer_mode:e.target.value,revisit_allowed:e.target.value==='shared'})}><option value="shared">One total timer</option><option value="section">Separate fixed section timers</option></select></label>
      <label>Total duration (minutes)<input type="number" min="5" max="300" value={oa.duration_minutes} onChange={e=>{const minutes=Number(e.target.value);change({duration_minutes:minutes,sections:rebalance(oa.sections,minutes).map((s,i)=>({...s,weight:oa.sections[i].weight}))});}}/></label>
      <label>MCQ selection<select value={oa.mcq_mode} onChange={e=>change({mcq_mode:e.target.value})}>{['single','multiple','mixed'].map(v=><option key={v}>{v}</option>)}</select></label>
      <label>Coding contract<select value={oa.coding_contract} onChange={e=>change({coding_contract:e.target.value})}><option value="stdin_stdout">stdin / stdout</option><option value="function">Typed function</option></select></label>
      <label>SQL engine<select value={oa.sql_engine} onChange={e=>change({sql_engine:e.target.value})}><option value="sqlite">SQLite</option><option value="duckdb">DuckDB</option></select></label>
      </div><fieldset className={panelStyles.choices}><legend>Coding languages</legend>{['python','javascript','java','cpp',...(oa.coding_contract==='stdin_stdout'?['c']:[])].map(language=><label key={language} ><input type="checkbox" checked={oa.languages.includes(language)} onChange={e=>change({languages:e.target.checked?[...oa.languages,language]:oa.languages.filter(v=>v!==language)})}/>{language}</label>)}</fieldset>
      {oa.sections.map((s,index)=><details key={s.type}><summary>{s.type.toUpperCase()}: {s.count} questions</summary><fieldset><legend>{s.type.toUpperCase()} settings</legend><div className={panelStyles.grid}>{['easy','medium','hard'].map(d=><label key={d}>{s.type} {d} count<input type="number" min="0" max={s.type==='mcq'?100:10} value={s.difficulty[d]} onChange={e=>difficulty(index,d,e.target.value)}/></label>)}
        <label>{s.type} marks per question (comma separated)<input value={s.marks.join(',')} onChange={e=>updateSection(index,{marks:e.target.value.split(',').map(Number)})}/></label>
        <label>{s.type} section weight (%)<input type="number" min="0" max="100" value={s.weight} onChange={e=>updateSection(index,{weight:Number(e.target.value)})}/></label>
        <label>{s.type} section minutes<input type="number" min="1" max="300" value={s.duration_minutes} onChange={e=>updateSection(index,{duration_minutes:Number(e.target.value)})}/></label>
        </div><button onClick={()=>change({sections:rebalance(oa.sections.filter((_,i)=>i!==index))})}>Remove {s.type} section</button></fieldset></details>)}
      {['mcq','coding','sql'].filter(type=>!oa.sections.some(s=>s.type===type)).map(type=><button key={type} disabled={!allowed(catalog,type)} onClick={()=>change({sections:rebalance([...oa.sections,{type,count:1,difficulty:{easy:0,medium:1,hard:0},marks:[1],weight:0,duration_minutes:10}])})}>Add {type} section</button>)}
      <p>Section weights must total 100%. For separate timers, section minutes must match the total duration. Code/SQL requires real isolated execution acceptance.</p>
      <label>Monitoring<select value={oa.proctoring_level} onChange={e=>change({proctoring_level:e.target.value})}><option value="basic">Basic secure browser</option>{catalog.media_ready&&<><option value="camera">Sampled camera (+{catalog.pricing.credits.camera_proctoring} credits)</option><option value="dual">Dual camera (+{catalog.pricing.credits.dual_proctoring} credits)</option></>}</select></label>
      </details><p className={styles.note}>AI prepares and checks your questions in the background. Your timer starts after setup in Secure Browser. Contact support if you need a browser or camera accommodation.</p>
      <button className={styles.primary} disabled={busy||pending||!oa.sections.length||!catalog.enabled||!catalog.runtime_ready||catalog.purchase_ready===false} onClick={()=>run(async()=>{setQuote(await post('/practice/assessments/quotes',{configuration:oa}));setApproved(false);})}>{busy?'Preparing...':'Review price & generate OA'}</button>
      {quote&&<div className={styles.quote} aria-label="Mock OA purchase quote"><ul>{quote.line_items.map(line=><li key={line.code}>{line.code}: {line.credits} credits ({line.unit.replaceAll('_',' ')})</li>)}</ul><strong>Total: {quote.total_credits} credits</strong><p>Reserve now; capture once a validated playable OA is ready. Generation failure returns the hold. One attempt; accepted timers continue through disconnection. Start within {quote.start_within_days} days of readiness. AI providers process your requirements and performance topics for generation/advice. No recruitment questions are used.</p>
        <label><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/>I approve this price, purchase policy and AI processing.</label><button className={styles.primary} disabled={busy||!approved} onClick={()=>run(purchase)}>{busy?'Starting generation...':`Generate OA · ${quote.total_credits} credits`}</button></div>}
    </div></>}
    <h3>Your mock OA history</h3>{history&&<><ul>{history.purchases.map(p=><li key={p.purchase_id} className={styles.historyCard}><strong>{catalog?.templates.find(t=>t.id===p.configuration.template_id)?.name||p.configuration.template_id}</strong><span className={styles.state}>{p.state.replaceAll('_',' ')}</span><p>{p.price.total_credits} credits</p>{p.state==='generating'&&<p role="status">AI is preparing and checking your questions. {p.progress?`${p.progress.ready_questions}/${p.progress.total_questions} questions ready.`:''} We will offer to open Secure Browser when it is ready.</p>} {p.error_code&&<p role="alert">{p.state==='failed'?'Generation could not complete. Your reserved credits were returned. You can try a new practice OA.':'This practice OA needs attention. Contact support if refreshing does not help.'}</p>}
      {p.invitation_id&&['ready','started'].includes(p.state)&&<button className={styles.primary} disabled={busy} onClick={()=>setLaunchInvitation(p.invitation_id)}>Start / resume in Secure Browser</button>}{p.invitation_id&&<p><a href={`/assessments/${p.invitation_id}`}>Open / resume this practice OA</a></p>}{p.attempt_id&&<PracticeAssessmentReport attemptId={p.attempt_id}/>}</li>)}</ul>{!history.purchases.length&&<p>No mock OAs purchased yet.</p>}{history.next_cursor&&<button disabled={busy} onClick={()=>run(()=>load(history.next_cursor))}>Load older mock OAs</button>}</>}
    <details><summary>Purchases and refunds</summary><BillingOperationsPanel/></details>
    <KioskLaunchGuide assessment practice isOpen={!!launchInvitation} busy={busy} onClose={()=>setLaunchInvitation(null)} onOpen={launch}/>
  </section>;
}

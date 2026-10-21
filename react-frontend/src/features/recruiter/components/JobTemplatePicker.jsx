import React, {useRef, useState} from 'react';
import {JOB_TEMPLATES} from '../utils/jobTemplates';
import styles from './JobForm.module.css';

export default function JobTemplatePicker({onSelect,editing=false}) {
  const [search,setSearch]=useState('');
  const [selected,setSelected]=useState(null);
  const details=useRef(null), summary=useRef(null);
  const templates=Object.entries(JOB_TEMPLATES).filter(([name,t])=>`${name} ${t.department} ${t.skills.join(' ')}`.toLowerCase().includes(search.toLowerCase()));
  return <><details ref={details} className={styles.templateSection}>
    <summary ref={summary} className={styles.templateHeading}>{selected?`${selected.name} selected — change template`:'Choose a role template'} <span>{Object.keys(JOB_TEMPLATES).length} job + OA starters</span></summary>
    <p>{editing ? 'Applying a template replaces the editable job description and skills. Saved OA questions and customized assessment settings are preserved.' : 'Apply a complete job starter. At the end, include its OA to load editable questions, answer keys and tests.'}</p>
    <label className={styles.templateSearch}>Find a role<input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search roles, skills or departments"/></label>
    <div className={styles.templateGrid}>{templates.map(([name,t])=><button type="button" key={name} aria-pressed={selected?.name===name} className={styles.templateCard} onClick={()=>{onSelect(name,t);setSelected({name,template:t});details.current.open=false;summary.current.focus();}}>
      <strong>{name}</strong><span>{t.department}</span><small>{['product','business_analyst','ux_design','security','marketing','sales','hr','customer_support','finance'].includes(t.oaTemplateId)?'Knowledge MCQs':t.oaTemplateId==='data_analyst'?'SQL + MCQs':t.oaTemplateId==='data_scientist'?'Coding + SQL + MCQs':'Coding + MCQs'}</small>
    </button>)}</div>{!templates.length&&<p role="status">No matching templates. You can enter a custom role.</p>}
  </details>{selected&&<p role="status" className={styles.selectionNotice}><strong>{selected.name} applied.</strong> Its complete OA starter is ready when you include an assessment. Customized OA settings are preserved.</p>}</>;
}

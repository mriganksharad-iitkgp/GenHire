import React,{useState} from 'react';
import styles from './HiringSetupWizard.module.css';
export default function QuestionAccordionGroup({label,items,render,title,initiallyCollapsed=true}) {
  const [active,setActive]=useState(null),[all,setAll]=useState(false);
  return <details aria-label={`${label.replace(/ questions$/,'')} draft questions`} className={styles.accordion} open={initiallyCollapsed?undefined:true}>
    <summary>{label} ({items.length})</summary>
    <div className={styles.questionActions}><button type="button" onClick={()=>{setAll(!all);setActive(null);}}>{all?'Collapse all':'Expand all'} {label.toLowerCase()}</button></div>
    {items.map((item,index)=><details key={item._id||item.id||index} className={styles.compactHelp}
      open={all||active===index} onToggle={e=>{if(e.target!==e.currentTarget||all)return;const opened=e.currentTarget.open;
        setActive(current=>opened?index:current===index?null:current);}}>
      <summary onClick={e=>{e.preventDefault();if(all){setAll(false);setActive(index);}else setActive(active===index?null:index);}}>{title(item,index)}</summary>
      {render(item,index)}
    </details>)}
  </details>;
}

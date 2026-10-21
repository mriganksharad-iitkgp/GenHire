import React,{useId,useRef,useState,useEffect} from 'react';
import {createPortal} from 'react-dom';
import styles from './HiringSetupWizard.module.css';
export default function TermHelp({term,children}) {
  const id=useId(), button=useRef(null), [position,setPosition]=useState(null);
  const show=()=>{const r=button.current.getBoundingClientRect(),width=Math.min(290,window.innerWidth-24);
    setPosition({left:Math.max(12,Math.min(r.left,window.innerWidth-width-12)),top:r.bottom+8,width,
      ...(r.bottom>window.innerHeight-150?{top:'auto',bottom:window.innerHeight-r.top+8}:{})});};
  useEffect(()=>{if(!position)return;const hide=()=>setPosition(null);window.addEventListener('scroll',hide,true);window.addEventListener('resize',hide);return()=>{window.removeEventListener('scroll',hide,true);window.removeEventListener('resize',hide);};},[position]);
  return <span className={styles.termHelp} onMouseEnter={show} onMouseLeave={()=>setPosition(null)}>
    <button ref={button} type="button" aria-label={`Explain ${term}`} aria-describedby={position?id:undefined}
      onFocus={show} onBlur={()=>setPosition(null)} onClick={show} onKeyDown={e=>{if(e.key==='Escape')setPosition(null);}}>?</button>
    {position&&createPortal(<span role="tooltip" id={id} className={styles.tooltip} style={position}>{children}</span>,document.body)}
  </span>;
}

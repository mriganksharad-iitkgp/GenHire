import {useCallback,useEffect,useRef,useState} from 'react';
import {getUser,getToken} from 'shared/utils/session';

export const DRAFT_TTL=7*24*60*60*1000;
export function jobDraftKey(user,jobId) {
  const owner=user?._id||user?.id||user?.user_id||user?.email;
  return owner?`genhire:job-draft:v1:${encodeURIComponent(String(owner))}:${encodeURIComponent(jobId||'new')}`:null;
}
export function readJobDraft(storage,key,now=Date.now()) {
  if(!key)return null;
  try {
    const raw=storage.getItem(key);if(!raw)return null;
    if(raw.length>500000){storage.removeItem(key);return null;}
    const item=JSON.parse(raw);
    if(item.version!==1||!Number.isFinite(item.savedAt)||item.savedAt>now+60000||now-item.savedAt>DRAFT_TTL||!item.value?.jobFields||typeof item.value.jobFields!=='object'
      ||typeof item.value.jobFields.title!=='string'||typeof item.value.jobFields.description!=='string'||!Array.isArray(item.value.jobFields.skills)){
      storage.removeItem(key);return null;
    }
    return item;
  } catch{return null;}
}

export default function useJobDraftRecovery({isOpen,jobId,value,onRestore,hold=false}) {
  const key=getToken()?jobDraftKey(getUser(),jobId):null;
  const [pending,setPending]=useState(null),[status,setStatus]=useState('');
  const held=useRef(hold);held.current=hold;
  const latest=useRef(value),restore=useRef(onRestore),pendingRef=useRef(false),cleared=useRef(false),last=useRef('');
  latest.current={key,value};restore.current=onRestore;
  const flush=useCallback(()=>{
    if(!key||held.current||pendingRef.current||cleared.current)return;
    if(latest.current.key!==key)return;
    const current=latest.current.value;
    if(!current?.jobFields?.title?.trim()&&!current?.jobFields?.description?.trim()&&!current?.aiPrompt?.trim())return;
    try{
      const signature=JSON.stringify(current);if(signature===last.current)return;
      const serialized=JSON.stringify({version:1,savedAt:Date.now(),value:current});
      if(serialized.length>500000)throw new Error('draft_limit');
      localStorage.setItem(key,serialized);last.current=signature;setStatus('Progress saved on this device');
    }catch{setStatus('Device autosave unavailable. Use Save hiring draft before leaving.');}
  },[key]);
  useEffect(()=>{
    if(!isOpen)return;
    cleared.current=false;last.current='';
    let item=null;try{item=readJobDraft(localStorage,key);}catch{setStatus('Device autosave is unavailable.');}
    pendingRef.current=!!item;setPending(item);if(item)setStatus('');
    const saveOnLeave=()=>flush();
    window.addEventListener('pagehide',saveOnLeave);document.addEventListener('visibilitychange',saveOnLeave);
    return()=>{flush();window.removeEventListener('pagehide',saveOnLeave);document.removeEventListener('visibilitychange',saveOnLeave);};
  },[isOpen,key,flush]);
  const signature=JSON.stringify(value);
  useEffect(()=>{if(!isOpen)return;const timer=setTimeout(flush,600);return()=>clearTimeout(timer);},[isOpen,signature,flush]);
  const discard=useCallback(()=>{try{if(key)localStorage.removeItem(key);}catch{}pendingRef.current=false;setPending(null);last.current=JSON.stringify(latest.current.value);setStatus('Saved device draft discarded');},[key]);
  const clear=useCallback(()=>{cleared.current=true;pendingRef.current=false;setPending(null);try{if(key)localStorage.removeItem(key);}catch{}},[key]);
  return {pending,status,flush,clear,discard,checkpoint:patch=>{
    pendingRef.current=false;cleared.current=false;setPending(null);
    latest.current={...latest.current,value:{...latest.current.value,...patch}};flush();
  },resume:()=>{if(!pending)return;restore.current(pending.value);last.current=JSON.stringify(pending.value);pendingRef.current=false;setPending(null);setStatus('Device draft restored. Reattach any uploaded file before saving.');}};
}

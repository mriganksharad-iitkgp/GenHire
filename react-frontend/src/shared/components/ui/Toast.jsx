import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import styles from './Toast.module.css';
const Toast = ({ message, type = 'info', duration = 3000, onClose }) => {
  const [visible,setVisible]=useState(true), close=useRef(onClose), fade=useRef(null), expiry=useRef(null);
  close.current=onClose;
  useEffect(()=>{
    setVisible(true);
    expiry.current=setTimeout(()=>{setVisible(false);fade.current=setTimeout(()=>close.current?.(),300);},duration);
    return()=>{clearTimeout(expiry.current);clearTimeout(fade.current);};
  },[message,duration]);
  const icons={success:'fa-check-circle',error:'fa-times-circle',warning:'fa-exclamation-triangle',info:'fa-info-circle'};
  return createPortal(<div role={type==='error'?'alert':'status'} aria-live={type==='error'?'assertive':'polite'}
    className={`${styles.toast} ${styles[type]||styles.info} ${visible?styles.visible:styles.hidden}`}>
    <i aria-hidden="true" className={`fa ${icons[type]||icons.info}`}/><span>{message}</span>
    <button type="button" aria-label="Close notification" className={styles.closeButton} onClick={()=>{
      clearTimeout(expiry.current);clearTimeout(fade.current);setVisible(false);fade.current=setTimeout(()=>close.current?.(),200);
    }}><i aria-hidden="true" className="fa fa-times"/></button>
  </div>,document.body);
};
export default Toast;

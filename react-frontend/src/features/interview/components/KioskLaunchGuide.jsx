import React, { useEffect, useRef, useState } from "react";
import { Download, ShieldCheck, X } from "lucide-react";
import { KIOSK_DOWNLOAD_URL, KIOSK_MAC_DOWNLOAD_URL } from "shared/constants/appLinks";
import styles from "../pages/InterviewExperience.module.css";

export function openKiosk(payload) {
  const bytes = new TextEncoder().encode(JSON.stringify({ ...payload, token: payload.token, webOrigin: window.location.origin }));
  const encoded = btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(""));
  const frame = document.createElement("iframe"); frame.hidden = true;
  frame.src = `secure-interview://start?initData=${encodeURIComponent(encoded)}`;
  document.body.appendChild(frame); setTimeout(() => frame.remove(), 5000);
}

export default function KioskLaunchGuide({ isOpen, onClose, onOpen, busy = false, practice = false, prepareOnly = false }) {
  const [installed, setInstalled] = useState(false); const [requested, setRequested] = useState(false); const dialog = useRef(null);
  const closeRef = useRef(onClose); closeRef.current = onClose; const busyRef = useRef(busy); busyRef.current = busy;
  useEffect(() => { if (!isOpen) return; setRequested(false); const previous = document.activeElement; dialog.current?.focus();
    const keyboard = (event) => { if (event.key === "Escape" && !busyRef.current) closeRef.current();
      if (event.key !== "Tab") return;
      const elements = [...dialog.current.querySelectorAll('a[href],button:not(:disabled),input')]; const first = elements[0]; const last = elements.at(-1);
      if (event.shiftKey && [first, dialog.current].includes(document.activeElement)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }; document.addEventListener("keydown", keyboard); return () => { document.removeEventListener("keydown", keyboard); previous?.focus(); };
  }, [isOpen]);
  if (!isOpen) return null;
  return <div className={styles.reportOverlay}><section ref={dialog} tabIndex={-1} className={styles.centerCard} role="dialog" aria-modal="true" aria-labelledby="kiosk-title">
    <header className={styles.reportHeader}><span className={styles.brand}><ShieldCheck size={20}/> GenHire Secure Browser</span><button onClick={onClose} disabled={busy} aria-label="Close installation guide" className={styles.textButton}><X size={20}/></button></header>
    <h1 id="kiosk-title">Get ready for your {practice ? "practice" : "interview"}</h1><p>Use your laptop or desktop. Install the secure browser once, then open your interview from this page.</p>
    <ol><li>Download and run the Windows installer. On Mac, move GenHire to Applications.</li><li>Finish installation, then return to this page.</li><li>Choose Open Secure Browser and accept the browser's “Open GenHire” prompt.</li></ol>
    <div className={styles.actions}><a className={styles.secondary} href={KIOSK_DOWNLOAD_URL} target="_blank" rel="noreferrer"><Download size={18}/> Download for Windows</a>{KIOSK_MAC_DOWNLOAD_URL && <a className={styles.secondary} href={KIOSK_MAC_DOWNLOAD_URL} target="_blank" rel="noreferrer">Download for Mac</a>}</div>
    {!KIOSK_MAC_DOWNLOAD_URL && <p className={styles.note}>The configured installer supports Windows. Ask your recruiter for the supported Mac installer if you use a Mac.</p>}
    <label className={styles.consent}><input type="checkbox" checked={installed} onChange={(event) => setInstalled(event.target.checked)}/> I have installed GenHire Secure Browser on this computer.</label>
    <button disabled={!installed || busy} className={styles.primary} onClick={async () => { setRequested(!prepareOnly); await onOpen(); }}>{busy ? "Preparing your session…" : prepareOnly ? "Continue to CV selection" : "Open Secure Browser"}</button>
    {requested && <p className={styles.note} role="status">If the app hasn't opened, accept the browser prompt or finish installation, then try again. Browsers cannot reliably detect whether the app is installed.</p>}
    <p className={styles.note}>Inside the app, check your camera, microphone and speakers, then capture your face. A second phone camera is required only when your recruiter enables it. Answer time starts after setup.</p>
  </section></div>;
}

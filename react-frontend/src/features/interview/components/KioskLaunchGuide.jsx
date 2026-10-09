import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Download, ShieldCheck, X } from "lucide-react";
import { KIOSK_DOWNLOAD_URL, KIOSK_MAC_DOWNLOAD_URL } from "shared/constants/appLinks";
import styles from "../pages/InterviewExperience.module.css";

const INSTALLATION_KEY = "genhire:kiosk-installed:v1";
function installationConfirmed() {
  try { return window.localStorage.getItem(INSTALLATION_KEY) === "confirmed"; }
  catch { return false; }
}
function rememberInstallation(value) {
  try {
    if (value) window.localStorage.setItem(INSTALLATION_KEY, "confirmed");
    else window.localStorage.removeItem(INSTALLATION_KEY);
  } catch { /* Storage can be unavailable in private browsers; launch still works. */ }
}

export function openKiosk(payload) {
  const bytes = new TextEncoder().encode(JSON.stringify({ ...payload, token: payload.token, webOrigin: window.location.origin }));
  const encoded = btoa(Array.from(bytes, (byte) => String.fromCharCode(byte)).join(""));
  const frame = document.createElement("iframe"); frame.hidden = true;
  frame.src = `secure-interview://start?initData=${encodeURIComponent(encoded)}`;
  document.body.appendChild(frame); setTimeout(() => frame.remove(), 5000);
}

export default function KioskLaunchGuide({ isOpen, onClose, onOpen, busy = false, practice = false, prepareOnly = false }) {
  const [installed, setInstalled] = useState(installationConfirmed);
  const [showHelp, setShowHelp] = useState(false);
  const [requested, setRequested] = useState(false);
  const dialog = useRef(null);
  const closeRef = useRef(onClose); closeRef.current = onClose;
  const busyRef = useRef(busy); busyRef.current = busy;
  useEffect(() => {
    if (!isOpen) return;
    setRequested(false); setShowHelp(false);
    const previous = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    const keyboard = (event) => {
      if (event.key === "Escape" && !busyRef.current) closeRef.current();
      if (event.key !== "Tab") return;
      const elements = [...dialog.current.querySelectorAll('a[href],button:not(:disabled),input')];
      const first = elements[0], last = elements.at(-1);
      if (event.shiftKey && [first, dialog.current].includes(document.activeElement)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", keyboard);
    return () => { document.removeEventListener("keydown", keyboard); document.body.style.overflow = previousOverflow; previous?.focus(); };
  }, [isOpen]);
  if (!isOpen) return null;
  const needsSetup = !installed || showHelp;
  const confirm = (value) => { setInstalled(value); rememberInstallation(value); };
  return createPortal(<div className={styles.reportOverlay}><section ref={dialog} tabIndex={-1} className={`${styles.centerCard} ${styles.launchCard}`} role="dialog" aria-modal="true" aria-labelledby="kiosk-title">
    <header className={styles.reportHeader}><span className={styles.brand}><ShieldCheck size={20}/> GenHire Secure Browser</span><button onClick={onClose} disabled={busy} aria-label="Close installation guide" className={styles.textButton}><X size={20}/></button></header>
    <h1 id="kiosk-title">{installed ? "Open your" : "Set up your"} {practice ? "practice interview" : "interview"}</h1>
    <p>{installed ? "Your installation confirmation is saved on this browser. Open the secure browser and accept the browser prompt to continue." : "Use your laptop or desktop. Install the secure browser once, then return here to start."}</p>
    {needsSetup && <div id="kiosk-installation-help">
      <ol><li>Download the installer for your computer and finish installation.</li><li>Return here and confirm installation below.</li><li>Choose Open Secure Browser and accept the browser's "Open GenHire" prompt.</li></ol>
      <div className={styles.actions}><a className={styles.secondary} href={KIOSK_DOWNLOAD_URL} target="_blank" rel="noreferrer"><Download size={18}/> Download for Windows</a>{KIOSK_MAC_DOWNLOAD_URL && <a className={styles.secondary} href={KIOSK_MAC_DOWNLOAD_URL} target="_blank" rel="noreferrer">Download for Mac</a>}</div>
      {!KIOSK_MAC_DOWNLOAD_URL && <p className={styles.note}>A Mac installer is not available here. Use Windows or ask your recruiter about a supported device.</p>}
      <label className={styles.consent}><input type="checkbox" checked={installed} onChange={(event) => confirm(event.target.checked)}/> I have installed GenHire Secure Browser on this computer.</label>
    </div>}
    <button disabled={!installed || busy} className={styles.primary} onClick={async () => { setRequested(!prepareOnly); await onOpen(); }}>{busy ? "Preparing your session..." : prepareOnly ? "Continue to CV selection" : "Open Secure Browser"}</button>
    {installed && <button className={styles.textButton} aria-expanded={showHelp} aria-controls="kiosk-installation-help" onClick={() => setShowHelp(!showHelp)}>{showHelp ? "Hide installation help" : "Need to install or reinstall?"}</button>}
    {requested && <p className={styles.note} role="status">Waiting for the secure browser. If it has not opened, accept the browser prompt, or use installation help to reinstall and try again.</p>}
    <p className={styles.note}>Inside the app, check your camera, microphone and speakers, then capture your face. A second phone camera is required only when your recruiter enables it. Answer time starts after setup.</p>
  </section></div>, document.body);
}

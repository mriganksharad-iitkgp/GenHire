import "shared/styles/portal-theme.css";
import "./kiosk.css";
import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import Chat from "features/interview/pages/Chat";
import { returnFromKiosk } from "features/interview/utils/kioskReturn";
import { setToken } from "shared/utils/session";
import styles from "features/interview/pages/InterviewExperience.module.css";

const launchStateFor = (payload) => ({ applicationId: payload.applicationId, isPractice: payload.isPractice });

function Kiosk() {
  const [launch, setLaunch] = useState(null); const [error, setError] = useState("");
  const launchRef = useRef(null);
  useEffect(() => {
    const initialize = (encoded) => {
      if (!encoded) return;
      try {
        const payload = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0))));
        if (launchRef.current) { if (payload.sessionId !== launchRef.current.sessionId || payload.applicationId !== launchRef.current.applicationId) setError("An interview is already open. Finish it before opening another session."); return; }
        if (!payload.sessionId && !payload.applicationId) throw new Error("Open your interview from your GenHire dashboard.");
        setToken(payload.token); payload.launchState = launchStateFor(payload); launchRef.current = payload; setLaunch(payload);
      } catch (failure) { setError(failure.message); }
    };
    window.electronAPI?.onInitDeepLink((_event, encoded) => initialize(encoded));
    window.electronAPI?.rendererReady().then(initialize).catch(() => setError("Return to your dashboard and open the interview again."));
  }, []);
  const back = (path) => returnFromKiosk(window.electronAPI, launch, path);
  if (!launch) return <main className={styles.shell}><section className={styles.centerCard}><span className={styles.brand}>GenHire Secure Browser</span><h1>Open your interview</h1><p>Open an interview from your GenHire dashboard, then accept the request to launch GenHire Secure Browser.</p>{error && <p role="alert">{error}</p>}<button className={styles.textButton} onClick={() => window.electronAPI?.quitApp()}>Close browser</button></section></main>;
  return <>{error && <div role="alert" className={styles.error}>{error}</div>}<BrowserRouter><Chat interviewId={launch.sessionId || "start"} apiBase={`${launch.apiUrl.replace(/\/$/, "")}/api`} webOrigin={launch.webOrigin} onReturn={back} launchState={launch.launchState} /></BrowserRouter></>;
}
createRoot(document.getElementById("root")).render(<Kiosk />);

import "shared/styles/portal-theme.css";
import "./kiosk.css";
import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import Chat from "features/interview/pages/Chat";
import { returnFromKiosk } from "features/interview/utils/kioskReturn";
import { setToken } from "shared/utils/session";
import styles from "features/interview/pages/InterviewExperience.module.css";
import GenHireBrand from "shared/components/ui/GenHireBrand";
import ScopedAssessment from "features/assessment/components/ScopedAssessment";

const launchStateFor = (payload) => ({ applicationId: payload.applicationId, isPractice: payload.isPractice });
document.body.dataset.uiKind = 'app';

function Kiosk() {
  const [launch, setLaunch] = useState(null); const [error, setError] = useState("");
  const launchRef = useRef(null);
  useEffect(() => {
    const initialize = (encoded) => {
      if (!encoded) return;
      try {
        const payload = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0))));
        if (launchRef.current) { if (payload.sessionId !== launchRef.current.sessionId || payload.applicationId !== launchRef.current.applicationId) setError("An interview is already open. Finish it before opening another session."); return; }
        if (payload.mode === 'oa') {
          if (!payload.launchCode || !payload.invitationId) throw new Error('Open the OA from your GenHire dashboard.');
        } else {
          if (!payload.sessionId && !payload.applicationId) throw new Error("Open your interview from your GenHire dashboard.");
          setToken(payload.token);
        }
        payload.launchState = launchStateFor(payload); launchRef.current = payload; setLaunch(payload);
      } catch { setError('Invalid secure-browser launch. Open it again from your GenHire dashboard.'); }
    };
    window.electronAPI?.onInitDeepLink((_event, encoded) => initialize(encoded));
    window.electronAPI?.rendererReady().then(initialize).catch(() => setError("Return to your dashboard and open the interview again."));
  }, []);
  const back = (path) => returnFromKiosk(window.electronAPI, launch, path);
  if (!launch) return <main className={styles.shell}><section className={styles.centerCard}><GenHireBrand label="Secure Browser" /><h1>Open your assessment or interview</h1><p>Open your session from the GenHire dashboard, then accept the request to launch GenHire Secure Browser.</p>{error && <p role="alert">{error}</p>}<button className={styles.textButton} onClick={() => window.electronAPI?.quitApp()}>Close browser</button></section></main>;
  return <>{error && <div role="alert" className={styles.error}>{error}</div>}<BrowserRouter>{launch.mode === 'oa' ? <ScopedAssessment launch={launch} /> : <Chat interviewId={launch.sessionId || "start"} apiBase={`${launch.apiUrl.replace(/\/$/, "")}/api`} webOrigin={launch.webOrigin} onReturn={back} launchState={launch.launchState} />}</BrowserRouter></>;
}
createRoot(document.getElementById("root")).render(<Kiosk />);

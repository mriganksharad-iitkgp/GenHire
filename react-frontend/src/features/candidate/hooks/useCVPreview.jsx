import React, { useCallback, useEffect, useRef, useState } from "react";
import Modal from "shared/components/ui/Modal";
import { request, requestBlob } from "shared/api/client";
import styles from "features/candidate/pages/Profile.module.css";

export default function useCVPreview() {
  const [selection, setSelection] = useState(null);
  const [url, setUrl] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const closeButton = useRef(null);
  const close = useCallback(() => setSelection(null), []);
  const viewCV = useCallback((item) => { setSelection({ cv_id:item?.cv_id, id:item?.id }); setUrl(null); setError(null); }, []);
  useEffect(() => {
    if (!selection) return undefined;
    let cancelled = false, objectUrl;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();
    setUrl(null); setError(null);
    const load = async () => {
      try {
        let cvId = selection.cv_id;
        if (!cvId && !selection.id) {
          const result = await request("/cv/list", { signal:controller.signal });
          const cvs = Array.isArray(result?.cvs) ? result.cvs : [];
          cvId = (cvs.find(cv => cv.is_primary) || cvs[0])?.cv_id;
          if (!cvId) throw new Error("No CV uploaded yet. Upload one in My Profile.");
        }
        if (cancelled) return;
        const path = cvId ? `/cv/${encodeURIComponent(cvId)}/preview` : `/applications/${encodeURIComponent(selection.id)}/cv`;
        const blob = await requestBlob(path, { signal:controller.signal });
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob); setUrl(objectUrl);
      } catch (err) {
        if (!cancelled) setError(controller.signal.aborted ? "The CV took too long to load. Please retry." : err.status >= 500 ? "The CV is unavailable right now. Please retry." : err.message || "Unable to load the CV.");
      } finally { clearTimeout(timeout); }
    };
    load();
    return () => { cancelled = true; clearTimeout(timeout); controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); document.body.style.overflow = previousOverflow; previousFocus?.focus(); };
  }, [selection, attempt]);
  const preview = <Modal isOpen={!!selection} onClose={close} closeOnEsc contentClassName={styles.previewModal}>
    <section role="dialog" aria-modal="true" aria-labelledby="cv-preview-title" onKeyDown={event => {
      if (event.key !== "Tab") return;
      const controls = [...event.currentTarget.querySelectorAll('button,a[href],iframe')];
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
      <div className={styles.previewHeader}><h2 id="cv-preview-title">CV preview</h2><button ref={closeButton} type="button" onClick={close} className={styles.ghostButton}>Close</button></div>
      {error ? <div className={styles.previewState} role="alert"><p>{error}</p><button className={styles.primaryButton} onClick={() => setAttempt(n => n + 1)}>Retry</button></div> : url ? <><iframe className={styles.previewFrame} title="Uploaded CV" src={url} /><a href={url} download="CV.pdf" className={styles.ghostButton}>Download CV</a></> : <p className={styles.previewState} role="status">Loading CV...</p>}
    </section>
  </Modal>;
  return { viewCV, preview };
}

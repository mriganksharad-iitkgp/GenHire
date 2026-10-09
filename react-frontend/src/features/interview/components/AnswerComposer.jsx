import React, { useEffect, useRef } from "react";
import { Mic, PencilLine } from "lucide-react";
import styles from "../pages/InterviewExperience.module.css";

export default function AnswerComposer({ mode, onModeChange, speechState, paused, pendingAnswer,
  audioRetryAvailable, hasSpoken, draft, onDraftChange, onSendText, onSendVoice, onRetryAudio,
  onRepeat, onMoreTime, onRecord }) {
  const inputRef = useRef(null);
  const processing = ["thinking", "transcribing"].includes(speechState);
  const disabled = paused || processing;
  useEffect(() => { if (mode === "text") inputRef.current?.focus(); }, [mode]);

  return <section className={styles.answerComposer} aria-label="Your answer">
    <div className={styles.answerMode} role="group" aria-label="Answer format">
      <button type="button" aria-pressed={mode === "voice"} disabled={disabled || pendingAnswer !== null}
        onClick={() => onModeChange("voice")}><Mic size={16} />Speak answer</button>
      <button type="button" aria-pressed={mode === "text"} disabled={disabled || pendingAnswer !== null}
        onClick={() => onModeChange("text")}><PencilLine size={16} />Type answer</button>
    </div>
    {mode === "voice" ? <>
      <p className={styles.note}>Start speaking within 30 seconds. After you speak, 8 seconds of silence sends your answer automatically. Recordings are sent after 3 minutes at most. You can also choose Send answer.</p>
      <div className={styles.answerActions}>
        {audioRetryAvailable && <button className={styles.secondary} disabled={disabled} onClick={onRetryAudio}>Retry transcription</button>}
        <button className={styles.primary} disabled={disabled || speechState !== "listening" || pendingAnswer !== null} onClick={onSendVoice}><Mic size={18} />Send answer</button>
        <button className={styles.secondary} disabled={disabled || pendingAnswer !== null} onClick={onRepeat}>Repeat question</button>
        {speechState === "listening" && !hasSpoken && <button className={styles.textButton} disabled={paused} onClick={onMoreTime} title="Restart the 30-second thinking countdown. The question time limit stays the same.">More thinking time</button>}
        {speechState === "idle" && pendingAnswer === null && <button className={styles.secondary} disabled={disabled} onClick={onRecord}>Record answer</button>}
      </div>
    </> : <div className={styles.textAnswer}>
      <p id="typed-answer-help" className={styles.note}>Automatic answer submission is off while you type. Camera and microphone monitoring continue. The question time limit still applies.</p>
      <label htmlFor="typed-answer">Your typed answer</label>
      <textarea id="typed-answer" ref={inputRef} value={draft} onChange={event => onDraftChange(event.target.value)}
        aria-describedby="typed-answer-help" placeholder="Describe your approach, decisions and results."
        disabled={disabled || pendingAnswer !== null} />
      <div className={styles.answerActions}>
        <button className={styles.primary} disabled={disabled || !draft.trim() || pendingAnswer !== null} onClick={onSendText}>Send text answer</button>
        <button className={styles.secondary} disabled={disabled || pendingAnswer !== null} onClick={onRepeat}>Repeat question</button>
      </div>
    </div>}
  </section>;
}

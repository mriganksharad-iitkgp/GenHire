import React, { memo } from "react";
import Styles from "../../pages/Chat.module.css";

const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
};

function InterviewHeader({
  questionCount,
  maxQuestions,
  interviewElapsedTime,
  silenceTimer,
  isTimerRunning,
  hasSpoken,
  noAnswerRemaining,
  autoSubmitAfter,
}) {
  // Listening status line. Two phases per question:
  //  - candidate hasn't spoken yet: relaxed "answer when ready", switching to
  //    a visible countdown for the final 15s of the no-answer window;
  //  - candidate is answering: quiet while they talk, then a countdown once
  //    they've paused long enough that auto-submit approaches.
  let indicator = null;
  if (isTimerRunning) {
    if (!hasSpoken) {
      if (typeof noAnswerRemaining === "number" && noAnswerRemaining <= 15) {
        indicator = `⏳ No answer detected — skipping this question in ${noAnswerRemaining}s`;
      } else {
        indicator = "🎤 Listening — answer when you're ready";
      }
    } else {
      const remaining = Math.max(0, (autoSubmitAfter || 10) - silenceTimer);
      if (silenceTimer >= 4) {
        indicator = `✅ Finished? Auto-submitting in ${remaining}s`;
      } else {
        indicator = "🎙️ Recording your answer…";
      }
    }
  }

  return (
    <div className={Styles["interview-header"]}>
      <div className={Styles["progress-info"]}>
        <span className={Styles["question-counter"]}>
          Question {questionCount} of {maxQuestions}
        </span>
        <span className={Styles["time-elapsed"]}>
          ⏱️ {formatTime(interviewElapsedTime)}
        </span>
      </div>
      {indicator && (
        <div className={Styles["silence-indicator"]}>{indicator}</div>
      )}
    </div>
  );
}

export default memo(InterviewHeader);

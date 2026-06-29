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
  transcriptLength,
}) {
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
      {isTimerRunning && transcriptLength > 0 && (
        <div className={Styles["silence-indicator"]}>
          {silenceTimer < 5
            ? `Speaking... ${5 - silenceTimer}s until auto-submit`
            : "Auto-submitting..."}
        </div>
      )}
    </div>
  );
}

export default memo(InterviewHeader);

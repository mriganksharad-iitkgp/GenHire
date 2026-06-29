import React, { memo } from "react";
import Styles from "../../pages/Chat.module.css";

// Exported so Chat.jsx can reference the length for the cycling useEffect
export const LOADING_STEPS = [
  "Verifying your credentials...",
  "Loading your CV and job description...",
  "Generating personalised interview questions...",
  "Almost ready...",
];

function LoadingScreen({ loadingStepIndex }) {
  return (
    <div className={Styles.loadingContainer}>
      <div className={Styles.spinner}></div>
      <h3
        style={{
          marginTop: "20px",
          color: "#4338ca",
          fontSize: "24px",
          fontWeight: "600",
        }}
      >
        Preparing Your Interview
      </h3>
      <p
        style={{
          color: "#475569",
          maxWidth: "400px",
          textAlign: "center",
          lineHeight: "1.6",
          minHeight: "1.6em",
          transition: "opacity 0.3s ease",
        }}
      >
        {LOADING_STEPS[loadingStepIndex]}
      </p>
      {/* Progress dots — fill left-to-right as the step index advances */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          marginTop: "18px",
          justifyContent: "center",
        }}
      >
        {LOADING_STEPS.map((_, i) => (
          <div
            key={i}
            style={{
              width: "9px",
              height: "9px",
              borderRadius: "50%",
              background: i <= loadingStepIndex ? "#4338ca" : "#e2e8f0",
              transition: "background 0.4s ease",
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default memo(LoadingScreen);

import React from "react";
import { Sparkles, UserRound, ShieldCheck } from "lucide-react";
import AuthBrand from "./AuthBrand";
import styles from "./AuthStory.module.css";

export default function AuthStory({ title = "Your next chapter.", accent = "Starts with you.", description = "Explore roles, prepare with AI interviews and mock OAs, and follow each stage of your application." }) {
  return (
      <aside className={styles.storyPanel}>
        <AuthBrand />
        <div className={styles.storyCopy}>
          <span className={styles.eyebrow}><Sparkles size={15} aria-hidden="true" /> A better way forward</span>
          <h2>{title}<br /><em>{accent}</em></h2>
          <p>{description}</p>
        </div>
        <div className={styles.illustration} aria-hidden="true">
          <div className={styles.orbit} /><div className={styles.orbitInner} />
          <div className={styles.interviewCard}>
            <div className={styles.cardHeader}><span className={styles.avatar}><UserRound size={24} /></span><div><strong>A conversation that counts</strong><small>Practice at your own pace</small></div><span className={styles.liveDot} /></div>
            <div className={styles.waveform}>{[20, 34, 48, 26, 58, 40, 66, 32, 50, 24, 44, 62, 28, 46, 36, 22].map((height, index) => <span key={index} style={{ "--bar-height": `${height}px`, "--delay": `${index * 0.12}s` }} />)}</div>
            <div className={styles.cardFooter}><span>Screen. Assess. Progress.</span><span className={styles.sparkBadge}><Sparkles size={14} /> AI interviews + OAs</span></div>
          </div>
          <div className={styles.floatingCard}><span className={styles.checkBadge}><ShieldCheck size={21} /></span><div><strong>Your journey, connected</strong><small>Screening &rarr; Optional OA &rarr; Company rounds</small></div></div>
          <span className={styles.sparkOne}>+</span><span className={styles.sparkTwo}>+</span>
        </div>
        <p className={styles.storyFooter}>Prepared candidates. Thoughtful hiring.</p>
      </aside>
  );
}

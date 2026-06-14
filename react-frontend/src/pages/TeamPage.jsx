import React, { useState } from "react";
import styles from "./TeamPage.module.css";

const teamMembers = [
  {
    name: "Nikhil Gupta",
    contribution:
      "Developed the HR and candidate portals end to end, spanning React flows, Python APIs, and CV/interview automation.",
    linkedIn: "https://www.linkedin.com/in/nikhil-gupta-359742256/",
    imageUrl: "https://media.licdn.com/dms/image/v2/D4D03AQEYale5anIyzQ/profile-displayphoto-shrink_400_400/profile-displayphoto-shrink_400_400/0/1684241864091?e=1779321600&v=beta&t=hTKjgiBn_DSMTHBEjLogvcT6eeAdDnNHr0gaddyqDMQ",
  },
  {
    name: "Aditya Pandey",
    contribution:
      "Engineered the proctoring pipeline for recording analysis, face verification, cheating detection, and high-load tuning.",
    linkedIn: "https://www.linkedin.com/in/aditya-pandey-359742256/",
    imageUrl: "https://media.licdn.com/dms/image/v2/D5603AQF9O12iP6npGg/profile-displayphoto-scale_400_400/B56ZfyD6gvHcA4-/0/1752112826849?e=1779321600&v=beta&t=Ucb4H9xE-dcwIXEsTK1OGoeSm3f8LpLjrP7NkfUg3k8",
  },
  {
    name: "Raja Subrahmanya",
    contribution:
      "Built LLM-driven question generation and rubric-based evaluation with orchestration and structured parsing.",
    linkedIn: "https://www.linkedin.com/in/raja-subrahmanya-06a2b1162/",
    imageUrl: "https://media.licdn.com/dms/image/v2/D4D03AQHMxY_qsRMLvA/profile-displayphoto-scale_400_400/B4DZ0G7SxfJoAg-/0/1773937702333?e=1779321600&v=beta&t=d0HgVE5mP0niNwGYqYSzq9kmFj95tbc0j7dpkUXuH04",
  },
  {
    name: "Swetank Shandilya",
    contribution:
      "Created CV and JD parsing plus semantic matching and scoring, wired into recruiter workflows.",
    linkedIn: "https://www.linkedin.com/in/swetank-shandilya-368592269/",
    imageUrl: "https://media.licdn.com/dms/image/v2/D5603AQEUaZgz_q_XBQ/profile-displayphoto-shrink_400_400/B56Zr6MI8sLAAg-/0/1765134078829?e=1779321600&v=beta&t=FtgLaxjZ2V5khZZnTMpNalWxy77nntM0dzaDhkiR5KQ",
  },
  {
    name: "Gopi Kant",
    contribution:
      "Integrated payments and billing with credit tracking and reconciliation across the platform.",
    linkedIn: "https://www.linkedin.com/in/gopi-kant/",
    imageUrl: "https://media.licdn.com/dms/image/v2/D4D03AQFw19KHczAiMw/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1694977800587?e=1779321600&v=beta&t=vkKNKcANYGCl0iS-5TrsRZyrpaaN3mwXduxOYGqJCDk",
  },
  {
    name: "Roshan Yadav",
    contribution:
      "Owned deployments and built candidate, recruiter, and admin authentication and onboarding flows.",
    linkedIn: "https://www.linkedin.com/in/roshanality/",
    imageUrl: "https://media.licdn.com/dms/image/v2/D5603AQFysSvw7-gsWg/profile-displayphoto-crop_800_800/B56ZsXruVZG4AI-/0/1765628898269?e=1779321600&v=beta&t=3iV_D-ejqblIUOUf8hPvc4hYCMNfSZZNM0yvbp_Ch38",
  },
  {
    name: "Sumedh Deshkar",
    contribution:
      "Delivered proctoring gaze heatmaps and parallel request handling for analysis workflows.",
    linkedIn: "https://www.linkedin.com/in/deshkar/",
    imageUrl: "https://media.licdn.com/dms/image/v2/D5603AQFcFKvwb8FNgg/profile-displayphoto-shrink_400_400/profile-displayphoto-shrink_400_400/0/1716150437485?e=1779321600&v=beta&t=OjXq_W6rIO7kMie-jPAS0jWYpoKEvblg1H4rbuSd6h8",
  },
  {
    name: "Vaibhav K",
    contribution:
      "Led testing of the question generation pipeline, including difficulty tuning using JD/CV, and contributed to AI cost estimation.",
    linkedIn: "https://www.linkedin.com/in/vaibhav-kumar-368592269/",
    imageUrl: "https://media.licdn.com/dms/image/v2/D5603AQE8n9XoQeZzjA/profile-displayphoto-shrink_400_400/B56Zr6MI8sLAAg-/0/1765134078829?e=1779321600&v=beta&t=FtgLaxjZ2V5khZZnTMpNalWxy77nntM0dzaDhkiR5KQ",
  }
];

const TeamMemberAvatar = ({ member }) => {
  const [imgFailed, setImgFailed] = useState(false);
  
  const initials = member.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const gradients = [
    "linear-gradient(135deg, #6366f1 0%, #a855f7 100%)", // Indigo to Purple
    "linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)", // Cyan to Blue
    "linear-gradient(135deg, #f97316 0%, #ec4899 100%)", // Orange to Pink
    "linear-gradient(135deg, #10b981 0%, #059669 100%)", // Emerald to Teal
    "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)", // Amber to Orange
    "linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%)", // Pink to Purple
    "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)", // Blue to Dark Blue
    "linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)", // Teal to Dark Teal
  ];

  const hashString = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return Math.abs(hash);
  };

  const gradientIndex = hashString(member.name) % gradients.length;
  const gradient = gradients[gradientIndex];

  if (imgFailed || !member.imageUrl) {
    return (
      <div
        className={styles.avatarFallback}
        style={{ background: gradient }}
        title={`${member.name} profile`}
      >
        <span className={styles.avatarInitials}>{initials}</span>
        <div className={styles.fallbackPattern} />
      </div>
    );
  }

  return (
    <img
      src={member.imageUrl}
      alt={`${member.name} profile`}
      className={styles.avatar}
      loading="lazy"
      onError={() => setImgFailed(true)}
    />
  );
};

const TeamPage = () => {
  return (
    <div className={styles.teamPage}>
      <section className={styles.hero}>
        <div className={styles.heroPanel}>
          <div className={styles.heroContent}>
          {/* <span className={styles.kicker}>Team</span> */}
          <h1 className={styles.title}>Meet the Developers</h1>
          <p className={styles.subtitle}>
            This team shipped the core platform, from HR workflows and proctoring to
            GenAI evaluation, CV-JD matching, payments, and production readiness.
          </p>
          </div>
        </div>
      </section>

      <section className={styles.gridSection}>
        <div className={styles.grid}>
          {teamMembers.map((member) => (
            <article className={styles.card} key={member.name}>
              <div className={styles.cardHeader}>
                <div className={styles.avatarWrap}>
                  <TeamMemberAvatar member={member} />
                  <a
                    className={styles.linkedInOverlay}
                    href={member.linkedIn}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`LinkedIn profile of ${member.name}`}
                    title={`LinkedIn profile of ${member.name}`}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path
                        d="M4.98 3.5c0 1.38-1.11 2.5-2.48 2.5S0 4.88 0 3.5 1.11 1 2.5 1s2.48 1.12 2.48 2.5zM0.5 22h4V8.5h-4V22zM8.5 8.5h3.8v1.85h.05c.53-1 1.85-2.05 3.8-2.05 4.05 0 4.8 2.67 4.8 6.15V22h-4v-6.45c0-1.54-.03-3.52-2.15-3.52-2.15 0-2.48 1.68-2.48 3.4V22h-4V8.5z"
                        fill="currentColor"
                      />
                    </svg>
                  </a>
                </div>
                <h3 className={styles.name}>{member.name}</h3>
              </div>
              <div className={styles.cardBody}>
                <p className={styles.contribution}>{member.contribution}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
};

export default TeamPage;

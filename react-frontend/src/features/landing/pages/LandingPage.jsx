import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "./LandingPage.module.css";
import usePricingCatalog from 'shared/hooks/usePricingCatalog';

const LandingPage = () => {
  const {catalog:pricing,error:pricingError,reload:reloadPricing}=usePricingCatalog();
  const credits=key=>pricing?.credits?.[key] ?? 'See current price';
  const packAmount=key=>pricing?.packs?.[key] ? (pricing.packs[key].price_paise/100).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}) : 'See wallet';
  const packCredits=key=>pricing?.packs?.[key]?.credits_allocated?.toLocaleString() ?? 'See wallet for';
  const navigate = useNavigate();
  const [isScrolled, setIsScrolled] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [workflowTab, setWorkflowTab] = useState("candidate"); // "candidate" or "recruiter"
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [animationPaused, setAnimationPaused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [pageVisible, setPageVisible] = useState(true);

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)') ?? {matches:true};
    const updateMotion = () => setReducedMotion(media.matches);
    const updateVisibility = () => setPageVisible(!document.hidden);
    updateMotion(); updateVisibility();
    media.addEventListener?.('change', updateMotion);
    document.addEventListener('visibilitychange', updateVisibility);
    return () => {
      media.removeEventListener?.('change', updateMotion);
      document.removeEventListener('visibilitychange', updateVisibility);
    };
  }, []);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const close = event => { if (event.key === 'Escape') { setMobileMenuOpen(false); document.getElementById('landing-menu-toggle')?.focus(); } };
    document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [mobileMenuOpen]);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    document.title = "GenHire | AI Screening & Online Assessments";

    const description = document.querySelector('meta[name="description"]');
    if (description) {
      description.setAttribute(
        "content",
        "GenHire connects CV screening, AI interviews and role-based online assessments with coding, SQL and MCQs. Recruiters control each next round; candidates can prepare with interviews and mock OAs."
      );
    }
  }, []);

  // Auto-rotate workflow steps within the selected tab
  useEffect(() => {
    if (animationPaused || reducedMotion || !pageVisible) return;
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % 4);
    }, 2000);
    return () => clearInterval(interval);
  }, [workflowTab, animationPaused, reducedMotion, pageVisible]);

  const features = [
    { icon: "🎙", title: "AI screening interviews", description: "Review CV fit, structured interview answers and proctoring signals before deciding who moves forward.", gradient: "linear-gradient(135deg, #667eea, #764ba2)" },
    { icon: "💻", title: "Role-based online assessments", description: "Build OAs with coding, SQL and single- or multiple-answer MCQs. Mix question types to match the role.", gradient: "linear-gradient(135deg, #11998e, #38ef7d)" },
    { icon: "✍", title: "AI, manual or hybrid questions", description: "Start with a role preset, describe what AI should generate, or add your own questions, testcases and marks.", gradient: "linear-gradient(135deg, #4facfe, #00b4d8)" },
    { icon: "🧭", title: "Your hiring process, your rules", description: "Set screening thresholds and application deadlines. Invite qualified candidates automatically or review them before choosing an OA or company round.", gradient: "linear-gradient(135deg, #6366f1, #8b5cf6)" },
    { icon: "🛡", title: "Secure assessment sessions", description: "Use Secure Browser for OAs, with timed sections, saved answers and configured integrity controls. Review signals alongside performance.", gradient: "linear-gradient(135deg, #f97316, #ec4899)" },
    { icon: "🎯", title: "Practice with useful feedback", description: "Prepare for AI interviews and, where available, role-based mock OAs. Review scores and feedback to decide what to work on next.", gradient: "linear-gradient(135deg, #fa709a, #d946ef)" }
  ];

  const candidateSteps = [
    { step: 1, title: "Find a role & apply", description: "Build your profile, upload your CV and apply before the job deadline.", icon: "🔎" },
    { step: 2, title: "Complete AI screening", description: "Take your screening interview within its window and track your application status.", icon: "🎙" },
    { step: 3, title: "Take an OA if invited", description: "Complete the role's coding, SQL or MCQ sections in Secure Browser before the assessment closes.", icon: "💻" },
    { step: 4, title: "Hear about company rounds", description: "The recruiter reviews results and decides the next technical, HR or other company-led round.", icon: "🤝" }
  ];

  const recruiterSteps = [
    { step: 1, title: "Design the role & timeline", description: "Create the JD, choose an optional OA and set questions, marks, timing and application deadlines.", icon: "📝" },
    { step: 2, title: "Screen with clear thresholds", description: "Review CV fit, interview scores and integrity signals using your screening criteria.", icon: "🎙" },
    { step: 3, title: "Assess the right skills", description: "Automatically invite screening-cleared candidates or review them first. Use coding, SQL and MCQs as needed.", icon: "💻" },
    { step: 4, title: "Review & arrange next rounds", description: "Review scores, release results, export shortlisted contacts or send approved company-round messages.", icon: "📊" }
  ];

  const stats = [
    { value: "Screen", label: "CV fit + AI interviews" },
    { value: "Assess", label: "Coding, SQL + MCQs" },
    { value: "Decide", label: "Recruiter-controlled next rounds" },
    { value: "Prepare", label: "Interview + OA practice" }
  ];

  const roleExamples = [
    { title: "Software engineering", description: "Combine coding problems with difficulty, language and testcase choices, plus knowledge MCQs." },
    { title: "Data & analytics", description: "Assess SQL query skills and analytical knowledge with weighted datasets and MCQs." },
    { title: "Product & DevOps", description: "Start with a role preset and tailor knowledge questions and relevant technical tasks to the position." }
  ];

  const seoServices = [
    { title: "One role setup", description: "Plan screening and an optional OA while creating the role. Choose total or section timing and publish reviewed content." },
    { title: "A workspace for coding", description: "Candidates edit code, run sample or custom input and submit against hidden tests. Weighted passing tests determine coding marks." },
    { title: "SQL & MCQ assessment", description: "Use public sample and hidden SQL datasets, single-answer MCQs or multiple-answer MCQs with configurable marks." },
    { title: "Clear application stages", description: "Distinguish screening cleared, OA invited, assessment outcomes and company rounds. Clearing screening does not guarantee another invitation." },
    { title: "Company-led next rounds", description: "Your team chooses what follows the OA. Track decisions, export contacts and prepare approved messages for the shortlist." },
    { title: "Practice before the real thing", description: "Candidates can use separate interview and mock OA practice. Availability and the exact credit quote are shown before purchase." }
  ];

  const creditUsage = {
    candidate: [
      { action: "Practice Interview", cost: `${credits('practice_interview')} credits` },
      { action: "Practice Interview + Proctoring", cost: `${credits('practice_interview_proctored')} credits` },
      { action: "Role-based mock OA (when available)", cost: `${credits('mock_oa')} credits base` },
      { action: "Signup Welcome Bonus", cost: `${credits('signup_bonus')} free`, highlight: true },
    ],
    recruiter: [
      { action: "Real Candidate Interview", cost: `${credits('screening')} credits` },
      { action: "Interview + Proctoring", cost: `${credits('screening_proctored')} credits` },
      { action: "AI JD + selected OA questions", cost: `${credits('ai_jd')} credits` },
      { action: "Candidate Invite (per email)", cost: `${credits('candidate_invite')} credits` },
      { action: "OA setup (when available)", cost: `${credits('oa_setup')} credits` },
      { action: "Accepted recruitment OA attempt", cost: `${credits('oa_attempt')} credits base` },
      { action: "Signup Welcome Bonus", cost: `${credits('signup_bonus')} free`, highlight: true },
    ],
  };

  const faqs = [
    {
      question: "What is GenHire?",
      answer:
        "GenHire connects CV screening, AI interviews, role-based online assessments and recruiter-led next rounds. Candidates can also prepare with interview and mock OA practice."
    },
    {
      question: "Does GenHire support AI CV screening?",
      answer:
        "Yes. GenHire screens CVs and resumes against job descriptions, scores candidate fit, highlights gaps, and helps recruiters shortlist qualified candidates."
    },
    {
      question: "Can GenHire automate interviews?",
      answer:
        "Yes. GenHire supports AI-powered interviews with answer evaluation, reports, transcripts, proctoring signals, and analytics for hiring decisions."
    },
    {
      question: "What can an online assessment include?",
      answer: "Recruiters can combine coding, SQL and single- or multiple-answer MCQs, use AI-generated or manual questions, and set marks and assessment timing. Coding supports sample/custom input runs and hidden-test grading; SQL runs use sample datasets and submissions are checked against the authored datasets."
    },
    {
      question: "Does everyone who clears screening take an OA?",
      answer: "No. The recruiter can enable automatic invitations, review screening-cleared candidates first, or choose a different next round. Follow the status and deadlines on your application; the company arranges its own later interviews."
    },
    {
      question: "Can candidates practice an OA?",
      answer: "Role-based mock OAs are available when practice assessments are enabled. Review the quoted credit cost before confirming, complete the timed assessment in Secure Browser, then review your score and feedback. Practice is separate from real job applications."
    },
    {
      question: "How do wallet credits work?",
      answer:
        "Current server prices are shown below. OA purchases show an exact quote before approval. Reservations, capture and technical-failure returns follow the disclosed operation policy; mock OA generation captures when validated content is ready. New attempts are separate purchases. Wallet history records charges and returned funds."
    },
    {
      question: "What is interview proctoring?",
      answer:
        "Proctoring uses AI-powered gaze tracking and behaviour analysis to monitor candidates during the session. Integrity signals help recruiters review a session; they are not proof of misconduct and should be considered alongside the candidate's performance."
    },
    {
      question: "Can I try GenHire before paying?",
      answer:
        `New accounts receive the configured signup bonus: ${credits('signup_bonus')} credits. Current activity prices determine how far that balance goes.`
    }
  ];

  return (
    <div className={styles.landingPage}>
      <a className={styles.skipLink} href="#main-content">Skip to content</a>
      {/* Navigation */}
      <nav className={`${styles.navbar} ${isScrolled ? styles.scrolled : ""}`}>
        <div className={styles.navContainer}>
          <Link to="/" className={styles.logo}>
            <div className={styles.logoIcon}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 7h-9"></path>
                <path d="M14 17H5"></path>
                <circle cx="17" cy="17" r="3"></circle>
                <circle cx="7" cy="7" r="3"></circle>
              </svg>
            </div>
            <span>GenHire</span>
          </Link>

          <div className={styles.navLinks}>
            <a href="#features">Features</a>
            <a href="#how-it-works">How It Works</a>
            <a href="#pricing">Pricing</a>
            <a href="#credits">Credits</a>
            <a href="#roles">Roles</a>
          </div>

          <div className={styles.navActions}>
            <button
              className={styles.loginBtn}
              onClick={() => navigate("/login")}
            >
              Login
            </button>
            <button
              className={styles.signupBtn}
              onClick={() => navigate("/register")}
            >
              Get Started Free
            </button>
          </div>

          <button 
            className={styles.mobileMenuBtn}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            id="landing-menu-toggle"
            aria-expanded={mobileMenuOpen}
            aria-controls="landing-mobile-menu"
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Nav Drawer */}
        <div id="landing-mobile-menu" inert={!mobileMenuOpen} aria-hidden={!mobileMenuOpen} className={`${styles.mobileDrawer} ${mobileMenuOpen ? styles.drawerOpen : ''}`}>
          <div className={styles.mobileNavLinks}>
            <a href="#features" onClick={() => setMobileMenuOpen(false)}>Features</a>
            <a href="#how-it-works" onClick={() => setMobileMenuOpen(false)}>How It Works</a>
            <a href="#pricing" onClick={() => setMobileMenuOpen(false)}>Pricing</a>
            <a href="#roles" onClick={() => setMobileMenuOpen(false)}>Roles</a>
            <a href="#credits" onClick={() => setMobileMenuOpen(false)}>Credits</a>
          </div>
          <div className={styles.mobileNavActions}>
            <button
              className={styles.loginBtn}
              onClick={() => { setMobileMenuOpen(false); navigate("/login"); }}
            >
              Login
            </button>
            <button
              className={styles.signupBtn}
              onClick={() => { setMobileMenuOpen(false); navigate("/register"); }}
            >
              Get Started Free
            </button>
          </div>
        </div>
        
        {mobileMenuOpen && (
          <div className={styles.drawerOverlay} onClick={() => setMobileMenuOpen(false)}></div>
        )}
      </nav>

      <main id="main-content" tabIndex={-1}>
      {/* Hero Section */}
      <section className={styles.hero}>
        <div className={styles.heroBackground}>
          <div className={styles.heroGradient}></div>
          <div className={styles.heroParticles}></div>
        </div>

        <div className={styles.heroContent}>
          <div className={styles.heroText}>
            <div className={styles.heroBadge}>
              <span className={styles.badgePulse}></span>
              GenHire AI Recruitment Platform
            </div>
            <h1 className={styles.heroTitle}>
              Screen with AI. Assess skills. <br />
              <span className={styles.gradientText}>Choose what comes next.</span>
            </h1>
            <p className={styles.heroSubtitle}>
              Bring CV screening, AI interviews and role-based online assessments
              into one hiring journey. Test coding, SQL and MCQ skills, review the
              evidence, and choose the next round for your team.
            </p>
            <div className={styles.heroCta}>
              <button
                className={styles.primaryBtn}
                onClick={() => navigate("/register")}
              >
                <span>Join as a candidate</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M12 5l7 7-7 7"></path>
                </svg>
              </button>
              <button
                className={styles.secondaryBtn}
                onClick={() => navigate("/recruiter-signup")}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                  <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
                </svg>
                <span>Create a hiring workspace</span>
              </button>
            </div>
            <div className={styles.heroTrust}>
              <span>Built around the skills your role needs</span>
              <div className={styles.trustLogos}>
                <span className={styles.trustLogo}>Coding</span>
                <span className={styles.trustLogo}>SQL</span>
                <span className={styles.trustLogo}>MCQs</span>
                <span className={styles.trustLogo}>AI screening</span>
              </div>
            </div>
          </div>

          <div className={styles.heroVisual}>
            <div className={styles.dashboardPreview}>
              <div className={styles.previewHeader}>
                <div className={styles.previewDots}>
                  <span></span><span></span><span></span>
                </div>
                <span>Hiring pipeline / Example</span>
              </div>
              <div className={styles.previewContent}>
                <div className={styles.previewCard}>
                  <div className={styles.candidateAvatar}>JD</div>
                  <div className={styles.candidateInfo}>
                    <h4>Sample Candidate</h4>
                    <p>Software Engineer</p>
                  </div>
                  <div className={styles.scoreCircle}>
                    <svg viewBox="0 0 36 36">
                      <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#e2e8f0" strokeWidth="3"></path>
                      <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#10b981" strokeWidth="3" strokeDasharray="85, 100"></path>
                    </svg>
                    <span>85%</span>
                  </div>
                </div>
                <div className={styles.previewMetrics}>
                  <div className={styles.metric}>
                    <span className={styles.metricLabel}>CV Score</span>
                    <div className={styles.metricBar}>
                      <div style={{ width: "78%" }}></div>
                    </div>
                    <span className={styles.metricValue}>78%</span>
                  </div>
                  <div className={styles.metric}>
                    <span className={styles.metricLabel}>Interview</span>
                    <div className={styles.metricBar}>
                      <div style={{ width: "85%", background: "#10b981" }}></div>
                    </div>
                    <span className={styles.metricValue}>85%</span>
                  </div>
                  <div className={styles.metric}>
                    <span className={styles.metricLabel}>OA score</span>
                    <div className={styles.metricBar}>
                      <div style={{ width: "92%", background: "#8b5cf6" }}></div>
                    </div>
                    <span className={styles.metricValue}>92%</span>
                  </div>
                </div>
              </div>
            </div>
            <div className={styles.floatingCards}>
              {/* Above dashboard - Position 1 (top-left) */}
              <div className={`${styles.floatingCard} ${styles.card1}`}>
                <span className={styles.floatingIcon}>📈</span>
                <span>Real-time Analytics</span>
              </div>
              {/* Above dashboard - Position 2 (top-right) */}
              <div className={`${styles.floatingCard} ${styles.card2}`}>
                <span className={styles.floatingIcon}>🔒</span>
                <span>Secure Proctoring</span>
              </div>
              {/* Below dashboard - Position 5 (left side) */}
              <div className={`${styles.floatingCard} ${styles.card3}`}>
                <span className={styles.floatingIcon}>🎯</span>
                <span>Role-based OAs</span>
              </div>
              {/* Below dashboard - Position 3 (bottom center) */}
              <div className={`${styles.floatingCard} ${styles.card4}`}>
                <span className={styles.floatingIcon}>✓</span>
                <span>Screening / OA</span>
              </div>
              {/* Below dashboard - Position 4 (bottom right) */}
              <div className={`${styles.floatingCard} ${styles.card5}`}>
                <span className={styles.floatingIcon}>⚡</span>
                <span>Flexible next rounds</span>
              </div>
              {/* Below dashboard - Position 6 (right side) */}
              <div className={`${styles.floatingCard} ${styles.card6}`}>
                <span className={styles.floatingIcon}>📊</span>
                <span>Smart Reports</span>
              </div>
            </div>
          </div>
        </div>

        <div className={styles.heroWave}>
          <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M0 120L60 105C120 90 240 60 360 45C480 30 600 30 720 37.5C840 45 960 60 1080 67.5C1200 75 1320 75 1380 75L1440 75V120H1380C1320 120 1200 120 1080 120C960 120 840 120 720 120C600 120 480 120 360 120C240 120 120 120 60 120H0Z" fill="white"></path>
          </svg>
        </div>
      </section>

      {/* Stats Section */}
      <section className={styles.statsSection}>
        <div className={styles.container}>
          <div className={styles.statsGrid}>
            {stats.map((stat, index) => (
              <div key={index} className={styles.statItem}>
                <span className={styles.statValue}>{stat.value}</span>
                <span className={styles.statLabel}>{stat.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className={styles.featuresSection}>
        <div className={styles.container}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>Features</span>
            <h2 className={styles.sectionTitle}>
              Everything You Need for <span className={styles.gradientText}>AI Hiring</span>
            </h2>
            <p className={styles.sectionSubtitle}>
              Screening, skills assessment and next-round decisions, connected in one workspace.
            </p>
          </div>

          <div className={styles.featuresGrid}>
            {features.map((feature, index) => (
              <div key={index} className={styles.featureCard}>
                <div
                  className={styles.featureIcon}
                  style={{ background: feature.gradient }}
                >
                  <span>{feature.icon}</span>
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SEO Services Section */}
      <section className={styles.featuresSection} aria-labelledby="genhire-services-title">
        <div className={styles.container}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>AI Recruitment Software</span>
            <h2 id="genhire-services-title" className={styles.sectionTitle}>
              What <span className={styles.gradientText}>GenHire</span> Does for Hiring Teams
            </h2>
            <p className={styles.sectionSubtitle}>
              Start with the role, choose the skills to assess, and keep candidates
              informed as they move through your hiring process.
            </p>
          </div>

          <div className={styles.featuresGrid}>
            {seoServices.map((service, index) => (
              <article key={index} className={styles.featureCard}>
                <h3>{service.title}</h3>
                <p>{service.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className={styles.howItWorksSection}>
        <div className={styles.container}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>How It Works</span>
            <h2 className={styles.sectionTitle}>
              From application to <span className={styles.gradientText}>next-round decisions</span>
            </h2>
            <p className={styles.sectionSubtitle}>
              An OA is optional. Recruiters decide when it fits and what follows it.
            </p>
          </div>

          <div className={styles.workflowTabs} role="group" aria-label="Choose a hiring journey">
            <button
              aria-pressed={workflowTab === "candidate"}
              className={`${styles.workflowTab} ${workflowTab === "candidate" ? styles.active : ""}`}
              onClick={() => { setWorkflowTab("candidate"); setActiveStep(0); }}
            >
              <span className={styles.tabIcon}>👤</span>
              For Candidates
            </button>
            <button
              aria-pressed={workflowTab === "recruiter"}
              className={`${styles.workflowTab} ${workflowTab === "recruiter" ? styles.active : ""}`}
              onClick={() => { setWorkflowTab("recruiter"); setActiveStep(0); }}
            >
              <span className={styles.tabIcon}>💼</span>
              For Recruiters
            </button>
          </div>

          <div className={styles.animationControls}>
            <span>{reducedMotion ? 'Motion reduced. Select any step to explore.' : 'A new step every 2 seconds. Select one to pause and read.'}</span>
            {!reducedMotion && <button type="button" aria-pressed={animationPaused} onClick={() => setAnimationPaused(value => !value)}>{animationPaused ? 'Resume animation' : 'Pause animation'}</button>}
          </div>
          <div className={styles.workflowContent}>
            <div className={styles.workflowSteps}>
              {(workflowTab === "candidate" ? candidateSteps : recruiterSteps).map((item, index) => (
                <button
                  type="button"
                  aria-label={`Step ${item.step}: ${item.title}`}
                  aria-pressed={activeStep === index}
                  key={index}
                  className={`${styles.workflowStep} ${activeStep === index ? styles.activeStep : ""}`}
                  onClick={() => { setActiveStep(index); setAnimationPaused(true); }}
                >
                  <span className={styles.stepNumber}>
                    <span>{item.step}</span>
                  </span>
                  <span className={styles.stepContent}>
                    <span className={styles.stepIcon}>{item.icon}</span>
                    <strong>{item.title}</strong>
                    <span className={styles.stepDescription}>{item.description}</span>
                  </span>
                  {index < 3 && <span className={styles.stepConnector}></span>}
                </button>
              ))}
            </div>

            <div className={styles.workflowVisual}>
              <div className={styles.visualCard}>
                {workflowTab === "candidate" ? (
                  <div className={styles.candidateVisual}>
                    <div className={styles.visualHeader}>
                      <div className={styles.visualAvatar}>
                        <span>👤</span>
                      </div>
                      <div>
                        <h4>Candidate Journey</h4>
                        <p>Step {activeStep + 1} of 4</p>
                      </div>
                    </div>
                    <div className={styles.visualProgress}>
                      {[0, 1, 2, 3].map((i) => (
                        <div
                          key={i}
                          className={`${styles.progressDot} ${i <= activeStep ? styles.completed : ""}`}
                        ></div>
                      ))}
                    </div>
                    <div className={styles.visualContent}>
                      <span className={styles.bigIcon}>{candidateSteps[activeStep].icon}</span>
                      <h3>{candidateSteps[activeStep].title}</h3>
                      <p>{candidateSteps[activeStep].description}</p>
                    </div>
                  </div>
                ) : (
                  <div className={styles.recruiterVisual}>
                    <div className={styles.visualHeader}>
                      <div className={styles.visualAvatar} style={{ background: "linear-gradient(135deg, #10b981 0%, #059669 100%)" }}>
                        <span>💼</span>
                      </div>
                      <div>
                        <h4>Recruiter Journey</h4>
                        <p>Step {activeStep + 1} of 4</p>
                      </div>
                    </div>
                    <div className={styles.visualProgress}>
                      {[0, 1, 2, 3].map((i) => (
                        <div
                          key={i}
                          className={`${styles.progressDot} ${i <= activeStep ? styles.completed : ""}`}
                          style={{ background: i <= activeStep ? "#10b981" : "" }}
                        ></div>
                      ))}
                    </div>
                    <div className={styles.visualContent}>
                      <span className={styles.bigIcon}>{recruiterSteps[activeStep].icon}</span>
                      <h3>{recruiterSteps[activeStep].title}</h3>
                      <p>{recruiterSteps[activeStep].description}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className={styles.pricingSection}>
        <div className={styles.container}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>Pricing</span>
            <h2 className={styles.sectionTitle}>
              Simple, Transparent <span className={styles.gradientText}>Wallet Recharge</span>
            </h2>
            <p className={styles.sectionSubtitle}>
              Use wallet credits for screening, assessments and practice. Review each activity's current price before confirming.
            </p>
            <p className={styles.sectionSubtitle}>
              New accounts receive the configured one-time signup bonus: {credits('signup_bonus')} credits.
              {pricingError && <button onClick={reloadPricing}>Retry current prices</button>}
            </p>
          </div>

          <h3 className={styles.pricingGroupTitle}>Candidate Plans</h3>
          <div className={styles.pricingGrid}>
            <div className={styles.pricingCard}>
              <div className={styles.pricingHeader}>
                <h3>Signup Bonus</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.amount}>Free</span>
                </div>
                <p>{credits('signup_bonus')} one-time wallet credits on signup</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> {credits('signup_bonus')} credits added on first signup</li>
                <li><span>✓</span> Non-expiring wallet credits</li>
                <li><span>✓</span> Auto-applied, no payment required</li>
                <li><span>✓</span> Available to every new account</li>
              </ul>
              <button className={styles.pricingBtn} onClick={() => navigate("/register")}>
                Claim on Signup
              </button>
            </div>

            <div className={`${styles.pricingCard} ${styles.popular}`}>
              <div className={styles.popularBadge}>Wallet recharge</div>
              <div className={styles.pricingHeader}>
                <h3>Candidate Pro</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.currency}>{pricing?.currency || ''}</span>
                  <span className={styles.amount}>{packAmount('candidate_pro')}</span>
                  <span className={styles.period}>one-time</span>
                </div>
                <p>{packCredits('candidate_pro')} non-expiring wallet credits</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> {packCredits('candidate_pro')} non-expiring credits</li>
                <li><span>✓</span> Interview practice and available mock OAs</li>
                <li><span>✓</span> Real-time wallet activity tracking</li>
                <li><span>✓</span> {credits('signup_bonus')} signup bonus credits on first signup</li>
              </ul>
              <button className={`${styles.pricingBtn} ${styles.primaryPricingBtn}`} onClick={() => navigate("/register")}>
                Start and Recharge
              </button>
            </div>

            <div className={styles.pricingCard}>
              <div className={styles.pricingHeader}>
                <h3>Candidate Max</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.currency}>{pricing?.currency || ''}</span>
                  <span className={styles.amount}>{packAmount('candidate_max')}</span>
                  <span className={styles.period}>one-time</span>
                </div>
                <p>{packCredits('candidate_max')} non-expiring wallet credits</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> {packCredits('candidate_max')} non-expiring credits</li>
                <li><span>✓</span> Interview practice and available mock OAs</li>
                <li><span>✓</span> Real-time wallet activity tracking</li>
                <li><span>✓</span> Recharge anytime</li>
              </ul>
              <button className={`${styles.pricingBtn} ${styles.primaryPricingBtn}`} onClick={() => navigate("/register")}>
                Start and Recharge
              </button>
            </div>
          </div>

          <h3 className={styles.pricingGroupTitle}>Recruiter Plans</h3>
          <div className={styles.pricingGrid}>
            <div className={styles.pricingCard}>
              <div className={styles.pricingHeader}>
                <h3>Signup Bonus</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.amount}>Free</span>
                </div>
                <p>{credits('signup_bonus')} one-time wallet credits on signup</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> {credits('signup_bonus')} credits added on first signup</li>
                <li><span>✓</span> Non-expiring wallet credits</li>
                <li><span>✓</span> Auto-applied, no payment required</li>
                <li><span>✓</span> Available to every new account</li>
              </ul>
              <button className={styles.pricingBtn} onClick={() => navigate("/recruiter-signup")}>
                Claim on Signup
              </button>
            </div>

            <div className={`${styles.pricingCard} ${styles.popular}`}>
              <div className={styles.popularBadge}>Wallet recharge</div>
              <div className={styles.pricingHeader}>
                <h3>Recruiter Pro</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.currency}>{pricing?.currency || ''}</span>
                  <span className={styles.amount}>{packAmount('recruiter_pro')}</span>
                  <span className={styles.period}>one-time</span>
                </div>
                <p>{packCredits('recruiter_pro')} non-expiring wallet credits</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> {packCredits('recruiter_pro')} non-expiring credits</li>
                <li><span>✓</span> AI JD generation billed at fixed credits</li>
                <li><span>✓</span> AI screening and quoted OA activities</li>
                <li><span>✓</span> Candidate email invites at {credits('candidate_invite')} credits each</li>
                <li><span>✓</span> {credits('signup_bonus')} signup bonus credits on first signup</li>
              </ul>
              <button className={`${styles.pricingBtn} ${styles.primaryPricingBtn}`} onClick={() => navigate("/recruiter-signup")}>
                Start and Recharge
              </button>
            </div>

            <div className={styles.pricingCard}>
              <div className={styles.pricingHeader}>
                <h3>Recruiter Max</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.currency}>{pricing?.currency || ''}</span>
                  <span className={styles.amount}>{packAmount('recruiter_max')}</span>
                  <span className={styles.period}>one-time</span>
                </div>
                <p>{packCredits('recruiter_max')} non-expiring wallet credits</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> {packCredits('recruiter_max')} non-expiring credits</li>
                <li><span>✓</span> AI JD generation billed at fixed credits</li>
                <li><span>✓</span> AI screening and quoted OA activities</li>
                <li><span>✓</span> Candidate email invites at {credits('candidate_invite')} credits each</li>
                <li><span>✓</span> Recharge anytime</li>
              </ul>
              <button className={styles.pricingBtn} onClick={() => navigate("/recruiter-signup")}>
                Start and Recharge
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Credit Usage Section */}
      <section id="credits" className={styles.creditSection}>
        <div className={styles.container}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>How Credits Work</span>
            <h2 className={styles.sectionTitle}>
              Know Exactly <span className={styles.gradientText}>What You Pay</span>
            </h2>
            <p className={styles.sectionSubtitle}>
              Current prices come from the server. One AI drafting price includes the JD and selected OA questions. Candidate attempts and optional extras are quoted separately.
            </p>
          </div>

          <div className={styles.creditGrid}>
            <div className={styles.creditCard}>
              <div className={styles.creditCardHeader}>
                <span className={styles.creditCardEmoji}>👤</span>
                <h3>Candidates</h3>
              </div>
              <div className={styles.creditRows}>
                {creditUsage.candidate.map((row, i) => (
                  <div key={i} className={`${styles.creditRow} ${row.highlight ? styles.creditRowBonus : ""}`}>
                    <span className={styles.creditAction}>{row.action}</span>
                    <span className={row.highlight ? styles.creditCostFree : styles.creditCost}>{row.cost}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className={styles.creditCard}>
              <div className={styles.creditCardHeader}>
                <span className={styles.creditCardEmoji}>💼</span>
                <h3>Recruiters</h3>
              </div>
              <div className={styles.creditRows}>
                {creditUsage.recruiter.map((row, i) => (
                  <div key={i} className={`${styles.creditRow} ${row.highlight ? styles.creditRowBonus : ""}`}>
                    <span className={styles.creditAction}>{row.action}</span>
                    <span className={row.highlight ? styles.creditCostFree : styles.creditCost}>{row.cost}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <p className={styles.creditNote}>
            Charges follow each activity quote. Mock OA generation is charged when validated content is ready; accepted recruitment OA attempts can also incur a charge. Review wallet history for charges and returns.
          </p>
        </div>
      </section>

      <section id="roles" className={styles.featuresSection} aria-labelledby="roles-title">
        <div className={styles.container}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>Beyond software engineering</span>
            <h2 id="roles-title" className={styles.sectionTitle}>Assess for the <span className={styles.gradientText}>role you are hiring</span></h2>
            <p className={styles.sectionSubtitle}>Use a preset as a starting point, then review and tailor every question to your requirements.</p>
          </div>
          <div className={styles.featuresGrid}>{roleExamples.map(role => <article key={role.title} className={styles.featureCard}><h3>{role.title}</h3><p>{role.description}</p></article>)}</div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className={styles.featuresSection} aria-labelledby="genhire-faq-title">
        <div className={styles.container}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>FAQ</span>
            <h2 id="genhire-faq-title" className={styles.sectionTitle}>
              Screening, OAs and <span className={styles.gradientText}>next rounds</span>
            </h2>
          </div>

          <div className={styles.featuresGrid}>
            {faqs.map((faq, index) => (
              <article key={index} className={styles.featureCard}>
                <h3>{faq.question}</h3>
                <p>{faq.answer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className={styles.ctaSection}>
        <div className={styles.container}>
          <div className={styles.ctaContent}>
            <h2>Ready to Automate Hiring with GenHire?</h2>
            <p>Screen with AI, assess role-specific skills and keep the next hiring decision in your hands.</p>
            <div className={styles.ctaButtons}>
              <button
                className={styles.ctaPrimary}
                onClick={() => navigate("/register")}
              >
                Get Started Free
              </button>
              <button
                className={styles.ctaSecondary}
                onClick={() => navigate("/login")}
              >
                Login to Dashboard
              </button>
            </div>
          </div>
        </div>
      </section>

      </main>
      {/* Footer */}
      <footer className={styles.footer}>
        <div className={styles.container}>
          <div className={styles.footerGrid}>
            <div className={styles.footerBrand}>
              <div className={styles.footerLogo}>
                <div className={styles.logoIcon}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 7h-9"></path>
                    <path d="M14 17H5"></path>
                    <circle cx="17" cy="17" r="3"></circle>
                    <circle cx="7" cy="7" r="3"></circle>
                  </svg>
                </div>
                <span>GenHire</span>
              </div>
              <p>AI screening, role-based online assessments and flexible company rounds. A connected workspace for recruiters and candidates.</p>
            </div>

            <div className={styles.footerLinks}>
              <h4>Explore</h4><ul><li><a href="#features">Screening & OAs</a></li><li><a href="#how-it-works">How it works</a></li><li><a href="#roles">Role-based assessments</a></li><li><a href="#pricing">Wallet pricing</a></li></ul>
            </div>
            <div className={styles.footerLinks}>
              <h4>Candidates</h4><ul><li><Link to="/register">Create an account</Link></li><li><Link to="/login">Applications & practice</Link></li><li><a href="#credits">Practice credits</a></li></ul>
            </div>
            <div className={styles.footerLinks}>
              <h4>Recruiters</h4><ul><li><Link to="/recruiter-signup">Create a workspace</Link></li><li><Link to="/login">Manage hiring</Link></li><li><a href="#credits">Assessment credits</a></li></ul>
            </div>
          </div>

          <div className={styles.footerBottom}>
            <p>© 2026 GenHire. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;

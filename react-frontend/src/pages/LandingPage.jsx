import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "./LandingPage.module.css";

const LandingPage = () => {
  const navigate = useNavigate();
  const [isScrolled, setIsScrolled] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [workflowTab, setWorkflowTab] = useState("candidate"); // "candidate" or "recruiter"

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Auto-rotate workflow steps within the selected tab
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % 4);
    }, 4000);
    return () => clearInterval(interval);
  }, [workflowTab]);

  const features = [
    {
      icon: "🤖",
      title: "AI-Powered Interviews",
      description: "Conduct intelligent mock interviews with real-time feedback and evaluation using advanced AI models.",
      gradient: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
    },
    {
      icon: "📄",
      title: "Smart CV Analysis",
      description: "Get instant CV scoring and matching against job descriptions with detailed skill gap analysis.",
      gradient: "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)"
    },
    {
      icon: "👁️",
      title: "Proctoring & Monitoring",
      description: "Ensure interview integrity with AI-powered gaze tracking and behavior analysis.",
      gradient: "linear-gradient(135deg, #ee0979 0%, #ff6a00 100%)"
    },
    {
      icon: "📊",
      title: "Detailed Analytics",
      description: "Track performance with comprehensive reports, transcripts, and actionable insights.",
      gradient: "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)"
    },
    {
      icon: "🎯",
      title: "Practice Mode",
      description: "Candidates can practice unlimited interviews to improve their skills before the real assessment.",
      gradient: "linear-gradient(135deg, #fa709a 0%, #fee140 100%)"
    },
    {
      icon: "🔒",
      title: "Secure & Reliable",
      description: "Production-grade security with encrypted data storage and GDPR compliance.",
      gradient: "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)"
    }
  ];

  const candidateSteps = [
    { step: 1, title: "Create Profile", description: "Sign up and build your professional profile with CV upload", icon: "👤" },
    { step: 2, title: "Browse Jobs", description: "Explore opportunities matching your skills and preferences", icon: "🔍" },
    { step: 3, title: "Apply & Interview", description: "Submit applications and take AI-powered mock interviews", icon: "🎤" },
    { step: 4, title: "Get Hired", description: "Receive feedback, improve, and land your dream job", icon: "🎉" }
  ];

  const recruiterSteps = [
    { step: 1, title: "Post Jobs", description: "Create detailed job postings with custom requirements", icon: "📝" },
    { step: 2, title: "Auto-Screen", description: "AI automatically scores and ranks candidates by fit", icon: "🤖" },
    { step: 3, title: "Review Results", description: "Access detailed interview reports and analytics", icon: "📊" },
    { step: 4, title: "Hire Talent", description: "Make data-driven hiring decisions confidently", icon: "✅" }
  ];

  const stats = [
    { value: "10K+", label: "Interviews Conducted" },
    { value: "500+", label: "Companies Trust Us" },
    { value: "95%", label: "Satisfaction Rate" },
    { value: "50%", label: "Time Saved" }
  ];

  const testimonials = [
    {
      quote: "GenHire transformed our hiring process. We reduced time-to-hire by 60% while improving candidate quality.",
      author: "Sarah Johnson",
      role: "HR Director, TechCorp",
      avatar: "S"
    },
    {
      quote: "The AI interview practice helped me prepare better than any other platform. I landed my dream job!",
      author: "Rahul Sharma",
      role: "Software Engineer",
      avatar: "R"
    },
    {
      quote: "Detailed analytics and proctoring features give us confidence in our remote hiring decisions.",
      author: "Michael Chen",
      role: "Talent Acquisition Lead",
      avatar: "M"
    }
  ];

  return (
    <div className={styles.landingPage}>
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
            <a href="#testimonials">Testimonials</a>
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
        </div>
      </nav>

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
              AI-Powered Hiring Platform
            </div>
            <h1 className={styles.heroTitle}>
              Transform Your <br />
              <span className={styles.gradientText}>Hiring Process</span>
            </h1>
            <p className={styles.heroSubtitle}>
              Streamline recruitment with AI-powered interviews, smart CV analysis,
              and comprehensive analytics. Save time, reduce bias, and hire the best talent.
            </p>
            <div className={styles.heroCta}>
              <button
                className={styles.primaryBtn}
                onClick={() => navigate("/register")}
              >
                <span>Start Free Trial</span>
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
                <span>For Recruiters</span>
              </button>
            </div>
            <div className={styles.heroTrust}>
              <span>Trusted by leading companies:</span>
              <div className={styles.trustLogos}>
                <div className={styles.trustLogo}>TechCorp</div>
                <div className={styles.trustLogo}>InnovateLabs</div>
                <div className={styles.trustLogo}>DataDriven</div>
                <div className={styles.trustLogo}>FutureHR</div>
              </div>
            </div>
          </div>

          <div className={styles.heroVisual}>
            <div className={styles.dashboardPreview}>
              <div className={styles.previewHeader}>
                <div className={styles.previewDots}>
                  <span></span><span></span><span></span>
                </div>
                <span>Interview Dashboard</span>
              </div>
              <div className={styles.previewContent}>
                <div className={styles.previewCard}>
                  <div className={styles.candidateAvatar}>JD</div>
                  <div className={styles.candidateInfo}>
                    <h4>John Doe</h4>
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
                    <span className={styles.metricLabel}>Proctoring</span>
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
                <span>AI Matching</span>
              </div>
              {/* Below dashboard - Position 3 (bottom center) */}
              <div className={`${styles.floatingCard} ${styles.card4}`}>
                <span className={styles.floatingIcon}>✓</span>
                <span>Interview Complete</span>
              </div>
              {/* Below dashboard - Position 4 (bottom right) */}
              <div className={`${styles.floatingCard} ${styles.card5}`}>
                <span className={styles.floatingIcon}>⚡</span>
                <span>Fast Screening</span>
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
              Everything You Need for <span className={styles.gradientText}>Smart Hiring</span>
            </h2>
            <p className={styles.sectionSubtitle}>
              Powerful tools designed to streamline your recruitment process from start to finish
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

      {/* How It Works Section */}
      <section id="how-it-works" className={styles.howItWorksSection}>
        <div className={styles.container}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>How It Works</span>
            <h2 className={styles.sectionTitle}>
              Simple Steps to <span className={styles.gradientText}>Success</span>
            </h2>
            <p className={styles.sectionSubtitle}>
              Whether you're a candidate or recruiter, our platform makes the process seamless
            </p>
          </div>

          <div className={styles.workflowTabs}>
            <button
              className={`${styles.workflowTab} ${workflowTab === "candidate" ? styles.active : ""}`}
              onClick={() => { setWorkflowTab("candidate"); setActiveStep(0); }}
            >
              <span className={styles.tabIcon}>👤</span>
              For Candidates
            </button>
            <button
              className={`${styles.workflowTab} ${workflowTab === "recruiter" ? styles.active : ""}`}
              onClick={() => { setWorkflowTab("recruiter"); setActiveStep(0); }}
            >
              <span className={styles.tabIcon}>💼</span>
              For Recruiters
            </button>
          </div>

          <div className={styles.workflowContent}>
            <div className={styles.workflowSteps}>
              {(workflowTab === "candidate" ? candidateSteps : recruiterSteps).map((item, index) => (
                <div
                  key={index}
                  className={`${styles.workflowStep} ${activeStep === index ? styles.activeStep : ""}`}
                  onClick={() => setActiveStep(index)}
                >
                  <div className={styles.stepNumber}>
                    <span>{item.step}</span>
                  </div>
                  <div className={styles.stepContent}>
                    <div className={styles.stepIcon}>{item.icon}</div>
                    <h4>{item.title}</h4>
                    <p>{item.description}</p>
                  </div>
                  {index < 3 && <div className={styles.stepConnector}></div>}
                </div>
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
              Non-expiring credits, fixed deductions, and full transaction visibility.
            </p>
            <p className={styles.sectionSubtitle}>
              Every new account gets a one-time 100 free signup credits bonus.
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
                <p>100 one-time wallet credits on signup</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> 100 credits added on first signup</li>
                <li><span>✓</span> Non-expiring wallet credits</li>
                <li><span>✓</span> Auto-applied, no payment required</li>
                <li><span>✓</span> Available to every new account</li>
              </ul>
              <button className={styles.pricingBtn} onClick={() => navigate("/register")}>
                Claim on Signup
              </button>
            </div>

            <div className={`${styles.pricingCard} ${styles.popular}`}>
              <div className={styles.popularBadge}>Most Popular</div>
              <div className={styles.pricingHeader}>
                <h3>Candidate Pro</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.currency}>₹</span>
                  <span className={styles.amount}>499.00</span>
                  <span className={styles.period}>one-time</span>
                </div>
                <p>500 non-expiring wallet credits</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> 500 non-expiring credits</li>
                <li><span>✓</span> Practice interview deductions at fixed rates</li>
                <li><span>✓</span> Real-time wallet activity tracking</li>
                <li><span>✓</span> 100 signup bonus credits on first signup</li>
              </ul>
              <button className={`${styles.pricingBtn} ${styles.primaryPricingBtn}`} onClick={() => navigate("/register")}>
                Start and Recharge
              </button>
            </div>

            <div className={styles.pricingCard}>
              <div className={styles.pricingHeader}>
                <h3>Candidate Max</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.currency}>₹</span>
                  <span className={styles.amount}>999.00</span>
                  <span className={styles.period}>one-time</span>
                </div>
                <p>1,000 non-expiring wallet credits</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> 1,000 non-expiring credits</li>
                <li><span>✓</span> Practice interview deductions at fixed rates</li>
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
                <p>100 one-time wallet credits on signup</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> 100 credits added on first signup</li>
                <li><span>✓</span> Non-expiring wallet credits</li>
                <li><span>✓</span> Auto-applied, no payment required</li>
                <li><span>✓</span> Available to every new account</li>
              </ul>
              <button className={styles.pricingBtn} onClick={() => navigate("/recruiter-signup")}>
                Claim on Signup
              </button>
            </div>

            <div className={`${styles.pricingCard} ${styles.popular}`}>
              <div className={styles.popularBadge}>Most Popular</div>
              <div className={styles.pricingHeader}>
                <h3>Recruiter Pro</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.currency}>₹</span>
                  <span className={styles.amount}>4,999.00</span>
                  <span className={styles.period}>one-time</span>
                </div>
                <p>5,000 non-expiring wallet credits</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> 5,000 non-expiring credits</li>
                <li><span>✓</span> AI JD generation billed at fixed credits</li>
                <li><span>✓</span> Real interview deductions at fixed credits</li>
                <li><span>✓</span> 100 signup bonus credits on first signup</li>
              </ul>
              <button className={`${styles.pricingBtn} ${styles.primaryPricingBtn}`} onClick={() => navigate("/recruiter-signup")}>
                Start and Recharge
              </button>
            </div>

            <div className={styles.pricingCard}>
              <div className={styles.pricingHeader}>
                <h3>Recruiter Max</h3>
                <div className={styles.pricingPrice}>
                  <span className={styles.currency}>₹</span>
                  <span className={styles.amount}>9,999.00</span>
                  <span className={styles.period}>one-time</span>
                </div>
                <p>10,000 non-expiring wallet credits</p>
              </div>
              <ul className={styles.pricingFeatures}>
                <li><span>✓</span> 10,000 non-expiring credits</li>
                <li><span>✓</span> AI JD generation billed at fixed credits</li>
                <li><span>✓</span> Real interview deductions at fixed credits</li>
                <li><span>✓</span> Recharge anytime</li>
              </ul>
              <button className={styles.pricingBtn} onClick={() => navigate("/recruiter-signup")}>
                Start and Recharge
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section id="testimonials" className={styles.testimonialsSection}>
        <div className={styles.container}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>Testimonials</span>
            <h2 className={styles.sectionTitle}>
              What Our Users <span className={styles.gradientText}>Say</span>
            </h2>
          </div>

          <div className={styles.testimonialsGrid}>
            {testimonials.map((testimonial, index) => (
              <div key={index} className={styles.testimonialCard}>
                <div className={styles.testimonialQuote}>
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                  </svg>
                </div>
                <p className={styles.testimonialText}>{testimonial.quote}</p>
                <div className={styles.testimonialAuthor}>
                  <div className={styles.authorAvatar}>{testimonial.avatar}</div>
                  <div>
                    <h4>{testimonial.author}</h4>
                    <p>{testimonial.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className={styles.ctaSection}>
        <div className={styles.container}>
          <div className={styles.ctaContent}>
            <h2>Ready to Transform Your Hiring?</h2>
            <p>Join thousands of companies and candidates using GenHire to streamline recruitment.</p>
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
              <p>AI-powered hiring platform that helps companies find the best talent efficiently.</p>
              <div className={styles.socialLinks}>
                <a href="#" aria-label="Twitter">
                  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z" /></svg>
                </a>
                <a href="#" aria-label="LinkedIn">
                  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" /><rect x="2" y="9" width="4" height="12" /><circle cx="4" cy="4" r="2" /></svg>
                </a>
                <a href="#" aria-label="GitHub">
                  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" /></svg>
                </a>
              </div>
            </div>

            <div className={styles.footerLinks}>
              <h4>Product</h4>
              <ul>
                <li><a href="#features">Features</a></li>
                <li><a href="#pricing">Pricing</a></li>
                <li><a href="#">API</a></li>
                <li><a href="#">Integrations</a></li>
              </ul>
            </div>

            <div className={styles.footerLinks}>
              <h4>Company</h4>
              <ul>
                <li><a href="#">About</a></li>
                <li><a href="#">Blog</a></li>
                <li><a href="#">Careers</a></li>
                <li><a href="#">Contact</a></li>
              </ul>
            </div>

            <div className={styles.footerLinks}>
              <h4>Legal</h4>
              <ul>
                <li><a href="#">Privacy Policy</a></li>
                <li><a href="#">Terms of Service</a></li>
                <li><a href="#">Cookie Policy</a></li>
                <li><a href="#">GDPR</a></li>
              </ul>
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

import AuthShell from "../components/AuthShell";
import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useGoogleLogin } from "@react-oauth/google";
import styles from "./RecruiterOnboarding.module.css";
import { setToken, setUser } from "shared/utils/session";
import { authPost } from "features/auth/api/authApi";

const STRENGTH_LEVELS = [
  { label: "Too short", color: "#ef4444" },
  { label: "Weak",      color: "#f97316" },
  { label: "Fair",      color: "#eab308" },
  { label: "Strong",    color: "#22c55e" },
];

function getPasswordStrength(pwd) {
  if (!pwd || pwd.length < 8) return 0;
  const types = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^a-zA-Z0-9]/].filter(r => r.test(pwd)).length;
  if (types <= 1) return 1;
  if (types === 2 || pwd.length < 12) return 2;
  return 3;
}

function getStrengthHint(pwd) {
  if (!pwd) return "";
  if (pwd.length < 8) return "Use at least 8 characters";
  const missing = [];
  if (!/[A-Z]/.test(pwd)) missing.push("uppercase letter");
  if (!/[0-9]/.test(pwd)) missing.push("number");
  if (!/[^a-zA-Z0-9]/.test(pwd)) missing.push("symbol");
  if (missing.length) return `Add a ${missing.slice(0, 2).join(" or ")} to strengthen`;
  return "";
}

const RecruiterOnboarding = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  // Step 1: Account Info
  const [accountInfo, setAccountInfo] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: ""
  });
  
  // Step 2: Company Info
  const [companyInfo, setCompanyInfo] = useState({
    companyName: "",
    industry: "",
    companySize: "",
    website: "",
    location: ""
  });
  
  // Step 3: Additional Details
  const [additionalInfo, setAdditionalInfo] = useState({
    companyDescription: "",
    reasonForJoining: "",
    linkedinProfile: ""
  });

  // Google auth data
  const [googleUser, setGoogleUser] = useState(null);

  React.useEffect(() => {
    const credential = location.state?.googleCredential;
    const profile = location.state?.googleProfile;
    if (!credential || !profile?.email) return;

    setGoogleUser({
      name: profile.name || "",
      email: profile.email,
      token: credential,
    });
    setAccountInfo(prev => ({
      ...prev,
      name: profile.name || "",
      email: profile.email,
    }));
    setCurrentStep(2);
    navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, location.state, navigate]);

  const industries = [
    "Technology",
    "Healthcare",
    "Finance & Banking",
    "E-commerce & Retail",
    "Manufacturing",
    "Education",
    "Consulting",
    "Real Estate",
    "Logistics & Transportation",
    "Media & Entertainment",
    "Hospitality & Tourism",
    "Non-profit",
    "Government",
    "Other"
  ];

  const companySizes = [
    "1-10 employees",
    "11-50 employees",
    "51-200 employees",
    "201-500 employees",
    "501-1000 employees",
    "1000+ employees"
  ];

  const steps = [
    { number: 1, title: "Account", description: "Your credentials" },
    { number: 2, title: "Company", description: "Organization details" },
    { number: 3, title: "About", description: "Tell us more" },
    { number: 4, title: "Review", description: "Confirm & submit" }
  ];

  const validateEmailForRecruiter = async (email) => {
    const normalizedEmail = String(email || "").trim();
    if (!normalizedEmail) return false;

    try {
      const response = await authPost("/check-email-account-type", { email: normalizedEmail, userType: "recruiter" });

      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }

      const isExplicitConflict =
        response.status === 409 ||
        (data && data.available === false && data.existing_user_type && data.requested_user_type);

      if (isExplicitConflict) {
        setError(data.error || "This email is already used for another account type");
        return false;
      }

      // Do not block signup for endpoint/network/server issues.
      // Final server-side registration still enforces account-type restrictions.
      if (!response.ok) {
        return true;
      }

      return true;
    } catch {
      // Allow progress if precheck service is unavailable.
      return true;
    }
  };

  const validateStep1 = async () => {
    if (googleUser) return true; // Skip validation for Google users
    
    if (!accountInfo.name.trim()) {
      setError("Full name is required");
      return false;
    }
    if (!accountInfo.email.trim()) {
      setError("Email is required");
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(accountInfo.email)) {
      setError("Please enter a valid email address");
      return false;
    }
    if (!accountInfo.password) {
      setError("Password is required");
      return false;
    }
    if (accountInfo.password.length < 8) {
      setError("Password must be at least 8 characters");
      return false;
    }
    if (accountInfo.password !== accountInfo.confirmPassword) {
      setError("Passwords do not match");
      return false;
    }

    return validateEmailForRecruiter(accountInfo.email);
  };

  const validateStep2 = () => {
    if (!companyInfo.companyName.trim()) {
      setError("Company name is required");
      return false;
    }
    if (!companyInfo.industry) {
      setError("Please select your industry");
      return false;
    }
    if (!companyInfo.companySize) {
      setError("Please select company size");
      return false;
    }
    return true;
  };

  const validateStep3 = () => {
    if (!additionalInfo.companyDescription.trim()) {
      setError("Please provide a company description");
      return false;
    }
    if (additionalInfo.companyDescription.trim().length < 50) {
      setError("Company description should be at least 50 characters");
      return false;
    }
    return true;
  };

  const handleNext = async () => {
    setError("");
    
    if (currentStep === 1 && !(await validateStep1())) return;
    if (currentStep === 2 && !validateStep2()) return;
    if (currentStep === 3 && !validateStep3()) return;
    
    if (currentStep < 4) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
      setError("");
    }
  };

  const handleSubmit = async () => {
    setError("");
    setIsLoading(true);

    try {
      const payload = {
        name: googleUser?.name || accountInfo.name.trim(),
        email: googleUser?.email || accountInfo.email.trim(),
        password: googleUser ? undefined : accountInfo.password,
        confirmPassword: googleUser ? undefined : accountInfo.confirmPassword,
        userType: "recruiter",
        // Company info for admin verification
        companyName: companyInfo.companyName.trim(),
        companyIndustry: companyInfo.industry,
        companySize: companyInfo.companySize,
        companyWebsite: companyInfo.website.trim(),
        companyLocation: companyInfo.location.trim(),
        companyDescription: additionalInfo.companyDescription.trim(),
        reasonForJoining: additionalInfo.reasonForJoining.trim(),
        linkedinProfile: additionalInfo.linkedinProfile.trim(),
        // If Google user, include token
        googleToken: googleUser?.token
      };

      const response = await authPost(
        googleUser ? "/google-oauth" : "/register",
        googleUser ? {
          token: googleUser.token,
          userType: "recruiter",
          ...payload
        } : payload
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Registration failed");
      }

      if (data.token && data.user) {
        setToken(data.token);
        setUser({
          ...data.user,
          userType: data.user.user_type,
          isVerified: data.user.is_verified,
          permissions: data.user.permissions || [],
        });
      }

      setSuccessMessage("Your recruiter profile is complete and pending verification. You'll receive an email once approved.");
      
      // Don't auto-login, show success and redirect after delay
      setTimeout(() => {
        navigate(data.token ? "/recruiter/dashboard" : "/login");
      }, 5000);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSuccess = async (tokenResponse) => {
    setError("");
    try {
      const accessToken = tokenResponse.access_token;
      const userInfoRes = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (!userInfoRes.ok) throw new Error("Failed to fetch Google user info");
      const userData = await userInfoRes.json();

      const canUseEmail = await validateEmailForRecruiter(userData.email);
      if (!canUseEmail) return;

      setGoogleUser({
        name: userData.name,
        email: userData.email,
        token: accessToken
      });

      setAccountInfo(prev => ({
        ...prev,
        name: userData.name,
        email: userData.email
      }));

      setCurrentStep(2);
    } catch (error) {
      setError(error?.message || "Failed to process Google sign-up. Please try again.");
    }
  };

  const handleGoogleError = () => {
    setError("Google sign-up failed. Please try again.");
  };

  const googleLogin = useGoogleLogin({
    onSuccess: handleGoogleSuccess,
    onError: handleGoogleError,
  });

  return (
    <AuthShell wide title="Build your next team." accent="Start with a connection." description="Create your hiring workspace and turn applications into meaningful conversations.">
      <div className={styles.onboardingCard}>
        {/* Header */}
        <div className={styles.header}>
          <Link to="/login" className={styles.backLink}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="19" y1="12" x2="5" y2="12"></line>
              <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
            Back to Login
          </Link>
          <h1>Recruiter Registration</h1>
          <p>Complete your profile to start hiring top talent</p>
        </div>

        {/* Progress Steps */}
        <div className={styles.progressContainer}>
          {steps.map((step, index) => (
            <div 
              key={step.number} 
              className={`${styles.progressStep} ${currentStep >= step.number ? styles.active : ''} ${currentStep > step.number ? styles.completed : ''}`}
            >
              <div className={styles.stepNumber}>
                {currentStep > step.number ? (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                ) : (
                  step.number
                )}
              </div>
              <div className={styles.stepInfo}>
                <span className={styles.stepTitle}>{step.title}</span>
                <span className={styles.stepDesc}>{step.description}</span>
              </div>
              {index < steps.length - 1 && <div className={styles.stepConnector}></div>}
            </div>
          ))}
        </div>

        {/* Error/Success Messages */}
        {error && (
          <div className={styles.errorMessage}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="15" y1="9" x2="9" y2="15"></line>
              <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
            {error}
          </div>
        )}
        
        {successMessage && (
          <div className={styles.successMessage}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <div>
              <strong>Registration Successful!</strong>
              <p>{successMessage}</p>
              <p className={styles.redirectNotice}>Redirecting to login page...</p>
            </div>
          </div>
        )}

        {/* Form Content */}
        {!successMessage && (
          <div className={styles.formContent}>
            {/* Step 1: Account Information */}
            {currentStep === 1 && (
              <div className={styles.stepContent}>
                <h2>Create Your Account</h2>
                <p className={styles.stepSubtitle}>Enter your credentials or sign up with Google</p>
                
                {!googleUser && (
                  <>
                    <div className={styles.googleSection}>
                      <button
                        type="button"
                        onClick={() => googleLogin()}
                        className={styles.googleBtn}
                      >
                        <svg viewBox="0 0 24 24" width="18" height="18">
                          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
                          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                        </svg>
                        Sign up with Google
                      </button>
                    </div>
                    
                    <div className={styles.divider}>
                      <span>or continue with email</span>
                    </div>
                  </>
                )}
                
                {googleUser && (
                  <div className={styles.googleConnected}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                      <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                    <div>
                      <strong>Signed in as {googleUser.name}</strong>
                      <span>{googleUser.email}</span>
                    </div>
                    <button 
                      type="button" 
                      onClick={() => {
                        setGoogleUser(null);
                        setAccountInfo({ name: "", email: "", password: "", confirmPassword: "" });
                      }}
                      className={styles.changeButton}
                    >
                      Change
                    </button>
                  </div>
                )}

                {!googleUser && (
                  <div className={styles.formGrid}>
                    <div className={styles.inputGroup}>
                      <label>Full Name *</label>
                      <input
                        type="text"
                        value={accountInfo.name}
                        onChange={(e) => setAccountInfo({...accountInfo, name: e.target.value})}
                        placeholder="Enter your full name"
                      />
                    </div>
                    
                    <div className={styles.inputGroup}>
                      <label>Work Email *</label>
                      <input
                        type="email"
                        value={accountInfo.email}
                        onChange={(e) => setAccountInfo({...accountInfo, email: e.target.value})}
                        placeholder="you@company.com"
                      />
                    </div>
                    
                    <div className={styles.inputGroup}>
                      <label>Password *</label>
                      <div className={styles.passwordInputWrapper}>
                        <input
                          type={showPassword ? "text" : "password"}
                          value={accountInfo.password}
                          onChange={(e) => setAccountInfo({...accountInfo, password: e.target.value})}
                          placeholder="Min. 8 characters"
                        />
                        <button
                          type="button"
                          className={styles.passwordToggle}
                          onClick={() => setShowPassword(!showPassword)}
                          aria-label={showPassword ? "Hide password" : "Show password"}
                        >
                          {showPassword ? (
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M3.28 2.22a.75.75 0 00-1.06 1.06l14.5 14.5a.75.75 0 101.06-1.06l-1.745-1.745a10.029 10.029 0 003.3-4.38 1.651 1.651 0 000-1.185A10.004 10.004 0 009.999 3a9.956 9.956 0 00-4.744 1.194L3.28 2.22zM7.752 6.69l1.092 1.092a2.5 2.5 0 013.374 3.373l1.091 1.092a4 4 0 00-5.557-5.557z" clipRule="evenodd" />
                              <path d="M10.748 13.93l2.523 2.523a9.987 9.987 0 01-3.27.547c-4.258 0-7.894-2.66-9.337-6.41a1.651 1.651 0 010-1.186A10.007 10.007 0 012.839 6.02L6.07 9.252a4 4 0 004.678 4.678z" />
                            </svg>
                          ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                              <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" />
                              <path fillRule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                            </svg>
                          )}
                        </button>
                      </div>
                      {accountInfo.password && (() => {
                        const level = getPasswordStrength(accountInfo.password);
                        const { label, color } = STRENGTH_LEVELS[level];
                        const hint = getStrengthHint(accountInfo.password);
                        return (
                          <div className={styles.strengthMeter} role="status" aria-live="polite">
                            <div className={styles.strengthBar}>
                              {STRENGTH_LEVELS.map((_, i) => (
                                <div
                                  key={i}
                                  className={styles.strengthSegment}
                                  style={{ background: i <= level ? color : undefined }}
                                />
                              ))}
                            </div>
                            <div className={styles.strengthRow}>
                              {hint && <span className={styles.strengthHint}>{hint}</span>}
                              <span className={styles.strengthLabel} style={{ color }}>{label}</span>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                    
                    <div className={styles.inputGroup}>
                      <label>Confirm Password *</label>
                      <div className={styles.passwordInputWrapper}>
                        <input
                          type={showConfirmPassword ? "text" : "password"}
                          value={accountInfo.confirmPassword}
                          onChange={(e) => setAccountInfo({...accountInfo, confirmPassword: e.target.value})}
                          placeholder="Re-enter password"
                        />
                        <button
                          type="button"
                          className={styles.passwordToggle}
                          onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                          aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                        >
                          {showConfirmPassword ? (
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M3.28 2.22a.75.75 0 00-1.06 1.06l14.5 14.5a.75.75 0 101.06-1.06l-1.745-1.745a10.029 10.029 0 003.3-4.38 1.651 1.651 0 000-1.185A10.004 10.004 0 009.999 3a9.956 9.956 0 00-4.744 1.194L3.28 2.22zM7.752 6.69l1.092 1.092a2.5 2.5 0 013.374 3.373l1.091 1.092a4 4 0 00-5.557-5.557z" clipRule="evenodd" />
                              <path d="M10.748 13.93l2.523 2.523a9.987 9.987 0 01-3.27.547c-4.258 0-7.894-2.66-9.337-6.41a1.651 1.651 0 010-1.186A10.007 10.007 0 012.839 6.02L6.07 9.252a4 4 0 004.678 4.678z" />
                            </svg>
                          ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                              <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" />
                              <path fillRule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Step 2: Company Information */}
            {currentStep === 2 && (
              <div className={styles.stepContent}>
                <h2>Company Information</h2>
                <p className={styles.stepSubtitle}>Tell us about your organization</p>
                
                <div className={styles.formGrid}>
                  <div className={styles.inputGroup + ' ' + styles.fullWidth}>
                    <label>Company Name *</label>
                    <input
                      type="text"
                      value={companyInfo.companyName}
                      onChange={(e) => setCompanyInfo({...companyInfo, companyName: e.target.value})}
                      placeholder="Enter company name"
                    />
                  </div>
                  
                  <div className={styles.inputGroup}>
                    <label>Industry *</label>
                    <select
                      value={companyInfo.industry}
                      onChange={(e) => setCompanyInfo({...companyInfo, industry: e.target.value})}
                    >
                      <option value="">Select industry</option>
                      {industries.map(ind => (
                        <option key={ind} value={ind}>{ind}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div className={styles.inputGroup}>
                    <label>Company Size *</label>
                    <select
                      value={companyInfo.companySize}
                      onChange={(e) => setCompanyInfo({...companyInfo, companySize: e.target.value})}
                    >
                      <option value="">Select size</option>
                      {companySizes.map(size => (
                        <option key={size} value={size}>{size}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div className={styles.inputGroup}>
                    <label>Company Website</label>
                    <input
                      type="url"
                      value={companyInfo.website}
                      onChange={(e) => setCompanyInfo({...companyInfo, website: e.target.value})}
                      placeholder="https://yourcompany.com"
                    />
                  </div>
                  
                  <div className={styles.inputGroup}>
                    <label>Headquarters Location</label>
                    <input
                      type="text"
                      value={companyInfo.location}
                      onChange={(e) => setCompanyInfo({...companyInfo, location: e.target.value})}
                      placeholder="City, Country"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: Additional Details */}
            {currentStep === 3 && (
              <div className={styles.stepContent}>
                <h2>Additional Details</h2>
                <p className={styles.stepSubtitle}>Help us understand your hiring needs</p>
                
                <div className={styles.formGrid}>
                  <div className={styles.inputGroup + ' ' + styles.fullWidth}>
                    <label>Company Description *</label>
                    <textarea
                      value={additionalInfo.companyDescription}
                      onChange={(e) => setAdditionalInfo({...additionalInfo, companyDescription: e.target.value})}
                      placeholder="Describe what your company does, your mission, and culture..."
                      rows={4}
                    />
                    <span className={styles.charCount}>
                      {additionalInfo.companyDescription.length}/500 characters
                    </span>
                  </div>
                  
                  <div className={styles.inputGroup + ' ' + styles.fullWidth}>
                    <label>Why are you joining GenHire?</label>
                    <textarea
                      value={additionalInfo.reasonForJoining}
                      onChange={(e) => setAdditionalInfo({...additionalInfo, reasonForJoining: e.target.value})}
                      placeholder="What are your hiring goals? What positions are you looking to fill?"
                      rows={3}
                    />
                  </div>
                  
                  <div className={styles.inputGroup + ' ' + styles.fullWidth}>
                    <label>LinkedIn Company Page</label>
                    <input
                      type="url"
                      value={additionalInfo.linkedinProfile}
                      onChange={(e) => setAdditionalInfo({...additionalInfo, linkedinProfile: e.target.value})}
                      placeholder="https://linkedin.com/company/yourcompany"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Step 4: Review */}
            {currentStep === 4 && (
              <div className={styles.stepContent}>
                <h2>Review Your Application</h2>
                <p className={styles.stepSubtitle}>Please verify all information is correct</p>
                
                <div className={styles.reviewSections}>
                  <div className={styles.reviewSection}>
                    <h3>
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                      </svg>
                      Account Information
                    </h3>
                    <div className={styles.reviewGrid}>
                      <div><span>Name:</span><strong>{googleUser?.name || accountInfo.name}</strong></div>
                      <div><span>Email:</span><strong>{googleUser?.email || accountInfo.email}</strong></div>
                      <div><span>Auth Method:</span><strong>{googleUser ? 'Google Account' : 'Email & Password'}</strong></div>
                    </div>
                    <button type="button" onClick={() => setCurrentStep(1)} className={styles.editButton}>Edit</button>
                  </div>
                  
                  <div className={styles.reviewSection}>
                    <h3>
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
                      </svg>
                      Company Information
                    </h3>
                    <div className={styles.reviewGrid}>
                      <div><span>Company:</span><strong>{companyInfo.companyName}</strong></div>
                      <div><span>Industry:</span><strong>{companyInfo.industry}</strong></div>
                      <div><span>Size:</span><strong>{companyInfo.companySize}</strong></div>
                      {companyInfo.website && <div><span>Website:</span><strong>{companyInfo.website}</strong></div>}
                      {companyInfo.location && <div><span>Location:</span><strong>{companyInfo.location}</strong></div>}
                    </div>
                    <button type="button" onClick={() => setCurrentStep(2)} className={styles.editButton}>Edit</button>
                  </div>
                  
                  <div className={styles.reviewSection}>
                    <h3>
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                      </svg>
                      Company Description
                    </h3>
                    <p className={styles.reviewDescription}>{additionalInfo.companyDescription}</p>
                    <button type="button" onClick={() => setCurrentStep(3)} className={styles.editButton}>Edit</button>
                  </div>
                </div>
                
                <div className={styles.verificationNotice}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                  </svg>
                  <div>
                    <strong>Account Verification Required</strong>
                    <p>After submission, our team will review your application. This usually takes 1-2 business days. You'll receive an email notification once your account is approved.</p>
                  </div>
                </div>
              </div>
            )}

            {/* Navigation Buttons */}
            <div className={styles.navigation}>
              {currentStep > 1 && (
                <button 
                  type="button" 
                  onClick={handleBack} 
                  className={styles.backButton}
                  disabled={isLoading}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="19" y1="12" x2="5" y2="12"></line>
                    <polyline points="12 19 5 12 12 5"></polyline>
                  </svg>
                  Back
                </button>
              )}
              
              {currentStep < 4 ? (
                <button 
                  type="button" 
                  onClick={handleNext} 
                  className={styles.nextButton}
                >
                  Continue
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                    <polyline points="12 5 19 12 12 19"></polyline>
                  </svg>
                </button>
              ) : (
                <button 
                  type="button" 
                  onClick={handleSubmit} 
                  className={styles.submitButton}
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <>
                      <span className={styles.spinner}></span>
                      Submitting...
                    </>
                  ) : (
                    <>
                      Submit Application
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className={styles.footer}>
          <p>Looking to find a job instead? <Link to="/register">Register as Candidate</Link></p>
        </div>
      </div>
    </AuthShell>
  );
};

export default RecruiterOnboarding;

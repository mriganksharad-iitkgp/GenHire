import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import styles from "./RecruiterOnboarding.module.css";

const RecruiterOnboarding = () => {
  const navigate = useNavigate();
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

  const validateStep1 = () => {
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
    return true;
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

  const handleNext = () => {
    setError("");
    
    if (currentStep === 1 && !validateStep1()) return;
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

      const endpoint = googleUser 
        ? `${process.env.REACT_APP_API_BASE}/google-oauth`
        : `${process.env.REACT_APP_API_BASE}/register`;

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(googleUser ? {
          token: googleUser.token,
          userType: "recruiter",
          ...payload
        } : payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Registration failed");
      }

      setSuccessMessage("Your recruiter account has been created and is pending verification. You'll receive an email once approved.");
      
      // Don't auto-login, show success and redirect after delay
      setTimeout(() => {
        navigate("/login");
      }, 5000);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    setError("");
    
    // Decode the JWT to get user info
    try {
      const token = credentialResponse.credential;
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
      }).join(''));
      
      const userData = JSON.parse(jsonPayload);
      
      setGoogleUser({
        name: userData.name,
        email: userData.email,
        token: token
      });
      
      // Pre-fill account info
      setAccountInfo(prev => ({
        ...prev,
        name: userData.name,
        email: userData.email
      }));
      
      // Move to step 2 since account info is handled by Google
      setCurrentStep(2);
    } catch (error) {
      setError("Failed to process Google sign-up. Please try again.");
    }
  };

  const handleGoogleError = () => {
    setError("Google sign-up failed. Please try again.");
  };

  return (
    <div className={styles.container}>
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
                      <GoogleLogin
                        onSuccess={handleGoogleSuccess}
                        onError={handleGoogleError}
                        theme="outline"
                        size="large"
                        text="signup_with"
                        width="100%"
                      />
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
                    <label>Why are you joining SmartHire?</label>
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
    </div>
  );
};

export default RecruiterOnboarding;

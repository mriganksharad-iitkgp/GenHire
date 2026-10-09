import AuthStory from "../components/AuthStory";
import AuthBrand from "../components/AuthBrand";
import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useGoogleLogin } from "@react-oauth/google";
import { Eye, EyeOff, ArrowRight, BriefcaseBusiness, ShieldCheck, UserRound } from "lucide-react";
import styles from "./LoginExperience.module.css";
import { useCandidateData } from "features/candidate/context/CandidateDataContext";
import { setToken, setUser } from "shared/utils/session";
import { authPost } from "features/auth/api/authApi";
import { retryAfterSeconds } from "shared/api/retry";

const ROLES = [
  { value: "candidate", label: "Candidate", Icon: UserRound },
  { value: "recruiter", label: "Recruiter", Icon: BriefcaseBusiness },
  { value: "admin", label: "Admin", Icon: ShieldCheck },
];

const Login = () => {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [userType, setUserType] = useState("candidate");
  const [retryUntil, setRetryUntil] = useState(0);
  const [now, setNow] = useState(Date.now());
  const pending = useRef(null);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { clearAllCaches } = useCandidateData();
  const retrySeconds = Math.max(0, Math.ceil((retryUntil - now) / 1000));
  const disabled = isLoading || retrySeconds > 0;

  useEffect(() => {
    if (!retryUntil) return undefined;
    const timer = setInterval(() => {
      const current = Date.now();
      setNow(current);
      if (current >= retryUntil) setRetryUntil(0);
    }, 1000);
    return () => clearInterval(timer);
  }, [retryUntil]);

  const begin = (kind) => {
    if (pending.current || Date.now() < retryUntil) return false;
    pending.current = { kind, role: userType };
    setIsLoading(true);
    setError("");
    return true;
  };

  const finish = () => {
    pending.current = null;
    setIsLoading(false);
  };

  const checkResponse = async (response) => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 429 || response.status === 503) {
        const seconds = retryAfterSeconds(response, data) || 3;
        setNow(Date.now());
        setRetryUntil(Date.now() + seconds * 1000);
      }
      throw new Error(data.email_verification_required
        ? `${data.error} Please check your email for the verification link.`
        : data.error || data.message || "Unable to sign in. Please try again.");
    }
    return data;
  };

  const completeLogin = (data) => {
    if (!data.token || !data.user) throw new Error("Sign-in response is incomplete. Please try again.");
    const role = data.user.user_type;
    if (!["candidate", "student", "recruiter", "admin"].includes(role)) {
      throw new Error("This account role is unavailable. Please contact support.");
    }
    clearAllCaches();
    setToken(data.token);
    setUser({ ...data.user, userType: role === "student" ? "candidate" : role,
      isVerified: data.user.is_verified, permissions: data.user.permissions || [] });
    navigate(role === "admin" ? "/admin" : role === "recruiter" ? "/recruiter/dashboard" : "/dashboard", { replace: true });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!begin("password")) return;
    const role = pending.current.role;
    try {
      completeLogin(await checkResponse(await authPost("/login", { identifier: identifier.trim(), password, userType: role })));
    } catch (err) {
      setError(err.message);
    } finally {
      finish();
    }
  };

  const handleGoogleSuccess = async ({ access_token: credential }) => {
    if (pending.current?.kind !== "google") return;
    const role = pending.current.role;
    try {
      const data = await checkResponse(await authPost("/google-oauth", { token: credential, userType: role }));
      if (data.onboarding_required) {
        navigate("/recruiter-signup", { state: { googleCredential: credential, googleProfile: data.user } });
      } else {
        completeLogin(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      finish();
    }
  };

  const googleLogin = useGoogleLogin({
    onSuccess: handleGoogleSuccess,
    onError: () => { setError("Google sign-in failed. Please try again."); finish(); },
    onNonOAuthError: () => { setError("Google sign-in was closed or blocked. You can try again or use your password."); finish(); },
  });

  return (
    <main className={styles.layout}>
      <AuthStory
        title={userType === "recruiter" ? "Find the people." : userType === "admin" ? "Keep things moving." : "Your next chapter."}
        accent={userType === "recruiter" ? "Build the future." : userType === "admin" ? "With confidence." : "Starts with you."}
        description={userType === "recruiter" ? "Bring applications, interviews and candidate insights into one thoughtful hiring journey." : userType === "admin" ? "One workspace to support your people and keep your hiring operations running smoothly." : "Explore opportunities, practice your interview and bring your experience to the conversation."}
      />

      <section className={styles.formPanel} aria-labelledby="login-title">
        <div className={styles.formCard}>
          <AuthBrand className={styles.mobileBrand} />
          <span className={styles.formEyebrow}>YOUR WORKSPACE AWAITS</span>
          <h2 id="login-title">Welcome back.</h2>
          <p className={styles.formIntro}>Sign in to pick up where you left off.</p>
          {searchParams.get("expired") === "1" && <p className={styles.notice} role="status">Your session has expired. Please sign in again.</p>}

          <div className={styles.roleSelector} role="group" aria-label="Account role">
            {ROLES.map(({ value, label, Icon }) => <button type="button" key={value} aria-pressed={userType === value}
              disabled={isLoading} className={userType === value ? styles.selectedRole : ""}
              onClick={() => { setUserType(value); setError(""); }}><Icon size={16} aria-hidden="true" />{label}</button>)}
          </div>

          <form onSubmit={handleSubmit} className={styles.form} aria-busy={isLoading}>
            {error && <div className={styles.error} role="alert">{error}</div>}
            <div className={styles.field}>
              <label htmlFor="identifier">{userType === "candidate" ? "Email or Invite ID" : "Email address"}</label>
              <input id="identifier" type={userType === "candidate" ? "text" : "email"} autoComplete="username"
                autoCapitalize="none" spellCheck={false} required maxLength={320} disabled={isLoading}
                value={identifier} onChange={(event) => setIdentifier(event.target.value)}
                placeholder={userType === "candidate" ? "you@example.com or your Invite ID" : "you@company.com"} />
            </div>
            <div className={styles.field}>
              <div className={styles.labelRow}><label htmlFor="password">Password</label><Link to="/forgot-password">Forgot password?</Link></div>
              <div className={styles.passwordField}>
                <input id="password" type={showPassword ? "text" : "password"} autoComplete="current-password"
                  required disabled={isLoading} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" />
                <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword}
                  onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeOff size={19} /> : <Eye size={19} />}</button>
              </div>
            </div>
            <button type="submit" className={styles.submit} disabled={disabled}>
              {isLoading ? "Signing you in..." : retrySeconds ? `Try again in ${retrySeconds}s` : "Sign in"}{!disabled && <ArrowRight size={18} aria-hidden="true" />}
            </button>
          </form>

          {userType !== "admin" ? <>
            <div className={styles.divider}><span>or continue with</span></div>
            <button type="button" disabled={disabled} className={styles.google}
              onClick={() => { if (begin("google")) { try { googleLogin(); } catch (_) { finish(); setError("Unable to open Google sign-in. Please try again."); } } }}>
              <span className={styles.googleMark} aria-hidden="true">G</span> Google
            </button>
            <p className={styles.register}>New to GenHire? <Link to={userType === "recruiter" ? "/recruiter-signup" : "/register"}>Create an account <ArrowRight size={14} aria-hidden="true" /></Link></p>
          </> : <p className={styles.notice}>Admin access is provided by your system administrator.</p>}
          {userType === "candidate" && <p className={styles.inviteHint}>Invited by a recruiter? Use the Invite ID and password from your invitation.</p>}
        </div>
        <p className={styles.formFooter}>Your experience. Your next opportunity.</p>
      </section>
    </main>
  );
};
export default Login;

import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import styles from "./Login.module.css";

const Login = () => {
	const [identifier, setIdentifier] = useState("");
	const [password, setPassword] = useState("");
	const [showPassword, setShowPassword] = useState(false);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState("");
	const [userType, setUserType] = useState("candidate"); // 'candidate', 'recruiter', or 'admin'
	const navigate = useNavigate();

	const handleSubmit = async (e) => {
		e.preventDefault();
		setIsLoading(true);
		setError("");

		try {
			const response = await fetch(`${process.env.REACT_APP_API_BASE}/login`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					identifier,
					password,
					userType
				}),
			});

			const data = await response.json();

			console.log('Login response:', data); // Debug log

			if (!response.ok) {
				// Check if email verification is required
				if (data.email_verification_required) {
					setError(data.error + " Please check your email for the verification link.");
				} else {
					throw new Error(data.error || "Login failed");
				}
				return;
			}

			// Store token and user data with user type, verification status, and permissions
			localStorage.setItem(process.env.REACT_APP_TOKEN_KEY || "companyxyz-token", data.token);
			localStorage.setItem(process.env.REACT_APP_USER_KEY || "companyxyz-user", JSON.stringify({
				...data.user,
				userType: data.user.user_type || userType,
				isVerified: data.user.is_verified,
				permissions: data.user.permissions || []
			}));

			console.log('Token stored:', data.token); // Debug log
			console.log('User data stored:', data.user); // Debug log

			// Navigate based on user type
			if (data.user.user_type === "admin" || userType === "admin") {
				console.log('Navigating to admin dashboard'); // Debug log
				navigate("/admin");
			} else if (data.user.user_type === "recruiter" || userType === "recruiter") {
				console.log('Navigating to recruiter dashboard'); // Debug log
				navigate("/recruiter-dashboard");
			} else {
				console.log('Navigating to candidate dashboard'); // Debug log
				navigate("/dashboard");
			}
		} catch (error) {
			setError(error.message);
		} finally {
			setIsLoading(false);
		}
	};

	const handleGoogleSuccess = async (credentialResponse) => {
		setIsLoading(true);
		setError("");

		try {
			const response = await fetch(`${process.env.REACT_APP_API_BASE}/google-oauth`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					token: credentialResponse.credential,
					userType: userType,
				}),
			});

			const data = await response.json();

			if (!response.ok) {
				throw new Error(data.error || "Google login failed");
			}

			// Store token and user data with verification status and permissions
			localStorage.setItem(process.env.REACT_APP_TOKEN_KEY || "companyxyz-token", data.token);
			localStorage.setItem(process.env.REACT_APP_USER_KEY || "companyxyz-user", JSON.stringify({
				...data.user,
				userType: data.user.user_type,
				isVerified: data.user.is_verified,
				permissions: data.user.permissions || []
			}));

			// Navigate based on user type
			if (data.user.user_type === "admin") {
				navigate("/admin");
			} else if (data.user.user_type === "recruiter") {
				navigate("/recruiter-dashboard");
			} else {
				navigate("/dashboard");
			}
		} catch (error) {
			setError(error.message);
		} finally {
			setIsLoading(false);
		}
	};

	const handleGoogleError = () => {
		setError("Google login failed. Please try again.");
	};

	// Get button text based on user type
	const getLoginButtonText = () => {
		if (isLoading) return "Logging in...";
		switch (userType) {
			case "admin": return "Log In as Admin";
			case "recruiter": return "Log In as Recruiter";
			default: return "Log In as Candidate";
		}
	};

	return (
		<div className={styles.loginContainer}>
			<div className={styles.loginCard}>
				<div className={styles.logoSection}>
					<div className={styles.logoIcon}>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
							<path d="M20 7h-9"></path>
							<path d="M14 17H5"></path>
							<circle cx="17" cy="17" r="3"></circle>
							<circle cx="7" cy="7" r="3"></circle>
						</svg>
					</div>
					<h1>GenHire</h1>
					<p>
						Welcome! Please select your role and log in to access your dashboard.
					</p>
				</div>

				{/* User Type Selection Tabs */}
				<div className={styles.userTypeTabs}>
					<button
						type="button"
						className={`${styles.tabButton} ${userType === "candidate" ? styles.activeTab : ""}`}
						onClick={() => {
							setUserType("candidate");
							setError("");
						}}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style={{ width: "16px", height: "16px" }}>
							<path d="M10 8a3 3 0 100-6 3 3 0 000 6zM3.465 14.493a1.23 1.23 0 00.41 1.412A9.957 9.957 0 0010 18c2.31 0 4.438-.784 6.131-2.1.43-.333.604-.903.408-1.41a7.002 7.002 0 00-13.074.003z" />
						</svg>
						Candidate
					</button>
					<button
						type="button"
						className={`${styles.tabButton} ${userType === "recruiter" ? styles.activeTab : ""}`}
						onClick={() => {
							setUserType("recruiter");
							setError("");
						}}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style={{ width: "16px", height: "16px" }}>
							<path fillRule="evenodd" d="M6 3.75A2.75 2.75 0 018.75 1h2.5A2.75 2.75 0 0114 3.75v.443c.572.055 1.14.122 1.706.2C17.053 4.582 18 5.75 18 7.07v3.469c0 1.126-.694 2.191-1.83 2.54-1.952.599-4.024.921-6.17.921s-4.219-.322-6.17-.921C2.694 12.73 2 11.665 2 10.539V7.07c0-1.321.947-2.489 2.294-2.676A41.047 41.047 0 016 4.193V3.75zm6.5 0v.325a41.622 41.622 0 00-5 0V3.75c0-.69.56-1.25 1.25-1.25h2.5c.69 0 1.25.56 1.25 1.25zM10 10a1 1 0 00-1 1v.01a1 1 0 001 1h.01a1 1 0 001-1V11a1 1 0 00-1-1H10z" clipRule="evenodd" />
							<path d="M3 15.055v-.684c.126.053.255.1.39.142 2.092.642 4.313.987 6.61.987 2.297 0 4.518-.345 6.61-.987.135-.041.264-.089.39-.142v.684c0 1.347-.985 2.53-2.363 2.686a41.454 41.454 0 01-9.274 0C3.985 17.585 3 16.402 3 15.055z" />
						</svg>
						Recruiter
					</button>
					<button
						type="button"
						className={`${styles.tabButton} ${userType === "admin" ? styles.activeTab : ""}`}
						onClick={() => {
							setUserType("admin");
							setError("");
						}}
					>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" style={{ width: "16px", height: "16px" }}>
							<path fillRule="evenodd" d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z" clipRule="evenodd" />
						</svg>
						Admin
					</button>
				</div>

				<form className={styles.loginForm} onSubmit={handleSubmit}>
					{error && (
						<div className={styles.errorMessage}>{error}</div>
					)}

					<div className={styles.inputGroup}>
						<label htmlFor="identifier">{userType === "candidate" ? "Email or Invite ID" : "Email"}</label>
						<input
							type="text"
							id="identifier"
							value={identifier}
							onChange={(e) => setIdentifier(e.target.value)}
							placeholder={
								userType === "candidate"
									? "Enter your email or Invite ID"
									: `Enter your ${userType} email`
							}
							autoComplete="username"
							required
						/>
					</div>

					<div className={styles.inputGroup}>
						<label htmlFor="password">Password</label>
					<div className={styles.passwordInputWrapper}>
						<input
							type={showPassword ? "text" : "password"}
							id="password"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							placeholder="Enter your password"
							required
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

				<div className={styles.forgotPassword}>
					<Link to="/forgot-password">Forgot password?</Link>
				</div>

				<button
					type="submit"
					className={styles.loginButton}
					disabled={isLoading}
				>
					{getLoginButtonText()}
				</button>
			</form>

				{/* Only show Google OAuth for candidates and recruiters */}
				{userType !== "admin" && (
					<div className={styles.oauthSection}>
						<div className={styles.divider}>
							<span>or continue with</span>
						</div>
						<div className={styles.googleButtonWrapper}>
							<GoogleLogin
								onSuccess={handleGoogleSuccess}
								onError={handleGoogleError}
								theme="outline"
								size="large"
								text="continue_with"
								width="100%"
							/>
						</div>
					</div>
				)}

				{/* Show note for admin login */}
				{userType === "admin" && (
					<div className={styles.adminNotice}>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
							<path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clipRule="evenodd" />
						</svg>
						<span>Admin accounts are created by system administrators.</span>
					</div>
				)}

				{/* Only show register link for non-admin */}
				{userType !== "admin" && (
					<div className={styles.registerSection}>
						<p>
							New to GenHire?{" "}
							<Link to="/register">Create an account</Link>
						</p>
					</div>
				)}
			</div>
		</div>
	);
};

export default Login;

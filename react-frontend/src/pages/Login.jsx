import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import styles from "./Login.module.css";

const Login = () => {
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState("");
	const [userType, setUserType] = useState("candidate"); // 'candidate' or 'recruiter'
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
					email, 
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

			// Store token and user data with user type
			localStorage.setItem(process.env.REACT_APP_TOKEN_KEY, data.token);
			localStorage.setItem(process.env.REACT_APP_USER_KEY, JSON.stringify({
				...data.user,
				userType: userType
			}));

			console.log('Token stored:', data.token); // Debug log
			console.log('User data stored:', data.user); // Debug log

			// Navigate based on user type
			if (userType === "recruiter") {
				console.log('Navigating to recruiter dashboard'); // Debug log
				navigate("/recruiter-dashboard");
			} else {
				console.log('Navigating to candidate dashboard'); // Debug log
				navigate("/");
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

			// Store token and user data
			localStorage.setItem(process.env.REACT_APP_TOKEN_KEY, data.token);
			localStorage.setItem(process.env.REACT_APP_USER_KEY, JSON.stringify({
				...data.user,
				userType: data.user.user_type
			}));

			// Navigate based on user type
			if (data.user.user_type === "recruiter") {
				navigate("/recruiter-dashboard");
			} else {
				navigate("/");
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

	return (
		<div className={styles.loginContainer}>
			<div className={styles.loginCard}>
				<div className={styles.logoSection}>
					<h1>CompanyXYZ Portal</h1>
					<p>
						Welcome! Please select your role and log in to access your dashboard.
					</p>
				</div>

				{/* User Type Selection Tabs */}
				<div className={styles.userTypeTabs}>
					<button
						type="button"
						className={`${styles.tabButton} ${userType === "candidate" ? styles.activeTab : ""}`}
						onClick={() => setUserType("candidate")}
					>
						<i className="fa fa-user"></i>
						Candidate
					</button>
					<button
						type="button"
						className={`${styles.tabButton} ${userType === "recruiter" ? styles.activeTab : ""}`}
						onClick={() => setUserType("recruiter")}
					>
						<i className="fa fa-briefcase"></i>
						Recruiter
					</button>
				</div>

				<form className={styles.loginForm} onSubmit={handleSubmit}>
					{error && (
						<div className={styles.errorMessage}>{error}</div>
					)}

					<div className={styles.inputGroup}>
						<label htmlFor="email">Email</label>
						<input
							type="email"
							id="email"
							value={email}
							onChange={(e) => setEmail(e.target.value)}
							placeholder={`Enter your ${userType} email`}
							required
						/>
					</div>

					<div className={styles.inputGroup}>
						<label htmlFor="password">Password</label>
						<input
							type="password"
							id="password"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							placeholder="Enter your password"
							required
						/>
					</div>

					<div className={styles.forgotPassword}>
						<Link to="/forgot-password">Forgot password?</Link>
					</div>

					<button
						type="submit"
						className={styles.loginButton}
						disabled={isLoading}
					>
						{isLoading ? "Logging in..." : `Log In as ${userType === "candidate" ? "Candidate" : "Recruiter"}`}
					</button>
				</form>

				<div style={{ margin: "1.5rem 0", textAlign: "center", color: "#666" }}>
					<div style={{ display: "flex", alignItems: "center", margin: "1rem 0" }}>
						<div style={{ flex: 1, height: "1px", backgroundColor: "#ddd" }}></div>
						<span style={{ padding: "0 1rem", fontSize: "0.9rem" }}>OR</span>
						<div style={{ flex: 1, height: "1px", backgroundColor: "#ddd" }}></div>
					</div>

					<div style={{ display: "flex", justifyContent: "center" }}>
						<GoogleLogin
							onSuccess={handleGoogleSuccess}
							onError={handleGoogleError}
							theme="outline"
							size="large"
							text="continue_with"
							width="300"
						/>
					</div>
				</div>

				<div className={styles.registerSection}>
					<p>
						New to CompanyXYZ?{" "}
						<a href="/register">Create an account</a>
					</p>
				</div>
			</div>
		</div>
	);
};

export default Login;

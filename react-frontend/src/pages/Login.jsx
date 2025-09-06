import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
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

			if (!response.ok) {
				throw new Error(data.error || "Login failed");
			}

			// Store token and user data with user type
			localStorage.setItem(process.env.REACT_APP_TOKEN_KEY, data.token);
			localStorage.setItem(process.env.REACT_APP_USER_KEY, JSON.stringify({
				...data.user,
				userType: userType
			}));

			// Navigate based on user type
			if (userType === "recruiter") {
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
						<a href="#reset">Forgot password?</a>
					</div>

					<button
						type="submit"
						className={styles.loginButton}
						disabled={isLoading}
					>
						{isLoading ? "Logging in..." : `Log In as ${userType === "candidate" ? "Candidate" : "Recruiter"}`}
					</button>
				</form>

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

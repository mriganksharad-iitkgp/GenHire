import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "./Login.module.css";

const Login = () => {
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState("");
	const navigate = useNavigate();

	const handleSubmit = async (e) => {
		e.preventDefault();
		setIsLoading(true);
		setError("");

		// Simulate API call for authentication
		try {
			// Replace with actual authentication logic
			setTimeout(() => {
				if (email && password) {
					// Successful login logic
					localStorage.setItem("candidateLoggedIn", "true");
					console.log("Logged in");
					navigate("/");
				} else {
					setError("Invalid credentials. Please try again.");
				}
				setIsLoading(false);
			}, 1000);
		} catch (error) {
			setError("An error occurred. Please try again.");
			setIsLoading(false);
		}
	};

	return (
		<div className={styles.loginContainer}>
			<div className={styles.loginCard}>
				<div className={styles.logoSection}>
					<h1>Candidate Portal</h1>
					<p>Welcome back! Please log in to continue.</p>
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
							placeholder="Enter your email"
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
						{isLoading ? "Logging in..." : "Log In"}
					</button>
				</form>

				<div className={styles.registerSection}>
					<p>
						Don't have an account?{" "}
						<a href="#register">Contact your recruiter</a>
					</p>
				</div>
			</div>
		</div>
	);
};

export default Login;

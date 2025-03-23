import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "./Register.module.css";

const Register = () => {
	const navigate = useNavigate();
	const [formData, setFormData] = useState({
		name: "",
		email: "",
		password: "",
		confirmPassword: "",
	});
	const [errors, setErrors] = useState({});
	const [isSubmitting, setIsSubmitting] = useState(false);

	const handleChange = (e) => {
		const { name, value } = e.target;
		setFormData({
			...formData,
			[name]: value,
		});

		// Clear error when field is edited
		if (errors[name]) {
			setErrors({
				...errors,
				[name]: "",
			});
		}
	};

	const validateForm = () => {
		const newErrors = {};

		// Name validation
		if (!formData.name.trim()) {
			newErrors.name = "Name is required";
		}

		// Email validation
		if (!formData.email.trim()) {
			newErrors.email = "Email is required";
		} else if (!/\S+@\S+\.\S+/.test(formData.email)) {
			newErrors.email = "Email address is invalid";
		}

		// Password validation
		if (!formData.password) {
			newErrors.password = "Password is required";
		} else if (formData.password.length < 6) {
			newErrors.password = "Password must be at least 6 characters";
		}

		// Confirm password validation
		if (!formData.confirmPassword) {
			newErrors.confirmPassword = "Please confirm your password";
		} else if (formData.password !== formData.confirmPassword) {
			newErrors.confirmPassword = "Passwords do not match";
		}

		setErrors(newErrors);
		return Object.keys(newErrors).length === 0;
	};

	const handleSubmit = (e) => {
		e.preventDefault();

		if (validateForm()) {
			setIsSubmitting(true);

			// Simulate API call with setTimeout
			setTimeout(() => {
				// Store user data (in a real app, this would be handled by backend)
				localStorage.setItem("candidateName", formData.name);
				localStorage.setItem("candidateEmail", formData.email);
				localStorage.setItem("candidateLoggedIn", "true");

				setIsSubmitting(false);
				navigate("/");
			}, 1500);
		}
	};

	return (
		<div className={styles.registerContainer}>
			<div className={styles.registerCard}>
				<div className={styles.logoSection}>
					<h1>JobPortal</h1>
					<p>Create your account to get started</p>
				</div>

				<form className={styles.registerForm} onSubmit={handleSubmit}>
					<div className={styles.formGroup}>
						<label htmlFor="name">Full Name</label>
						<input
							type="text"
							id="name"
							name="name"
							value={formData.name}
							onChange={handleChange}
							className={errors.name ? styles.errorInput : ""}
						/>
						{errors.name && (
							<span className={styles.errorMessage}>
								{errors.name}
							</span>
						)}
					</div>

					<div className={styles.formGroup}>
						<label htmlFor="email">Email Address</label>
						<input
							type="email"
							id="email"
							name="email"
							value={formData.email}
							onChange={handleChange}
							className={errors.email ? styles.errorInput : ""}
						/>
						{errors.email && (
							<span className={styles.errorMessage}>
								{errors.email}
							</span>
						)}
					</div>

					<div className={styles.formGroup}>
						<label htmlFor="password">Password</label>
						<input
							type="password"
							id="password"
							name="password"
							value={formData.password}
							onChange={handleChange}
							className={errors.password ? styles.errorInput : ""}
						/>
						{errors.password && (
							<span className={styles.errorMessage}>
								{errors.password}
							</span>
						)}
					</div>

					<div className={styles.formGroup}>
						<label htmlFor="confirmPassword">
							Confirm Password
						</label>
						<input
							type="password"
							id="confirmPassword"
							name="confirmPassword"
							value={formData.confirmPassword}
							onChange={handleChange}
							className={
								errors.confirmPassword ? styles.errorInput : ""
							}
						/>
						{errors.confirmPassword && (
							<span className={styles.errorMessage}>
								{errors.confirmPassword}
							</span>
						)}
					</div>

					<button
						type="submit"
						className={styles.registerButton}
						disabled={isSubmitting}
					>
						{isSubmitting ? "Creating Account..." : "Register"}
					</button>
				</form>

				<div className={styles.loginLink}>
					Already have an account? <Link to="/login">Login</Link>
				</div>
			</div>
		</div>
	);
};

export default Register;

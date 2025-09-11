import React, { useState, useEffect } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import Navbar from "./Navbar";
import styles from "./Layout.module.css";
import axios from "axios";

const Layout = ({ children }) => {
	const navigate = useNavigate();
	const [isAuthenticated, setIsAuthenticated] = useState(null);
	const [userType, setUserType] = useState(null);

	useEffect(() => {
		const verifyAuth = async () => {
			const token = localStorage.getItem(process.env.REACT_APP_TOKEN_KEY);
			const userData = localStorage.getItem(process.env.REACT_APP_USER_KEY);

			if (!token) {
				setIsAuthenticated(false);
				return;
			}

			try {
				// Verify token with backend
				const response = await axios.get(
					`${process.env.REACT_APP_API_BASE}/me`,
					{
						headers: {
							Authorization: `Bearer ${token}`,
						},
					}
				);

				console.log('Auth verification response:', response.data); // Debug log

				if (response.data) {
					setIsAuthenticated(true);
					setUserType(response.data.user_type);
					
					// If user is a recruiter trying to access candidate pages, redirect
					if (response.data.user_type === 'recruiter') {
						navigate('/recruiter-dashboard');
						return;
					}
				} else {
					console.log('No response data, clearing localStorage'); // Debug log
					localStorage.removeItem(process.env.REACT_APP_TOKEN_KEY);
					localStorage.removeItem(process.env.REACT_APP_USER_KEY);
					setIsAuthenticated(false);
				}
			} catch (error) {
				console.error('Auth verification failed:', error); // Debug log
				localStorage.removeItem(process.env.REACT_APP_TOKEN_KEY);
				localStorage.removeItem(process.env.REACT_APP_USER_KEY);
				setIsAuthenticated(false);
			}
		};

		verifyAuth();
	}, [navigate]);

	if (isAuthenticated === null) {
		return (
			<div className={styles.loadingContainer}>
				<div className={styles.loadingSpinner}>Loading...</div>
			</div>
		);
	}

	if (!isAuthenticated) {
		return <Navigate to="/login" replace />;
	}

	// If recruiter tries to access candidate layout, they've already been redirected
	return (
		<div className={styles.layoutContainer}>
			<Navbar userType={userType} />
			<main className={styles.mainContent}>{children}</main>
		</div>
	);
};

export default Layout;

import React, { useState, useEffect } from "react";
import { Navigate, useNavigate, Outlet } from "react-router-dom";
import Navbar from "./Navbar";
import styles from "./Layout.module.css";
import axios from "axios";
import { getToken, getUser, clearSession } from "shared/utils/session";

const Layout = () => {
	const navigate = useNavigate();
	const [isAuthenticated, setIsAuthenticated] = useState(null);
	const [userType, setUserType] = useState(null);

	useEffect(() => {
		const verifyAuth = async () => {
			const token = getToken();

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
					console.log('No response data, clearing session'); // Debug log
					clearSession();
					setIsAuthenticated(false);
				}
			} catch (error) {
				console.error('Auth verification failed:', error); // Debug log
				clearSession();
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

	return (
		<div className={styles.layoutContainer}>
			<Navbar userType={userType} />
			<main className={styles.mainContent}><Outlet /></main>
		</div>
	);
};

export default Layout;

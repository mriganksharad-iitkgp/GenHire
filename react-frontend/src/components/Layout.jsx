import React from "react";
import { Navigate } from "react-router-dom";
import Navbar from "./Navbar";
import styles from "./Layout.module.css";

const Layout = ({ children }) => {
	// Check if user is logged in
	const isLoggedIn = localStorage.getItem("companyxyz-token") !== null;

	// Redirect to login if not logged in
	if (!isLoggedIn) {
		return <Navigate to="/login" />;
	}

	return (
		<div className={styles.layoutContainer}>
			<Navbar />
			<main className={styles.mainContent}>{children}</main>
		</div>
	);
};

export default Layout;

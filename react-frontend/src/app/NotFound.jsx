import React from "react";
import { Link } from "react-router-dom";
import styles from "./NotFound.module.css";

const NotFound = () => {
	return (
		<div className={styles.notFoundContainer}>
			<div className={styles.content}>
				<h1>404</h1>
				<h2>Page Not Found</h2>
				<p>
					Sorry, the page you are looking for doesn't exist or has
					been moved.
				</p>
				<div className={styles.actions}>
					<Link to="/" className={styles.homeButton}>
						Go to Homepage
					</Link>
				</div>
			</div>
		</div>
	);
};

export default NotFound;

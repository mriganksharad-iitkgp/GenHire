import React, { useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import styles from "./Dashboard.module.css";

const Dashboard = () => {
	const navigate = useNavigate();

	// Check authentication when component mounts
	useEffect(() => {
		const isLoggedIn = localStorage.getItem("candidateLoggedIn") === "true";
		if (!isLoggedIn) {
			navigate("/login");
		}
	}, [navigate]);

	return (
		<div className={styles.dashboardContainer}>
			<header className={styles.header}>
				<div className={styles.logo}>
					<img src="../android-chrome-192x192.png" alt="Logo" />
					<h1>Candidate Portal</h1>
				</div>
				<div className={styles.userNav}>
					<Link to="/profile" className={styles.profileLink}>
						<img src="../android-chrome-192x192.png" alt="User" />
						<span>Profile</span>
					</Link>
				</div>
			</header>

			<div className={styles.content}>
				<div className={styles.welcomeSection}>
					<h2>Welcome to Your Dashboard</h2>
					<p>
						This is your central hub for managing your job
						applications and interviews.
					</p>
				</div>

				<div className={styles.cardsContainer}>
					<div className={styles.card}>
						<div className={styles.cardHeader}>
							<h3>Upcoming Interviews</h3>
							<span className={styles.badge}>2</span>
						</div>
						<div className={styles.cardBody}>
							<div className={styles.interviewItem}>
								<div className={styles.interviewInfo}>
									<h4>
										Technical Interview - Software Engineer
									</h4>
									<p>Tech Innovations Inc.</p>
								</div>
								<div className={styles.interviewMeta}>
									<div className={styles.interviewDate}>
										<i className="fa fa-calendar"></i>
										<span>Tomorrow, 10:00 AM</span>
									</div>
									<Link
										to="/interview/123"
										className={styles.interviewButton}
									>
										Join
									</Link>
								</div>
							</div>

							<div className={styles.interviewItem}>
								<div className={styles.interviewInfo}>
									<h4>HR Discussion - React Developer</h4>
									<p>DataViz Solutions</p>
								</div>
								<div className={styles.interviewMeta}>
									<div className={styles.interviewDate}>
										<i className="fa fa-calendar"></i>
										<span>Sep 28, 2:30 PM</span>
									</div>
									<Link
										to="/interview/456"
										className={styles.interviewButton}
									>
										Join
									</Link>
								</div>
							</div>
						</div>
					</div>

					<div className={styles.card}>
						<div className={styles.cardHeader}>
							<h3>Application Status</h3>
						</div>
						<div className={styles.cardBody}>
							<div className={styles.statsContainer}>
								<div className={styles.statItem}>
									<span className={styles.statNumber}>3</span>
									<span className={styles.statLabel}>
										Total Applications
									</span>
								</div>
								<div className={styles.statItem}>
									<span className={styles.statNumber}>1</span>
									<span className={styles.statLabel}>
										Shortlisted
									</span>
								</div>
								<div className={styles.statItem}>
									<span className={styles.statNumber}>1</span>
									<span className={styles.statLabel}>
										In Progress
									</span>
								</div>
								<div className={styles.statItem}>
									<span className={styles.statNumber}>1</span>
									<span className={styles.statLabel}>
										Rejected
									</span>
								</div>
							</div>
							<Link
								to="/profile"
								className={styles.viewAllButton}
							>
								View All Applications
							</Link>
						</div>
					</div>
				</div>

				<div className={styles.quickActionsSection}>
					<h3>Quick Actions</h3>
					<div className={styles.quickActionsGrid}>
						<Link to="/profile" className={styles.actionCard}>
							<i className="fa fa-user"></i>
							<span>Update Profile</span>
						</Link>
						<Link to="/profile" className={styles.actionCard}>
							<i className="fa fa-file-text"></i>
							<span>Update CV</span>
						</Link>
						<div
							className={styles.actionCard}
							onClick={() => navigate("/interview/999")}
						>
							<i className="fa fa-microphone"></i>
							<span>Practice Interview</span>
						</div>
						<div
							className={styles.actionCard}
							onClick={() => {
								localStorage.removeItem("candidateLoggedIn");
								navigate("/login");
							}}
						>
							<i className="fa fa-sign-out"></i>
							<span>Logout</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export default Dashboard;

import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import styles from "./Navbar.module.css";

const Navbar = () => {
	const navigate = useNavigate();
	const [darkMode, setDarkMode] = useState(false);
	const [userMenuOpen, setUserMenuOpen] = useState(false);
	const userMenuRef = useRef(null);

	// Check dark mode preference on component mount
	useEffect(() => {
		const savedDarkMode = localStorage.getItem("darkMode") === "true";
		setDarkMode(savedDarkMode);
		if (savedDarkMode) {
			document.body.classList.add("dark");
		}
	}, []);

	// Handle dark mode toggle
	const toggleDarkMode = () => {
		const newDarkMode = !darkMode;
		setDarkMode(newDarkMode);
		localStorage.setItem("darkMode", newDarkMode.toString());
		if (newDarkMode) {
			document.body.classList.add("dark");
		} else {
			document.body.classList.remove("dark");
		}
	};

	// Handle logout
	const handleLogout = () => {
		localStorage.removeItem("candidateLoggedIn");
		navigate("/login");
	};

	// Close user menu when clicking outside
	useEffect(() => {
		const handleClickOutside = (event) => {
			if (
				userMenuRef.current &&
				!userMenuRef.current.contains(event.target)
			) {
				setUserMenuOpen(false);
			}
		};

		document.addEventListener("mousedown", handleClickOutside);
		return () => {
			document.removeEventListener("mousedown", handleClickOutside);
		};
	}, []);

	return (
		<header className={styles.navbar}>
			<div className={styles.navContainer}>
				<div className={styles.navBrand}>
					<Link to="/" className={styles.brandLink}>
						<h1>JobPortal</h1>
					</Link>
				</div>

				<nav className={styles.navLinks}>
					<Link to="/" className={styles.navLink}>
						Jobs
					</Link>
					<Link to="/profile#applications" className={styles.navLink}>
						My Applications
					</Link>
					<Link to="/profile#interviews" className={styles.navLink}>
						Interviews
					</Link>
				</nav>

				<div className={styles.navActions}>
					<button
						className={styles.darkModeButton}
						onClick={toggleDarkMode}
						aria-label="Toggle dark mode"
					>
						{darkMode ? (
							<i className="fa fa-sun-o"></i>
						) : (
							<i className="fa fa-moon-o"></i>
						)}
					</button>

					<div className={styles.userDropdown} ref={userMenuRef}>
						<button
							className={styles.userButton}
							onClick={() => setUserMenuOpen(!userMenuOpen)}
						>
							<div className={styles.avatar}>
								<img
									src="../android-chrome-192x192.png"
									alt="User"
									onError={(e) => {
										e.target.onerror = null;
										e.target.src =
											"https://via.placeholder.com/40?text=User";
									}}
								/>
							</div>
							<span className={styles.userName}>
								{localStorage.getItem("candidateName") ||
									"User"}
							</span>
							<i
								className={`fa fa-caret-down ${
									userMenuOpen ? styles.rotateIcon : ""
								}`}
							></i>
						</button>

						{userMenuOpen && (
							<div className={styles.dropdownMenu}>
								<Link
									to="/profile"
									className={styles.dropdownItem}
								>
									<i className="fa fa-user"></i>
									My Profile
								</Link>
								<Link
									to="/profile#applications"
									className={styles.dropdownItem}
								>
									<i className="fa fa-file-text"></i>
									My Applications
								</Link>
								<Link
									to="/profile#interviews"
									className={styles.dropdownItem}
								>
									<i className="fa fa-calendar"></i>
									Upcoming Interviews
								</Link>
								<Link
									to="/interview/999"
									className={styles.dropdownItem}
								>
									<i className="fa fa-microphone"></i>
									Practice Interview
								</Link>
								<button
									className={styles.dropdownItem}
									onClick={handleLogout}
								>
									<i className="fa fa-sign-out"></i>
									Logout
								</button>
							</div>
						)}
					</div>
				</div>
			</div>
		</header>
	);
};

export default Navbar;

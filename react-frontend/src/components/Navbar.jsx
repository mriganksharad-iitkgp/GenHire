import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import styles from "./Navbar.module.css";
import { UpgradeButton } from "./recruiter/subscription";

const Navbar = ({ userType = "candidate" }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [darkMode, setDarkMode] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [profilePhoto, setProfilePhoto] = useState(null);
  const [userName, setUserName] = useState("");
  const [companyName, setCompanyName] = useState("TechCorp Solutions");
  const userMenuRef = useRef(null);

  // Check dark mode preference on component mount
  useEffect(() => {
    const savedDarkMode = localStorage.getItem("darkMode") === "true";
    setDarkMode(savedDarkMode);
    if (savedDarkMode) {
      document.body.classList.add("dark");
    }

    // Load user data
    loadUserData();
  }, []);

  // Load user data (profile photo and name)
  const loadUserData = async () => {
    try {
      const token = localStorage.getItem("companyxyz-token");
      if (!token) return;

      // Load profile data
      const profileResponse = await fetch(
        `${process.env.REACT_APP_API_URL}/api/profile`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      );

      if (profileResponse.ok) {
        const profileData = await profileResponse.json();
        setUserName(profileData.name || "User");

        // Set company name for recruiters
        if (userType === "recruiter" && profileData.company_name) {
          setCompanyName(profileData.company_name);
        }

        // Load profile photo if it exists
        if (profileData.profile_photo) {
          loadProfilePhoto();
        }
      }
    } catch (error) {
      console.error("Error loading user data in navbar:", error);
    }
  };

  // Load profile photo
  const loadProfilePhoto = async () => {
    try {
      const token = localStorage.getItem("companyxyz-token");
      if (!token) return;

      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/api/view-photo`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        const blob = await response.blob();
        const photoUrl = URL.createObjectURL(blob);
        setProfilePhoto(photoUrl);
      }
    } catch (error) {
      console.error("Error loading profile photo in navbar:", error);
    }
  };

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
    localStorage.removeItem("companyxyz-token");
    localStorage.removeItem("companyxyz-user");
    navigate("/login");
  };

  // Close user menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
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
          <Link
            to={userType === "recruiter" ? "/recruiter-dashboard" : "/"}
            className={styles.brandLink}
          >
            <h1>
              {userType === "recruiter"
                ? "SmartHire Recruiter Portal"
                : "SmartHire Career Portal"}
            </h1>
          </Link>
        </div>

        <nav className={styles.navLinks}>
          {userType === "recruiter" ? (
            <>
              <Link
                to="/recruiter-dashboard"
                className={`${styles.navLink} ${
                  location.pathname === "/recruiter-dashboard"
                    ? styles.active
                    : ""
                }`}
              >
                Dashboard
              </Link>
              <Link
                to="/recruiter/cost-statistics"
                className={`${styles.navLink} ${
                  location.pathname === "/recruiter/cost-statistics"
                    ? styles.active
                    : ""
                }`}
              >
                Cost Statistics
              </Link>
            </>
          ) : (
            <>
              <Link
                to="/"
                className={`${styles.navLink} ${
                  location.pathname === "/" ? styles.active : ""
                }`}
              >
                Open Positions
              </Link>
              <Link
                to="/profile#applications"
                className={`${styles.navLink} ${
                  location.pathname === "/profile" ? styles.active : ""
                }`}
              >
                My Applications
              </Link>
              <Link
                to="/practice"
                className={`${styles.navLink} ${
                  location.pathname === "/practice" ? styles.active : ""
                }`}
              >
                Practice
              </Link>
            </>
          )}
        </nav>

        <div className={styles.navActions}>
          {/* Upgrade Button for Recruiters */}
          {userType === "recruiter" && <UpgradeButton />}

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
                  src={profilePhoto || "../android-chrome-192x192.png"}
                  alt="User"
                  onError={(e) => {
                    e.target.onerror = null;
                    e.target.src = "https://via.placeholder.com/40?text=User";
                  }}
                />
              </div>
              <span className={styles.userName}>{userName || "User"}</span>
              <i
                className={`fa fa-caret-down ${
                  userMenuOpen ? styles.rotateIcon : ""
                }`}
              ></i>
            </button>

            {userMenuOpen && (
              <div className={styles.dropdownMenu}>
                {userType === "recruiter" ? (
                  <>
                    <Link
                      to="/recruiter-dashboard"
                      className={styles.dropdownItem}
                      onClick={() => setUserMenuOpen(false)}
                    >
                      <i className="fa fa-dashboard"></i>
                      Dashboard
                    </Link>
                    <Link
                      to="/recruiter-dashboard?tab=profile"
                      className={styles.dropdownItem}
                      onClick={() => setUserMenuOpen(false)}
                    >
                      <i className="fa fa-building"></i>
                      Company Profile
                    </Link>
                  </>
                ) : (
                  <>
                    <Link
                      to="/profile#bio"
                      className={styles.dropdownItem}
                      onClick={() => {
                        setUserMenuOpen(false);
                        // Force navigation even if already on profile page
                        if (window.location.pathname === "/profile") {
                          window.location.hash = "#bio";
                        }
                      }}
                    >
                      <i className="fa fa-user"></i>
                      My Profile
                    </Link>
                    <Link
                      to="/profile#applications"
                      className={styles.dropdownItem}
                      onClick={() => {
                        setUserMenuOpen(false);
                        // Force navigation even if already on profile page
                        if (window.location.pathname === "/profile") {
                          window.location.hash = "#applications";
                        }
                      }}
                    >
                      <i className="fa fa-file-text"></i>
                      My Applications
                    </Link>
                  </>
                )}
                <button className={styles.dropdownItem} onClick={handleLogout}>
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

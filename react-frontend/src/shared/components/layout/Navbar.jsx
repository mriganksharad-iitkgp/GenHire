import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import styles from "./Navbar.module.css";
import { UpgradeButton } from "components/recruiter/subscription";
import { CandidatePlanButton } from "components/candidate/subscription";
import { useCandidateData } from "contexts/CandidateDataContext";
import { getProfile } from "services/api";
import { getToken, clearSession } from "shared/utils/session";

const Navbar = ({ userType = "candidate" }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const userMenuRef = useRef(null);
  const { profile, profilePhotoUrl, loadProfileCached, clearAllCaches } = useCandidateData();

  const userName = profile?.name || "User";

  useEffect(() => {
    // Load user data
    loadUserData();
  }, []);

  // Load user data (profile photo and name)
  const loadUserData = async () => {
    try {
      const token = getToken();
      if (!token) return;

      await loadProfileCached(false, getProfile);
    } catch (error) {
      console.error("Error loading user data in navbar:", error);
    }
  };

  // Handle logout
  const handleLogout = () => {
    clearSession();
    if (clearAllCaches) {
      clearAllCaches();
    }
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
            to={userType === "recruiter" ? "/recruiter-dashboard" : "/dashboard"}
            className={styles.brandLink}
          >
            <div className={styles.logoIcon}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 7h-9"></path>
                <path d="M14 17H5"></path>
                <circle cx="17" cy="17" r="3"></circle>
                <circle cx="7" cy="7" r="3"></circle>
              </svg>
            </div>
            <h1>
              GenHire
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
              <Link
                to="/recruiter/team"
                className={`${styles.navLink} ${
                  location.pathname === "/recruiter/team" ? styles.active : ""
                }`}
              >
                Team
              </Link>
            </>
          ) : (
            <>
              <Link
                to="/dashboard"
                className={`${styles.navLink} ${
                  location.pathname === "/dashboard" ? styles.active : ""
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
              <Link
                to="/candidate/cost-statistics"
                className={`${styles.navLink} ${
                  location.pathname === "/candidate/cost-statistics" ? styles.active : ""
                }`}
              >
                Cost Statistics
              </Link>
              <Link
                to="/team"
                className={`${styles.navLink} ${
                  location.pathname === "/team" ? styles.active : ""
                }`}
              >
                Team
              </Link>
            </>
          )}
        </nav>

        <div className={styles.navActions}>
          {/* Upgrade Button for Recruiters */}
          {userType === "recruiter" && <UpgradeButton />}
          {userType !== "recruiter" && <CandidatePlanButton />}

          <div className={styles.userDropdown} ref={userMenuRef}>
            <button
              className={styles.userButton}
              onClick={() => setUserMenuOpen(!userMenuOpen)}
            >
              <div className={styles.avatar}>
                <img
                  key={profilePhotoUrl || 'default'}
                  src={profilePhotoUrl || "../android-chrome-192x192.png"}
                  alt="User"
                  onError={(e) => {
                    e.target.onerror = null;
                    e.target.src = "/android-chrome-192x192.png";
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

        {/* Hamburger Menu Button for Mobile */}
        <button 
          className={styles.mobileMenuBtn}
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle mobile menu"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {mobileMenuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile Nav Drawer */}
      <div className={`${styles.mobileDrawer} ${mobileMenuOpen ? styles.drawerOpen : ''}`}>
        <div className={styles.mobileNavLinks}>
          {userType === "recruiter" ? (
            <>
              <Link to="/recruiter-dashboard" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>Dashboard</Link>
              <Link to="/recruiter/cost-statistics" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>Cost Statistics</Link>
              <Link to="/recruiter/team" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>Team</Link>
              <div className={styles.mobileDivider}></div>
              <Link to="/recruiter-dashboard?tab=profile" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>Company Profile</Link>
            </>
          ) : (
            <>
              <Link to="/dashboard" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>Open Positions</Link>
              <Link to="/profile#applications" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>My Applications</Link>
              <Link to="/practice" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>Practice</Link>
              <Link to="/candidate/cost-statistics" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>Cost Statistics</Link>
              <Link to="/team" className={styles.mobileNavLink} onClick={() => setMobileMenuOpen(false)}>Team</Link>
              <div className={styles.mobileDivider}></div>
              <Link to="/profile#bio" className={styles.mobileNavLink} onClick={() => {
                setMobileMenuOpen(false);
                if (window.location.pathname === "/profile") window.location.hash = "#bio";
              }}>My Profile</Link>
            </>
          )}
          <button className={styles.mobileNavLink} onClick={() => { setMobileMenuOpen(false); handleLogout(); }}>
            <i className="fa fa-sign-out" style={{marginRight: '8px'}}></i> Logout
          </button>
        </div>
      </div>
      
      {mobileMenuOpen && (
        <div className={styles.drawerOverlay} onClick={() => setMobileMenuOpen(false)}></div>
      )}
    </header>
  );
};

export default Navbar;

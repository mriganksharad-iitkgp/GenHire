import { navigationItems, navigationActive } from "./navigation";
import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import styles from "./Navbar.module.css";
import { UpgradeButton } from "features/payment/components/recruiter-subscription";
import { CandidatePlanButton } from "features/payment/components/candidate-subscription";
import { useCandidateData } from "features/candidate/context/CandidateDataContext";
import { getProfile } from "shared/api/endpoints";
import { getToken, getUser, clearSession } from "shared/utils/session";

const Navbar = ({ userType = "candidate" }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const userMenuRef = useRef(null);
  const { profile, profilePhotoUrl, loadProfileCached, clearAllCaches } = useCandidateData();

  const userName = profile?.name || "User";

  // Burner (invite-only) candidates are scoped to the job they were
  // invited to — Practice, Cost Statistics, Team, and credit purchase are
  // general candidate features the backend now rejects for them, so hide
  // the links entirely instead of surfacing a 403 on click.
  const cachedUser = (() => {
    try {
      return getUser();
    } catch (_) {
      return null;
    }
  })();
  const isInviteOnly = !!(cachedUser && (cachedUser.is_invite_only || cachedUser.isInviteOnly));

  const links = navigationItems(userType, isInviteOnly);

  // Load user data (profile photo and name) once on mount
  useEffect(() => {
    const loadUserData = async () => {
      try {
        const token = getToken();
        if (!token) return;

        await loadProfileCached(false, getProfile);
      } catch (error) {
        console.error("Error loading user data in navbar:", error);
      }
    };
    loadUserData();
  }, [loadProfileCached]);

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

  useEffect(() => {
    setUserMenuOpen(false); setMobileMenuOpen(false);
  }, [location.pathname, location.search, location.hash]);

  useEffect(() => {
    const closeOnEscape = (event) => { if (event.key === "Escape") { setUserMenuOpen(false); setMobileMenuOpen(false); } };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, []);


  return (
    <header className={`${styles.navbar} ${userType === "recruiter" ? styles.recruiterNavbar : ""}`}>
      <div className={styles.navContainer}>
        <div className={styles.navBrand}>
          <Link
            to={userType === "recruiter" ? "/recruiter/dashboard" : "/dashboard"}
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

        <nav className={styles.navLinks} aria-label={userType === "recruiter" ? "Recruiter sections" : "Candidate sections"}>
          {links.map(item => <Link key={item.id} to={item.to} aria-current={navigationActive(item, location) ? "page" : undefined}
            className={`${styles.navLink} ${navigationActive(item, location) ? styles.active : ""}`}>{item.label}</Link>)}
        </nav>

        <div className={styles.navActions}>
          {/* Upgrade Button for Recruiters */}
          {userType === "recruiter" && <UpgradeButton />}
          {userType !== "recruiter" && !isInviteOnly && <CandidatePlanButton />}

          <div className={styles.userDropdown} ref={userMenuRef}>
            <button
              className={styles.userButton}
              aria-expanded={userMenuOpen}
              aria-label="Account menu"
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
                      to="/recruiter/dashboard"
                      className={styles.dropdownItem}
                      onClick={() => setUserMenuOpen(false)}
                    >
                      <i className="fa fa-dashboard"></i>
                      Dashboard
                    </Link>
                    <Link
                      to="/recruiter/dashboard?tab=profile"
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
                      to="/profile"
                      className={styles.dropdownItem}
                      onClick={() => setUserMenuOpen(false)}
                    >
                      <i className="fa fa-user"></i>
                      My Profile
                    </Link>
                    <Link
                      to="/applications"
                      className={styles.dropdownItem}
                      onClick={() => setUserMenuOpen(false)}
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
          aria-label={mobileMenuOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={mobileMenuOpen}
          aria-controls="workspace-menu"
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
      <div id="workspace-menu" hidden={!mobileMenuOpen} className={`${styles.mobileDrawer} ${mobileMenuOpen ? styles.drawerOpen : ''}`}>
        <div className={styles.mobileNavLinks}>
          {links.map(item => <Link key={item.id} to={item.to} aria-current={navigationActive(item, location) ? "page" : undefined}
            className={`${styles.mobileNavLink} ${navigationActive(item, location) ? styles.active : ""}`} onClick={() => setMobileMenuOpen(false)}>{item.label}</Link>)}
          <div className={styles.mobileDivider} />
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

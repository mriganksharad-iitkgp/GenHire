import React from "react";
import { useNavigate } from "react-router-dom";
import styles from "features/recruiter/pages/RecruiterDashboard.module.css";

export const Tabs = ({ activeTab, onChange }) => {
  const navigate = useNavigate();
  
  return (
    <div className={styles.tabNavigation}>
      <div className={styles.tabList}>
        <button
          className={`${styles.tabButton} ${
            activeTab === "overview" ? styles.active : ""
          }`}
          onClick={() => onChange("overview")}
        >
          <i className="fa fa-dashboard"></i> Overview
        </button>
        <button
          className={`${styles.tabButton} ${
            activeTab === "jobs" ? styles.active : ""
          }`}
          onClick={() => onChange("jobs")}
        >
          <i className="fa fa-briefcase"></i> Job Postings
        </button>
        <button
          className={`${styles.tabButton} ${
            activeTab === "candidates" ? styles.active : ""
          }`}
          onClick={() => onChange("candidates")}
        >
          <i className="fa fa-users"></i> Candidates
        </button>
        <button
          className={`${styles.tabButton} ${
            activeTab === "profile" ? styles.active : ""
          }`}
          onClick={() => onChange("profile")}
        >
          <i className="fa fa-building"></i> Company Profile
        </button>
        <button
          className={`${styles.tabButton} ${
            activeTab === "cost-statistics" ? styles.active : ""
          }`}
          onClick={() => navigate("/recruiter/cost-statistics")}
        >
          <i className="fa fa-chart-pie"></i> Cost Statistics
        </button>
      </div>
    </div>
  );
};

export default Tabs;

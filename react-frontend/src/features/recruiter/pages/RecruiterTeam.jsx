import React from "react";
import Navbar from "shared/components/layout/Navbar";
import TeamPage from "./TeamPage";
import styles from "./TeamPage.module.css";

const RecruiterTeam = () => {
  return (
    <div className={styles.recruiterWrapper}>
      <Navbar userType="recruiter" />
      <TeamPage />
    </div>
  );
};

export default RecruiterTeam;

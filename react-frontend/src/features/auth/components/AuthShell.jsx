import React from "react";
import AuthStory from "./AuthStory";
import AuthBrand from "./AuthBrand";
import styles from "./AuthShell.module.css";
export default function AuthShell({ children, wide = false, title, accent, description }) {
  return <main className={`${styles.layout} ${wide ? styles.wide : ""}`}>
    <AuthStory title={title} accent={accent} description={description} />
    <section className={styles.formPanel}><AuthBrand className={styles.mobileBrand} />{children}</section>
  </main>;
}

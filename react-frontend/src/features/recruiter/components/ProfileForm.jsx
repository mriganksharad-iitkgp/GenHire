import React from "react";
import styles from "features/recruiter/pages/RecruiterDashboard.module.css";

export default function ProfileForm({ companyProfile, isEditing, onChange, onSave, onCancel, onDeleteAccount }) {
  const fields = [["email","Account email","email"],["companyName","Company name","text"],["industry","Industry","text"],["location","Location","text"],["size","Company size","select"],["website","Website","url"]];
  return <div className={styles.profileForm}>
    {isEditing ? <form onSubmit={event => { event.preventDefault(); onSave(); }}>
      <div className={styles.companyFields}>{fields.map(([key,label,type]) => <div className={styles.formGroup} key={key}>
        <label htmlFor={`company-${key}`}>{label}</label>
        {type === "select" ? <select id={`company-${key}`} value={companyProfile[key] || ""} onChange={event => onChange({...companyProfile,[key]:event.target.value})}><option value="">Select company size</option>{["1-10 employees","11-50 employees","51-100 employees","100-500 employees","500+ employees"].map(size => <option key={size}>{size}</option>)}</select> : <input id={`company-${key}`} type={type} value={companyProfile[key] || ""} disabled={key === "email"} onChange={event => onChange({...companyProfile,[key]:event.target.value})} />}
        {key === "email" && <small>Your sign-in email cannot be changed.</small>}
      </div>)}</div>
      <div className={styles.formGroup}><label htmlFor="company-description">Company description</label><textarea id="company-description" value={companyProfile.description || ""} onChange={event => onChange({...companyProfile,description:event.target.value})} rows={5} /></div>
      <div className={styles.formActions}><button className={styles.primaryButton} type="submit"><i className="fa fa-check" aria-hidden="true" /> Save Changes</button><button className={styles.secondaryButton} type="button" onClick={onCancel}>Cancel</button></div>
    </form> : <>
      <div className={styles.companyIdentity}><span className={styles.companyMark} aria-hidden="true"><i className="fa fa-building-o" /></span><div><h2>{companyProfile.companyName || "Your company"}</h2><p>{[companyProfile.industry,companyProfile.location].filter(Boolean).join(" / ") || "Add your company details to introduce your team."}</p></div></div>
      <dl className={styles.companyFields}>{fields.filter(([key]) => key !== "companyName").map(([key,label]) => <div className={styles.companyField} key={key}><dt>{label}</dt><dd>{key === "website" && /^https?:\/\//i.test(companyProfile[key] || "") ? <a href={companyProfile[key]} target="_blank" rel="noreferrer">{companyProfile[key]}</a> : companyProfile[key] || "Not provided"}</dd></div>)}</dl>
      <section className={styles.companyDescription}><h3>About the company</h3><p>{companyProfile.description || "Add a description to tell candidates about your company and culture."}</p></section>
    </>}
    <section className={styles.accountSettings}><div><h3>Account settings</h3><p>Deleting your account is permanent.</p></div><button type="button" className={styles.dangerButton} onClick={onDeleteAccount}>Delete Account</button></section>
  </div>;
}

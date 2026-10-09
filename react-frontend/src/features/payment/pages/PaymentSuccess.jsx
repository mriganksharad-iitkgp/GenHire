import React from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CreditCard, Home, FileText } from "lucide-react";
import { getUser } from "shared/utils/session";
import styles from "./PaymentSuccess.module.css";

export default function PaymentSuccess() {
  const navigate = useNavigate(); const [params] = useSearchParams();
  const user = getUser(); const role = user?.userType || user?.user_type;
  const dashboard = role === "recruiter" ? "/recruiter/dashboard" : role === "admin" ? "/admin" : user ? "/dashboard" : "/login";
  const history = role === "recruiter" ? "/recruiter/subscription" : "/candidate/subscription";
  const reference = params.get("session_id");
  return <main className={styles.container}><section className={styles.card}>
    <div className={styles.iconWrapper}><CreditCard size={48} aria-hidden="true" /></div>
    <h1 className={styles.title}>Review your payment</h1>
    <p className={styles.subtitle}>Your wallet shows the confirmed transaction status.</p>
    <p className={styles.description}>Return to your wallet to check available credits and recharge history. Check the confirmed transaction status before starting another checkout.</p>
    {reference && <div className={styles.transactionBox}><p className={styles.transactionLabel}>Payment reference</p><p className={styles.transactionId}>{reference}</p></div>}
    <div className={styles.buttonGroup}><button className={styles.primaryButton} onClick={() => navigate(dashboard)}><Home size={18} />Return to dashboard</button><button className={styles.secondaryButton} onClick={() => navigate(user ? history : "/login")}><FileText size={18} />Review wallet history</button></div>
  </section></main>;
}

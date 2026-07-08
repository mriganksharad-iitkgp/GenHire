/**
 * PaymentHistory - Display payment transaction history
 */
import React from "react";
import { CalendarIcon } from "./Icons";
import styles from "./PaymentHistory.module.css";

/**
 * Format price for display
 */
const formatPrice = (price) => {
  if (price === 0) return "Free";
  return `₹${price.toFixed(2)}`;
};

/**
 * Format date for display
 */
const formatDate = (dateStr) => {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleDateString("en-IN", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

/**
 * Status badge component
 */
const StatusBadge = ({ status }) => {
  const normalizedStatus = status?.toLowerCase() || "unknown";
  return (
    <span className={`${styles.status} ${styles[normalizedStatus]}`}>
      {status || "Unknown"}
    </span>
  );
};

/**
 * Empty state component
 */
const EmptyState = () => (
  <div className={styles.empty}>
    <CalendarIcon />
    <h3>No payment history</h3>
    <p>Your payment history will appear here after your first transaction.</p>
  </div>
);

/**
 * PaymentHistory Component
 */
const PaymentHistory = ({ payments = [] }) => {
  if (payments.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className={styles.container}>
      <div className={styles.table}>
        <div className={styles.header}>
          <span>Date</span>
          <span>Plan</span>
          <span>Credits</span>
          <span>Amount</span>
          <span>Status</span>
        </div>
        {payments.map((payment, idx) => (
          <div key={payment.id || idx} className={styles.row}>
            <span>{formatDate(payment.created_at)}</span>
            <span>
              {payment.plan_name || "Subscription"}
              {payment.is_migration && (
                <small className={styles.migrationTag}>Migration</small>
              )}
            </span>
            <span>
              {payment.recharge_credits
                ? `${Number(payment.recharge_credits).toLocaleString("en-IN")} credits`
                : "-"}
            </span>
            <span>{formatPrice(payment.amount)}</span>
            <StatusBadge status={payment.status} />
          </div>
        ))}
      </div>
    </div>
  );
};

export default PaymentHistory;

/**
 * PlanCard - Individual subscription plan display card
 */
import React from "react";
import { CheckIcon, XIcon, StarIcon } from "./Icons";
import styles from "./PlanCard.module.css";

/**
 * Format price for display
 */
const formatPrice = (price) => {
  if (price === 0) return "Free";
  return `₹${price.toFixed(2)}`;
};

/**
 * Get plan features based on plan details
 */
const getPlanFeatures = (plan) => {
  const features = [];

  // Interview quota
  if (plan.interviews_allowed === -1 || plan.is_unlimited) {
    features.push({ text: "Unlimited AI Interviews", included: true });
  } else {
    features.push({
      text: `${plan.interviews_allowed} AI Interviews`,
      included: true,
    });
  }

  // Standard features based on price tier
  features.push({ text: "Smart CV Matching", included: true });
  features.push({ text: "Candidate Analytics", included: plan.price > 0 });
  features.push({ text: "Priority Support", included: plan.price >= 49 });
  features.push({ text: "Custom Branding", included: plan.price >= 99 });
  features.push({ text: "API Access", included: plan.price >= 99 });

  return features;
};

/**
 * Feature list item component
 */
const FeatureItem = ({ text, included }) => (
  <li className={included ? styles.included : styles.notIncluded}>
    {included ? <CheckIcon /> : <XIcon />}
    {text}
  </li>
);

/**
 * PlanCard Component
 */
const PlanCard = ({ plan, isCurrent, isPopular, isLoading, onSelect }) => {
  const features = getPlanFeatures(plan);
  const planId = plan.id || plan.slug;

  return (
    <div
      className={`${styles.card} ${isCurrent ? styles.current : ""} ${
        isPopular ? styles.popular : ""
      }`}
    >
      {isPopular && <div className={styles.popularBadge}>Most Popular</div>}

      <div className={styles.header}>
        <h3>{plan.name}</h3>
        <p className={styles.description}>
          {plan.description || "Perfect for your hiring needs"}
        </p>
      </div>

      <div className={styles.price}>
        <span className={styles.amount}>{formatPrice(plan.price)}</span>
        {plan.price > 0 && (
          <span className={styles.period}>
            /{plan.billing_period || "month"}
          </span>
        )}
      </div>

      <ul className={styles.features}>
        {features.map((feature, idx) => (
          <FeatureItem key={idx} {...feature} />
        ))}
      </ul>

      <button
        className={`${styles.button} ${isCurrent ? styles.currentButton : ""}`}
        onClick={() => !isCurrent && onSelect?.(planId)}
        disabled={isCurrent || isLoading}
      >
        {isLoading ? (
          <>
            <span className={styles.spinner} />
            Processing...
          </>
        ) : isCurrent ? (
          <>
            <CheckIcon />
            Current Plan
          </>
        ) : (
          <>
            <StarIcon />
            {plan.price === 0 ? "Select Plan" : "Upgrade Now"}
          </>
        )}
      </button>
    </div>
  );
};

export default PlanCard;

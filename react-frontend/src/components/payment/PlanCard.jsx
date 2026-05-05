/**
 * PlanCard - Individual recharge pack display card
 */
import React from "react";
import { CheckIcon, XIcon, StarIcon } from "./Icons";
import styles from "./PlanCard.module.css";

/**
 * Format price for display
 */
const formatPrice = (price) => {
  if (price === 0) return "Free";
  // Format for Indian Rupees
  return `₹${price.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

/**
 * Get plan features based on plan details
 * Always use standard features list for consistent display
 */
const getPlanFeatures = (plan) => {
  const features = [];
  const rechargeCredits = Number(
    plan.recharge_credits ?? plan.monthly_credits ?? plan.credits_allocated ?? 0,
  );

  if (rechargeCredits > 0) {
    features.push({
      text: `${rechargeCredits.toLocaleString("en-IN")} Non-expiring credits`,
      included: true,
    });
  } else if (plan.interviews_allowed === -1 || plan.is_unlimited) {
    features.push({ text: "Unlimited Usage Credits", included: true });
  } else {
    features.push({
      text: `${plan.interviews_allowed} AI Interviews`,
      included: true,
    });
  }

  features.push({ text: "Credits never expire", included: true });
  features.push({ text: "Recharge when wallet runs low", included: true });

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
  const isDisabled = Boolean(isCurrent || isLoading || plan.disable_action);

  const getButtonLabel = () => {
    if (isLoading) return "Processing...";
    if (isCurrent) return "Last Recharge Pack";
    if (plan.cta_label) return String(plan.cta_label);
    return plan.price === 0 ? "Select Pack" : "Recharge Credits";
  };

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
        {plan.price > 0 && <span className={styles.period}> one-time recharge</span>}
      </div>

      <ul className={styles.features}>
        {features.map((feature, idx) => (
          <FeatureItem key={idx} {...feature} />
        ))}
      </ul>

      <button
        className={`${styles.button} ${isCurrent ? styles.currentButton : ""}`}
        onClick={() => !isDisabled && onSelect?.(planId)}
        disabled={isDisabled}
      >
        {isLoading ? (
          <>
            <span className={styles.spinner} />
            {getButtonLabel()}
          </>
        ) : isCurrent ? (
          <>
            <CheckIcon />
            {getButtonLabel()}
          </>
        ) : (
          <>
            <StarIcon />
            {getButtonLabel()}
          </>
        )}
      </button>
    </div>
  );
};

export default PlanCard;

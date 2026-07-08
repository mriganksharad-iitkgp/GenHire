import React, { useEffect } from "react";
import styles from "./DetailModal.module.css";

/**
 * Reusable Detail Modal Component
 * Props:
 * - isOpen: boolean
 * - onClose: function
 * - title: string
 * - subtitle: string (optional)
 * - children: React nodes
 * - size: 'small' | 'medium' | 'large' | 'full' (default: 'medium')
 * - actions: array of { label, onClick, variant, disabled, loading }
 */
const DetailModal = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  size = "medium",
  actions = [],
}) => {
  // Close on escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={`${styles.modal} ${styles[size]}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerContent}>
            <h2 className={styles.title}>{title}</h2>
            {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
          </div>
          <button className={styles.closeButton} onClick={onClose}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className={styles.body}>{children}</div>

        {/* Footer Actions */}
        {actions.length > 0 && (
          <div className={styles.footer}>
            {actions.map((action, index) => (
              <button
                key={index}
                className={`${styles.actionButton} ${styles[action.variant || "secondary"]}`}
                onClick={action.onClick}
                disabled={action.disabled || action.loading}
              >
                {action.loading ? (
                  <span className={styles.buttonSpinner}></span>
                ) : null}
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// Subcomponents for structured content
export const ModalSection = ({ title, children, collapsible = false }) => {
  const [isCollapsed, setIsCollapsed] = React.useState(false);

  return (
    <div className={styles.section}>
      <div
        className={`${styles.sectionHeader} ${collapsible ? styles.collapsible : ""}`}
        onClick={() => collapsible && setIsCollapsed(!isCollapsed)}
      >
        <h3 className={styles.sectionTitle}>{title}</h3>
        {collapsible && (
          <svg
            className={`${styles.collapseIcon} ${isCollapsed ? styles.collapsed : ""}`}
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        )}
      </div>
      {!isCollapsed && <div className={styles.sectionContent}>{children}</div>}
    </div>
  );
};

export const ModalField = ({ label, value, type = "text", editable = false, onChange, options = [] }) => {
  if (editable) {
    if (type === "select") {
      return (
        <div className={styles.field}>
          <label className={styles.fieldLabel}>{label}</label>
          <select
            className={styles.fieldSelect}
            value={value || ""}
            onChange={(e) => onChange(e.target.value)}
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      );
    }
    if (type === "textarea") {
      return (
        <div className={styles.field}>
          <label className={styles.fieldLabel}>{label}</label>
          <textarea
            className={styles.fieldTextarea}
            value={value || ""}
            onChange={(e) => onChange(e.target.value)}
            rows={4}
          />
        </div>
      );
    }
    return (
      <div className={styles.field}>
        <label className={styles.fieldLabel}>{label}</label>
        <input
          type={type}
          className={styles.fieldInput}
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    );
  }

  return (
    <div className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      <span className={styles.fieldValue}>{value || "N/A"}</span>
    </div>
  );
};

export const ModalGrid = ({ columns = 2, children }) => {
  return (
    <div className={styles.grid} style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
      {children}
    </div>
  );
};

export const ModalBadge = ({ children, variant = "default" }) => {
  return <span className={`${styles.badge} ${styles[variant]}`}>{children}</span>;
};

export default DetailModal;

import React, { useEffect } from "react";
import styles from "./Modal.module.css";

/**
 * The shared modal shell. Owns the overlay/dismiss/ESC behavior every bespoke
 * modal used to reimplement; visuals stay with each consumer via
 * overlayClassName/contentClassName (defaults provided for new modals).
 *
 * Behavior notes (matching the modals this replaces):
 * - Renders in-tree (no portal) — existing stacking contexts depend on it.
 * - closeOnEsc is opt-IN: none of the legacy modals closed on ESC, so
 *   migrated ones keep their exact behavior unless they ask for it.
 * - Overlay click closes unless closeOnOverlayClick={false} (e.g. mid-payment).
 */
export default function Modal({
  isOpen,
  onClose,
  overlayClassName,
  contentClassName,
  closeOnOverlayClick = true,
  closeOnEsc = false,
  children,
}) {
  useEffect(() => {
    if (!isOpen || !closeOnEsc) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, closeOnEsc, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className={overlayClassName || styles.overlay}
      onClick={closeOnOverlayClick ? onClose : undefined}
    >
      <div
        className={contentClassName || styles.content}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

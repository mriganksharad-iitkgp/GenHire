import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import styles from "./Modal.module.css";

// Only the most recently opened dialog handles focus and dismissal. Keeping
// scroll ownership here also makes nested confirmations restore it correctly.
const openDialogs = [];
let previousOverflow = "";
const focusable = 'a[href],button,input:not([type="hidden"]),select,textarea,[tabindex]';
export default function Modal({
  isOpen,
  onClose,
  overlayClassName,
  contentClassName,
  closeOnOverlayClick = true,
  closeOnEsc = true,
  ariaLabel,
  ariaLabelledBy,
  ariaDescribedBy,
  children,
}) {
  const dialogRef = useRef(null);
  const callbacks = useRef({ onClose, closeOnEsc });
  callbacks.current = { onClose, closeOnEsc };
  const portalTarget = document.fullscreenElement && document.fullscreenElement !== document.documentElement
    ? document.fullscreenElement : document.body;

  useEffect(() => {
    if (!isOpen) return undefined;
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement;
    if (!openDialogs.length) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    openDialogs.push(dialog);
    dialog.focus();
    const isTop = () => openDialogs.at(-1) === dialog;
    const onKeyDown = (event) => {
      if (!isTop()) return;
      if (event.key === "Escape" && callbacks.current.closeOnEsc) {
        event.preventDefault(); event.stopPropagation(); callbacks.current.onClose?.();
      }
      if (event.key !== "Tab") return;
      const controls = [...dialog.querySelectorAll(focusable)].filter(element =>
        !element.disabled && element.tabIndex >= 0 && !element.closest('[hidden],[inert]') &&
        getComputedStyle(element).display !== "none" && getComputedStyle(element).visibility !== "hidden");
      const first = controls[0], last = controls.at(-1);
      if (!controls.length) { event.preventDefault(); dialog.focus(); }
      else if (event.shiftKey && [first, dialog].includes(document.activeElement)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && [last, dialog].includes(document.activeElement)) { event.preventDefault(); first.focus(); }
    };
    const keepFocus = event => { if (isTop() && !dialog.contains(event.target)) dialog.focus(); };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("focusin", keepFocus);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("focusin", keepFocus);
      const wasTop = isTop();
      openDialogs.splice(openDialogs.indexOf(dialog), 1);
      if (!openDialogs.length) document.body.style.overflow = previousOverflow;
      if (wasTop && previousFocus?.isConnected) previousFocus.focus();
    };
  }, [isOpen, portalTarget]);

  if (!isOpen) return null;

  return createPortal(
    <div
      className={overlayClassName || styles.overlay}
      onClick={event => { if (event.target === event.currentTarget && closeOnOverlayClick) onClose?.(); }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel || (!ariaLabelledBy ? "Dialog" : undefined)}
        aria-labelledby={ariaLabelledBy}
        aria-describedby={ariaDescribedBy}
        tabIndex={-1}
        className={contentClassName || styles.content}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>, portalTarget
  );
}

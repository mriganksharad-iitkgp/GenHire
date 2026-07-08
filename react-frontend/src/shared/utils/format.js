// Canonical date/number/currency formatting.
//
// The codebase had 104 inline toLocaleDateString/toLocaleString/currency
// occurrences across 32 files; new and migrated code formats through these
// helpers instead. Defaults match the most common inline usages so migrated
// call sites render identically.

/** "12 Mar 2026" style; returns "" for missing/invalid dates. */
export function formatDate(value, options) {
  const date = toDate(value);
  if (!date) return "";
  return date.toLocaleDateString(
    undefined,
    options || { year: "numeric", month: "short", day: "numeric" }
  );
}

/** Date + time, e.g. "12 Mar 2026, 4:05 PM"; "" when missing/invalid. */
export function formatDateTime(value, options) {
  const date = toDate(value);
  if (!date) return "";
  return date.toLocaleString(
    undefined,
    options || {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }
  );
}

/** INR currency by default (the app's billing currency). */
export function formatCurrency(amount, { currency = "INR", locale = "en-IN", maximumFractionDigits = 2 } = {}) {
  const numeric = Number(amount);
  if (!Number.isFinite(numeric)) return "";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    maximumFractionDigits,
  }).format(numeric);
}

/** Thousands-separated plain number; "" for non-numeric input. */
export function formatNumber(value, options) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  return new Intl.NumberFormat(undefined, options).format(numeric);
}

function toDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

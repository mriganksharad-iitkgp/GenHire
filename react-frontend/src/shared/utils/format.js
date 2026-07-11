// Canonical date/number/currency formatting.
//
// All dates on the site render in Indian time (Asia/Kolkata) using the
// dd/mm/yyyy convention (en-IN locale) — owner requirement. New and migrated
// code formats through these helpers instead of inline toLocale* calls.

export const IST_TIME_ZONE = "Asia/Kolkata";
const IST_LOCALE = "en-IN";

/** "12/03/2026" (dd/mm/yyyy, IST); returns "" for missing/invalid dates. */
export function formatDate(value, options) {
  const date = toDate(value);
  if (!date) return "";
  return date.toLocaleDateString(IST_LOCALE, {
    timeZone: IST_TIME_ZONE,
    ...(options || {}),
  });
}

/** Date + time, e.g. "12/03/2026, 4:05 pm" (IST); "" when missing/invalid. */
export function formatDateTime(value, options) {
  const date = toDate(value);
  if (!date) return "";
  return date.toLocaleString(IST_LOCALE, {
    timeZone: IST_TIME_ZONE,
    ...(options || {
      hour: "numeric",
      minute: "2-digit",
    }),
  });
}

/** A Date whose local components mirror the current wall-clock in Kolkata —
 * use for "today"/"start of month" calculations so date pickers and default
 * ranges follow IST regardless of the viewer's machine timezone. */
export function nowInIST() {
  return new Date(
    new Date().toLocaleString("en-US", { timeZone: IST_TIME_ZONE })
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
  return new Intl.NumberFormat(IST_LOCALE, options).format(numeric);
}

function toDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

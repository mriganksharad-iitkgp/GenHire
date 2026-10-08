// Respect server backpressure without automatically replaying writes.
export function retryAfterSeconds(response, data = {}, now = Date.now()) {
  const header = response.headers?.get("Retry-After");
  const seconds = header && !Number.isNaN(Number(header))
    ? Number(header)
    : header ? (Date.parse(header) - now) / 1000 : Number(data?.retry_after || 0);
  return Number.isFinite(seconds) ? Math.max(0, Math.min(86400, Math.ceil(seconds))) : 0;
}

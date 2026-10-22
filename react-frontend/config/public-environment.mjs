// Every admitted value is embedded in the browser bundle. Keep this allowlist
// explicit: a new public setting needs review, never a renamed server secret.
export const PUBLIC_KEYS = new Set([
  'REACT_APP_API_URL', 'REACT_APP_API_BASE', 'REACT_APP_FRONTEND_URL',
  'REACT_APP_GOOGLE_CLIENT_ID', 'REACT_APP_TOKEN_KEY', 'REACT_APP_USER_KEY',
  'REACT_APP_KIOSK_DOWNLOAD_URL', 'REACT_APP_KIOSK_MAC_DOWNLOAD_URL',
]);

// Vercel injects framework-prefixed build metadata for Vite (and CRA).
// The platform can add metadata without notice, so match the reserved
// prefixes rather than maintaining a failure-prone list of individual names.
// https://vercel.com/docs/environment-variables/framework-environment-variables
const VERCEL_METADATA_PREFIXES = ['VITE_VERCEL_', 'REACT_APP_VERCEL_'];
export function isBuildMetadataKey(key) {
  return VERCEL_METADATA_PREFIXES.some(prefix => key.startsWith(prefix));
}

export function publicEnvironment(values, mode) {
  const exposed = { NODE_ENV: mode };
  for (const key of Object.keys(values)) {
    if (isBuildMetadataKey(key)) continue;
    if (!PUBLIC_KEYS.has(key)) {
      throw new Error(`Unapproved public environment key: ${key}. Keep server credentials in the backend; see docs/oa_owner_setup_guide.md.`);
    }
    exposed[key] = values[key];
  }
  return exposed;
}

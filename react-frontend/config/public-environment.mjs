// Every admitted value is embedded in the browser bundle. Keep this allowlist
// explicit: a new public setting needs review, never a renamed server secret.
export const PUBLIC_KEYS = new Set([
  'REACT_APP_API_URL', 'REACT_APP_API_BASE', 'REACT_APP_FRONTEND_URL',
  'REACT_APP_GOOGLE_CLIENT_ID', 'REACT_APP_TOKEN_KEY', 'REACT_APP_USER_KEY',
  'REACT_APP_KIOSK_DOWNLOAD_URL', 'REACT_APP_KIOSK_MAC_DOWNLOAD_URL',
]);

export function publicEnvironment(values, mode) {
  for (const key of Object.keys(values)) {
    if (!PUBLIC_KEYS.has(key)) {
      throw new Error(`Unapproved public environment key: ${key}. Keep server credentials in the backend; see docs/oa_owner_setup_guide.md.`);
    }
  }
  return { NODE_ENV: mode, ...values };
}

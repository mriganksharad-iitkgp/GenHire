// Every admitted value is embedded in the browser bundle. Keep this allowlist
// explicit: a new public setting needs review, never a renamed server secret.
export const PUBLIC_KEYS = new Set([
  'REACT_APP_API_URL', 'REACT_APP_API_BASE', 'REACT_APP_FRONTEND_URL',
  'REACT_APP_GOOGLE_CLIENT_ID', 'REACT_APP_TOKEN_KEY', 'REACT_APP_USER_KEY',
  'REACT_APP_KIOSK_DOWNLOAD_URL', 'REACT_APP_KIOSK_MAC_DOWNLOAD_URL',
]);

// Vercel injects framework-prefixed build metadata for Vite (and CRA).
// It is not application configuration: tolerate these exact documented names
// but discard them, including commit messages, rather than shipping them.
// https://vercel.com/docs/environment-variables/framework-environment-variables
const VERCEL_METADATA = [
  'ENV', 'TARGET_ENV', 'URL', 'BRANCH_URL', 'PROJECT_PRODUCTION_URL', 'HASH_SALT',
  'GIT_PROVIDER', 'GIT_REPO_SLUG', 'GIT_REPO_OWNER', 'GIT_REPO_ID',
  'GIT_COMMIT_REF', 'GIT_COMMIT_SHA', 'GIT_COMMIT_MESSAGE',
  'GIT_COMMIT_AUTHOR_LOGIN', 'GIT_COMMIT_AUTHOR_NAME', 'GIT_PULL_REQUEST_ID',
  'OBSERVABILITY_CLIENT_CONFIG',
];
export const BUILD_METADATA_KEYS = new Set(
  ['VITE_VERCEL_', 'REACT_APP_VERCEL_'].flatMap(prefix => VERCEL_METADATA.map(name => prefix + name)),
);

export function publicEnvironment(values, mode) {
  const exposed = { NODE_ENV: mode };
  for (const key of Object.keys(values)) {
    if (BUILD_METADATA_KEYS.has(key)) continue;
    if (!PUBLIC_KEYS.has(key)) {
      throw new Error(`Unapproved public environment key: ${key}. Keep server credentials in the backend; see docs/oa_owner_setup_guide.md.`);
    }
    exposed[key] = values[key];
  }
  return exposed;
}

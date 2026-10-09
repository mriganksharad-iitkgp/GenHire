// Builds the environment the E2E backend runs with, and refuses to start if
// anything could reach a real shared resource.
//
// Why this exists: python-backend ALWAYS loads python-backend/.env (with
// override=False), which on a dev machine points at the Atlas dev cluster, a
// live Razorpay key and a real email provider. Process env wins over .env, so
// we (1) blank every secret-looking key found in .env, (2) set explicit local
// values, and (3) pass through ONLY the LLM keys, and only when asked.
import fs from 'node:fs';
import path from 'node:path';

// Mirrors POLICIES in python-backend/middleware/rate_limiter.py.
const RATE_LIMIT_POLICIES = [
  'auth', 'account', 'login', 'register', 'email', 'invite_redeem', 'application',
  'application_hour', 'ai', 'upload', 'invite_send', 'interview_start',
  'interview_answer', 'interview_setup', 'telemetry', 'speech', 'speech_token',
  'payment', 'socket_connect', 'socket_control', 'socket_frame', 'socket_status',
  'export', 'read', 'write',
];

const DEAD_END = 'http://127.0.0.1:9';   // nothing listens on the discard port

export const PORTS = { mongo: 27117, gcs: 4443, api: 5100, web: 3100 };

const SECRET_LIKE = /KEY|SECRET|TOKEN|URI|PASSWORD|DSN|URL|CREDENTIALS|ZEPTO|MAILGUN|RAZORPAY|REDIS/;
// The only values copied from the maintainer's .env into the test backend.
const LLM_PASSTHROUGH = [
  'OPENAI_API_KEY', 'GOOGLE_API_KEY', 'GROQ_API_KEY', 'DEEPSEEK_API_KEY',
  'DEEPSEEK_API_BASE',
];

export function parseEnvFile(file) {
  const out = {};
  if (!fs.existsSync(file)) return out;
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/);
    if (!m) continue;
    out[m[1]] = m[2].replace(/\s+#.*$/, '').replace(/^['"]|['"]$/g, '');
  }
  return out;
}

export function buildBackendEnv({ backendDir, saKeyPath, withAi }) {
  const dotenv = parseEnvFile(path.join(backendDir, '.env'));
  const env = {};

  // 1. Neutralise everything secret-looking that .env would otherwise inject.
  for (const key of Object.keys(dotenv)) if (SECRET_LIKE.test(key)) env[key] = '';

  // 2. LLM keys: real ones in the @ai run. Otherwise a dummy value — the
  //    backend refuses to boot with no key at all, and a dummy simply makes any
  //    provider call fail with 401 (no spend) instead of silently using real keys.
  for (const key of LLM_PASSTHROUGH) {
    if (key.endsWith('_BASE')) { env[key] = withAi && dotenv[key] ? dotenv[key] : ''; continue; }
    env[key] = withAi && dotenv[key] ? dotenv[key] : 'e2e-dummy-key-not-a-real-key';
  }
  if (withAi) {
    for (const key of Object.keys(dotenv)) {
      if (/^(LLM_|FACE_MATCH_|CV_|GROQ_CV_|OPENAI_(CV_)?MODEL|INTERVIEW_LLM_MODEL)/.test(key) && !SECRET_LIKE.test(key)) {
        env[key] = dotenv[key];
      }
    }
  }

  // Without --ai, any LLM call must fail instantly instead of reaching a real
  // provider: point the OpenAI-compatible endpoints at a closed loopback port.
  if (!withAi) Object.assign(env, { OPENAI_BASE_URL: DEAD_END + '/v1', GROQ_BASE_URL: DEAD_END, DEEPSEEK_API_BASE: DEAD_END });

  // 3. Explicit local configuration.
  Object.assign(env, {
    PORT: String(PORTS.api),
    FLASK_ENV: 'development',
    FLASK_SECRET_KEY: 'e2e-flask-secret',
    JWT_SECRET_KEY: 'e2e-jwt-secret-e2e-jwt-secret-e2e',
    INVITE_TOKEN_SECRET: 'e2e-invite-secret',
    MONGODB_URI: `mongodb://127.0.0.1:${PORTS.mongo}`,
    DATABASE_NAME: 'genhire_e2e',
    EMAIL_PROVIDER: 'noop',
    REQUIRE_EMAIL_VERIFICATION: 'false',
    FRONTEND_URL: `http://localhost:${PORTS.web}`,
    CORS_ORIGINS: `http://localhost:${PORTS.web},http://127.0.0.1:${PORTS.web}`,
    FORCE_HTTPS: 'false',
    GCS_BUCKET_NAME: 'e2e-bucket',
    GOOGLE_APPLICATION_CREDENTIALS: saKeyPath,
    STORAGE_EMULATOR_HOST: `http://127.0.0.1:${PORTS.gcs}`,
    // Keep dev-machine shortcuts from .env out of the picture.
    SKIP_GCS_CHECK: '', SKIP_WALLET_BOOTSTRAP: '', GCS_LOCAL_DIR: '',
    // The identity-card step is covered by one dedicated spec; everything else
    // runs with face matching off so it does not need the ML models.
    FACE_VERIFICATION_MODE: 'off',
    // No telemetry leaves the machine; a stalled outbound call would also block the
    // single-process backend (it caused slow socket joins in early runs).
    LANGCHAIN_TRACING_V2: 'false', LANGCHAIN_TRACING: 'false', LANGSMITH_TRACING: 'false',
    LANGCHAIN_ENDPOINT: DEAD_END, LANGSMITH_ENDPOINT: DEAD_END,
    // Generous limits so a fast test run is not throttled; the rate-limit spec
    // exercises the real defaults against a separate policy-specific check.
    RATE_LIMIT_NAMESPACE: 'e2e',
    // Lets a test give itself a private rate-limit bucket via X-Forwarded-For
    // (the backend is only reachable on loopback here).
    TRUSTED_PROXY_HOPS: '1',
    PYTHONUNBUFFERED: '1',
  });
  // Default budgets are tight (e.g. 5 registrations / 5 min), so raise every
  // policy — except `invite_redeem`, which stays at its real default so one
  // spec can assert that throttling (429) really happens.
  for (const policy of RATE_LIMIT_POLICIES) {
    if (policy !== 'invite_redeem') env[`RATE_LIMIT_${policy.toUpperCase()}_CALLS`] = '100000';
  }
  env.RATE_LIMIT_NETWORK_CALLS = '100000';
  return env;
}

// Last line of defence: runs before any process is launched.
export function assertSafe(env) {
  const problems = [];
  if (!/^mongodb:\/\/(127\.0\.0\.1|localhost)[:/]/.test(env.MONGODB_URI || '')) problems.push(`MONGODB_URI is not local: ${env.MONGODB_URI}`);
  if (env.EMAIL_PROVIDER !== 'noop') problems.push('EMAIL_PROVIDER must be noop');
  for (const k of ['RAZORPAY_KEY_ID', 'RAZORPAY_KEY_SECRET', 'ZEPTOMAIL_API_KEY', 'MAILGUN_API_KEY', 'REDIS_URL', 'SENTRY_DSN']) {
    if (env[k]) problems.push(`${k} must be blank in the test backend`);
  }
  if (!/^http:\/\/127\.0\.0\.1:/.test(env.STORAGE_EMULATOR_HOST || '')) problems.push('STORAGE_EMULATOR_HOST must be the local fake GCS');
  if (problems.length) {
    throw new Error('E2E safety check failed — refusing to start:\n  - ' + problems.join('\n  - '));
  }
}

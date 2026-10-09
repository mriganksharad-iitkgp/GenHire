// Starts and stops the throw-away stack: in-memory MongoDB, fake GCS, the
// (unmodified) Flask backend and the Vite dev server.
import { spawn, spawnSync } from 'node:child_process';
import { generateKeyPairSync } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { MongoMemoryServer } from 'mongodb-memory-server';
import { startFakeGcs } from './fake-gcs.mjs';
import { PORTS, buildBackendEnv, assertSafe } from './safety.mjs';

export const ADMIN = { email: 'admin@e2e.test', password: 'Admin#12345' };

async function waitFor(url, label, ms = 120000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try { if ((await fetch(url)).ok) return; } catch { /* not up yet */ }
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error(`${label} did not become ready at ${url} within ${ms / 1000}s`);
}

// A syntactically valid service-account key that is never used for real auth:
// its token_uri points at the fake GCS, so no request ever leaves the machine.
function writeFakeServiceAccount(dir) {
  const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const file = path.join(dir, 'fake-service-account.json');
  fs.writeFileSync(file, JSON.stringify({
    type: 'service_account', project_id: 'e2e-fake', private_key_id: 'e2e',
    private_key: privateKey.export({ type: 'pkcs8', format: 'pem' }),
    client_email: 'e2e@e2e-fake.iam.gserviceaccount.com', client_id: '1',
    token_uri: `http://127.0.0.1:${PORTS.gcs}/token`,
  }));
  return file;
}

function pipeLogs(child, name, logFile) {
  const out = fs.createWriteStream(logFile, { flags: 'a' });
  child.stdout?.pipe(out); child.stderr?.pipe(out);
  child.on('exit', code => out.write(`\n[${name} exited with code ${code}]\n`));
}

export async function startStack({ rootDir, withAi, log }) {
  const backendDir = path.resolve(rootDir, '../python-backend');
  const python = ['venv/bin/python', 'venv/Scripts/python.exe'].map(p => path.join(backendDir, p)).find(fs.existsSync);
  if (!python) throw new Error(`Backend virtualenv not found in ${backendDir}/venv — create it first (see python-backend README).`);

  const workDir = fs.mkdtempSync(path.join(os.tmpdir(), 'genhire-e2e-'));
  const logsDir = path.join(process.env.E2E_OUT_DIR, 'logs');
  fs.mkdirSync(logsDir, { recursive: true });
  const procs = []; const closers = [];

  const stop = async () => {
    for (const p of procs) { try { p.kill('SIGTERM'); } catch { /* already gone */ } }
    await new Promise(r => setTimeout(r, 800));
    for (const p of procs) { try { p.kill('SIGKILL'); } catch { /* already gone */ } }
    for (const c of closers) { try { await c(); } catch { /* best effort */ } }
    fs.rmSync(workDir, { recursive: true, force: true });
  };

  try {
    log('starting in-memory MongoDB (first run downloads the binary)…');
    const mongo = await MongoMemoryServer.create({ instance: { port: PORTS.mongo, ip: '127.0.0.1' } });
    closers.push(() => mongo.stop());
    const mongoUri = `mongodb://127.0.0.1:${PORTS.mongo}`;

    log('starting fake Google Cloud Storage…');
    const gcs = await startFakeGcs(PORTS.gcs);
    closers.push(() => gcs.close());

    const backendEnv = buildBackendEnv({ backendDir, saKeyPath: writeFakeServiceAccount(workDir), withAi });
    assertSafe(backendEnv);

    log('starting backend (python-backend, unmodified)…');
    const api = spawn(python, ['app.py'], { cwd: backendDir, env: { ...process.env, ...backendEnv } });
    pipeLogs(api, 'backend', path.join(logsDir, 'backend.log')); procs.push(api);
    await waitFor(`http://127.0.0.1:${PORTS.api}/health`, 'backend');

    log('seeding admin account…');
    const seed = spawnSync(python, [path.join(rootDir, 'e2e/harness/seed_admin.py'), mongoUri, backendEnv.DATABASE_NAME, ADMIN.email, ADMIN.password], { encoding: 'utf8' });
    if (seed.status !== 0) throw new Error(`admin seed failed:\n${seed.stderr || seed.stdout}`);

    log('starting frontend (Vite)…');
    const web = spawn('npx', ['vite', '--port', String(PORTS.web), '--strictPort', '--host', '127.0.0.1'], {
      cwd: rootDir,
      env: { ...process.env, REACT_APP_API_URL: `http://127.0.0.1:${PORTS.api}`, REACT_APP_API_BASE: `http://127.0.0.1:${PORTS.api}/api` },
    });
    pipeLogs(web, 'frontend', path.join(logsDir, 'frontend.log')); procs.push(web);
    await waitFor(`http://127.0.0.1:${PORTS.web}/`, 'frontend');

    return {
      stop,
      env: {
        E2E_API_URL: `http://127.0.0.1:${PORTS.api}`,
        E2E_WEB_URL: `http://127.0.0.1:${PORTS.web}`,
        E2E_MONGO_URI: mongoUri,
        E2E_DB_NAME: backendEnv.DATABASE_NAME,
        E2E_GCS_URL: `http://127.0.0.1:${PORTS.gcs}`,
        E2E_ADMIN_EMAIL: ADMIN.email,
        E2E_ADMIN_PASSWORD: ADMIN.password,
        E2E_INVITE_SECRET: backendEnv.INVITE_TOKEN_SECRET,
        E2E_AI: withAi ? '1' : '0',
        E2E_RUN_ID: Date.now().toString(36),
      },
    };
  } catch (err) {
    await stop();
    throw err;
  }
}

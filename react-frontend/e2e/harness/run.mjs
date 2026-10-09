#!/usr/bin/env node
// One-command entry point:  npm run test:e2e [-- <playwright args>]
//   --ai     also run the @ai specs (real LLM / speech providers, costs money)
//   --ui     open Playwright's interactive UI instead of the headless run
//   --keep   leave the stack running after the tests (for debugging)
//   --stack-only  start the stack, write its env to $E2E_OUT_DIR/stack.env and wait
//                 (then, from react-frontend/e2e:  set -a; . <out dir>/stack.env; set +a; npx playwright test)
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { PORTS } from './safety.mjs';

const e2eDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const rootDir = path.resolve(e2eDir, '..');          // react-frontend
const args = process.argv.slice(2);
const flag = f => { const i = args.indexOf(f); if (i >= 0) args.splice(i, 1); return i >= 0; };
const stackOnly = flag('--stack-only'); const withAi = flag('--ai'); const ui = flag('--ui'); const keep = flag('--keep');
const log = m => console.log(`  • ${m}`);

// Test output (reports, traces, logs, generated fixtures) must live OUTSIDE the
// project: Vite watches the project directory and force-reloads the page under
// test whenever a file such as a trace .html appears inside it.
const outDir = process.env.E2E_OUT_DIR || path.join(os.tmpdir(), 'genhire-e2e-results');
fs.mkdirSync(outDir, { recursive: true });
process.env.E2E_OUT_DIR = outDir;

function portFree(port) {
  return new Promise(res => {
    const s = net.createServer().once('error', () => res(false)).once('listening', () => s.close(() => res(true)));
    s.listen(port, '127.0.0.1');
  });
}

async function doctor() {
  const problems = [];
  const [major] = process.versions.node.split('.').map(Number);
  if (major < 18) problems.push(`Node 18+ required (found ${process.version}).`);
  const backend = path.resolve(rootDir, '../python-backend');
  if (!['venv/bin/python', 'venv/Scripts/python.exe'].some(p => fs.existsSync(path.join(backend, p)))) {
    problems.push('python-backend/venv is missing. Create it:  cd python-backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt');
  }
  for (const [name, port] of Object.entries(PORTS)) {
    if (!(await portFree(port))) problems.push(`Port ${port} (${name}) is in use — stop whatever is using it (the E2E stack uses its own ports, separate from the normal dev ports 3000/5000).`);
  }
  // The test tooling has its own package.json (see e2e/package.json for why) and is
  // installed on first use.
  if (!fs.existsSync(path.join(e2eDir, 'node_modules'))) {
    log('installing E2E dependencies (one-time)…');
    const install = spawnSync('npm', ['install', '--prefix', e2eDir], { stdio: 'inherit' });
    if (install.status !== 0) problems.push('npm install in react-frontend/e2e failed.');
  }
  if (!fs.existsSync(path.join(rootDir, 'node_modules', 'vite'))) {
    problems.push('Frontend dependencies are missing. Run:  cd react-frontend && npm install');
  }
  // No-op when Chromium is already installed; downloads it on the first run.
  spawnSync('npx', ['playwright', 'install', 'chromium'], { cwd: e2eDir, stdio: 'inherit' });
  return problems;
}

// Non-blocking: tell the maintainer when their backend venv lags behind
// requirements.txt (a missing package makes some flows fail in confusing ways —
// e.g. without opencv-python-headless the face-capture step returns 503).
function venvWarnings() {
  const backend = path.resolve(rootDir, '../python-backend');
  const py = ['venv/bin/python', 'venv/Scripts/python.exe'].map(p => path.join(backend, p)).find(fs.existsSync);
  const req = path.join(backend, 'requirements.txt');
  if (!py || !fs.existsSync(req)) return [];
  const norm = n => n.toLowerCase().replace(/[-_.]+/g, '-');
  const installed = new Set(spawnSync(py, ['-m', 'pip', 'list', '--format=freeze'], { encoding: 'utf8' }).stdout.split('\n').map(l => norm(l.split('==')[0])));
  const wanted = fs.readFileSync(req, 'utf8').split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#') && !l.startsWith('-')).map(l => norm(l.split(/[=<>~![; ]/)[0]));
  const missing = wanted.filter(n => n && !installed.has(n));
  return missing.length ? [`python-backend/venv is missing ${missing.length} package(s) from requirements.txt: ${missing.slice(0, 6).join(', ')}${missing.length > 6 ? ', …' : ''}\n      Fix:  cd python-backend && venv/bin/pip install -r requirements.txt   (some flows, e.g. face capture, need them)`] : [];
}

console.log(`
GenHire E2E — everything runs on this machine:
  · database   throw-away in-memory MongoDB (your Atlas dev cluster is NOT used)
  · storage    local fake Google Cloud Storage
  · email      disabled (noop)      · payments   not configured (skipped)
  · backend    python-backend exactly as in the repo, own ports ${PORTS.api}/${PORTS.web}
  · AI         ${withAi ? 'REAL LLM/speech providers (--ai): this spends API credits' : 'off — pass --ai to include the @ai specs'}
`);

const problems = await doctor();
for (const w of venvWarnings()) console.log(`  ! ${w}\n`);
if (problems.length) {
  console.error('Cannot start:\n' + problems.map(p => `  ✗ ${p}`).join('\n'));
  process.exit(2);
}

// stack.mjs needs the E2E dependencies, which doctor() may just have installed.
const { startStack } = await import('./stack.mjs');

let stack;
const shutdown = async () => { if (stack && !keep) await stack.stop(); };
for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.on(sig, async () => { await shutdown(); process.exit(130); });
}

try {
  stack = await startStack({ rootDir, withAi, log });
} catch (err) {
  console.error(`\nStack failed to start: ${err.message}\nLogs: ${path.join(outDir, 'logs')}`);
  process.exit(3);
}

if (stackOnly) {
  const file = path.join(outDir, 'stack.env');
  fs.writeFileSync(file, Object.entries(stack.env).map(([k, v]) => `${k}=${v}`).join('\n') + '\n');
  console.log(`\nStack is up. Env written to ${file}. Press Ctrl+C to stop.`);
  await new Promise(() => {});
}
log('stack is up — running tests\n');
const pwArgs = ['playwright', 'test', ...(ui ? ['--ui'] : []), ...(withAi ? [] : ['--grep-invert', '@ai']), ...args];
const child = spawn('npx', pwArgs, { cwd: e2eDir, stdio: 'inherit', env: { ...process.env, ...stack.env } });
const code = await new Promise(r => child.on('exit', c => r(c ?? 1)));
console.log(`\nResults, traces and logs: ${outDir}\nOpen the HTML report with:  npx playwright show-report ${path.join(outDir, 'report')}`);
if (keep) console.log(`\nStack left running (--keep). API ${stack.env.E2E_API_URL}  Web ${stack.env.E2E_WEB_URL}`);
else await shutdown();
process.exit(code);

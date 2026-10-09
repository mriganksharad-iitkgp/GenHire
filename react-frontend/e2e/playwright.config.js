// Playwright config for the E2E suite. Do not run `playwright test` directly:
// use `npm run test:e2e` (from react-frontend), which first starts the isolated local stack and
// exports the E2E_* variables read below. See e2e/README.md.
import os from 'node:os';
import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

// Outside the project on purpose — see the comment in e2e/harness/run.mjs.
const OUT = process.env.E2E_OUT_DIR || path.join(os.tmpdir(), 'genhire-e2e-results');

export default defineConfig({
  testDir: './specs',
  globalSetup: './harness/global-setup.mjs',
  outputDir: path.join(OUT, 'artifacts'),
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: 3,
  retries: 0, // locally we want flakes to be visible, not hidden
  reporter: [['list'], ['html', { outputFolder: path.join(OUT, 'report'), open: 'never' }]],
  use: {
    baseURL: process.env.E2E_WEB_URL || 'http://127.0.0.1:3100',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      // Fake webcam/mic so media prompts are auto-granted and need no hardware.
      args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
    },
    permissions: ['camera', 'microphone'],
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});

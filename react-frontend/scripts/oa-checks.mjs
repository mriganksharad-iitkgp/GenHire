// One portable entry point used locally and in CI. No live HTTP/provider calls.
import { spawnSync } from 'node:child_process';
const suites = ['test:public-env', 'test', 'test:question-editor', 'test:hiring-timing', 'test:landing', 'test:portals', 'test:interview-ui',
  'test:job-setup', 'test:assessment-authoring', 'test:hiring-progression', 'test:assessment-runtime',
  'test:assessment-evaluation', 'test:assessment-integrity', 'test:company-hiring', 'test:practice-assessment',
  'lint:ci', 'build', 'build:kiosk'];
for (const suite of suites) {
  console.log(`\nOA check: ${suite}`);
  // Windows npm is a .cmd shim, so execute the known npm CLI with Node directly.
  const cli = process.env.npm_execpath;
  if (!cli) throw new Error('Run this entry point using npm run check:oa.');
  const result = spawnSync(process.execPath, [cli, 'run', suite], { stdio: 'inherit', env: process.env });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}

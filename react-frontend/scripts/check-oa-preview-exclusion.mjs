// A local developer capability must never ship in either production frontend.
import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
async function check(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) await check(file);
    else if (entry.name.endsWith('.js')) {
      const source = await readFile(file, 'utf8');
      for (const marker of ['X-GenHire-Dev-Token', 'Local OA developer preview', '/dev/oa'])
        assert.ok(!source.includes(marker), `Developer preview leaked into production asset: ${file}`);
    }
  }
}
await check('build');
await check('../secure-browser-kiosk/web-app');
assert.match(await readFile('../python-backend/.dockerignore', 'utf8'), /^scripts\/dev\/$/m);
console.log('PASS developer preview route/client are absent from web and kiosk builds; backend harness is excluded from Docker.');

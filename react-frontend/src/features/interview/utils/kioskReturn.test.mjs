import assert from 'node:assert/strict';
import test from 'node:test';
import { returnFromKiosk } from './kioskReturn.js';

test('return preserves the launching tab without opening an unauthenticated duplicate', () => {
  const calls = [];
  const bridge = { disableKiosk: () => calls.push('unlock'), openExternal: url => calls.push(url), quitApp: () => calls.push('quit') };
  for (const path of ['/applications', '/practice']) {
    calls.length = 0;
    returnFromKiosk(bridge, { returnToExistingTab: true, webOrigin: 'https://genhire.in' }, path);
    assert.deepEqual(calls, ['unlock', 'quit']);
  }
  calls.length = 0;
  returnFromKiosk(bridge, { webOrigin: 'https://genhire.in' }, '/applications');
  assert.deepEqual(calls, ['unlock', 'https://genhire.in/applications', 'quit']);
});

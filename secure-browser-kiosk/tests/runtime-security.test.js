const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { resolvePublicFile, parseInitialization, validWebUrl } = require('../runtime-security');
test('only the bundled UI and hashed assets are public', () => {
  const root = path.resolve('kiosk');
  assert.equal(resolvePublicFile(root, '/'), path.join(root, 'web-app', 'index.html'));
  assert.equal(resolvePublicFile(root, '/assets/index-abc123.js?x=1'), path.join(root, 'web-app', 'assets', 'index-abc123.js'));
  assert.equal(resolvePublicFile(root, '/assets/editor.worker-abc123.js'), path.join(root, 'web-app', 'assets', 'editor.worker-abc123.js'));
  for (const name of ['vision_wasm_internal.wasm', 'blaze_face_short_range.tflite']) {
    assert.equal(resolvePublicFile(root, '/assets/' + name), path.join(root, 'web-app', 'assets', name));
  }
  for (const url of ['/main.js', '/preload.js', '/credentials.json', '/assets/../main.js', '/assets/%2e%2e/main.js', '/%zz', '/node_modules/socket.io-client/dist/socket.io.min.js']) assert.equal(resolvePublicFile(root, url), null, url);
});
test('launches require credentials and safe API/dashboard addresses', () => {
  const payload = { token: 'test-token', applicationId: 'application', apiUrl: 'https://api.example.com', webOrigin: 'https://app.example.com' };
  const encode = (p) => Buffer.from(JSON.stringify(p)).toString('base64');
  assert.deepEqual(parseInitialization(encode(payload)), payload);
  for (const apiUrl of ['http://public.example.com', 'file:///tmp', 'https://user:pass@example.com']) assert.throws(() => parseInitialization(encode({ ...payload, apiUrl })));
  assert.throws(() => parseInitialization(encode({ ...payload, webOrigin: '' })));
  assert.equal(validWebUrl('http://localhost:3000'), true);
});

test('OA launches carry a scoped one-time code and never an account token', () => {
  const payload = { mode: 'oa', launchCode: 'a'.repeat(43), invitationId: '123456789012345678901234', apiUrl: 'https://api.example.com', webOrigin: 'https://app.example.com' };
  const encode = value => Buffer.from(JSON.stringify(value)).toString('base64');
  assert.deepEqual(parseInitialization(encode(payload)), payload);
  for (const value of [{ ...payload, token: 'account-token' }, { ...payload, invitationId: '../other' }, { ...payload, launchCode: 'short' }]) assert.throws(() => parseInitialization(encode(value)));
  assert.throws(() => parseInitialization(Buffer.from('{"token":"PRIVATE_ACCOUNT_TOKEN').toString('base64')), error => !error.message.includes('PRIVATE_ACCOUNT_TOKEN'));
});

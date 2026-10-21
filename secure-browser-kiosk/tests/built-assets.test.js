// Run after the web+kiosk builds; check the actual bundled asset filenames.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { resolvePublicFile } = require('../runtime-security');

test('built kiosk serves runtime assets including the Monaco worker', () => {
  const root = path.resolve(__dirname, '..');
  const directory = path.join(root, 'web-app/assets');
  assert.ok(fs.existsSync(directory), 'Build react-frontend with build:kiosk first.');
  const assets = fs.readdirSync(directory).filter(name => /\.(js|css|svg|png|woff2?|wasm|tflite)$/.test(name));
  assert.ok(assets.some(name => /editor\.worker.*\.js$/.test(name)), 'Monaco worker must be packaged locally.');
  for (const name of assets) {
    assert.equal(resolvePublicFile(root, '/assets/'+name), path.join(directory, name));
  }
});

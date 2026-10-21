import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PUBLIC_KEYS, publicEnvironment } from './public-environment.mjs';

test('public API/OAuth/storage-name/download settings remain available', () => {
  const values = Object.fromEntries([...PUBLIC_KEYS].map(key => [key, 'public-fixture']));
  assert.deepEqual(publicEnvironment(values, 'production'), { NODE_ENV: 'production', ...values });
});

test('accidentally prefixed server secrets fail the build without printing values', () => {
  for (const key of ['REACT_APP_SPHERE_COMPILERS_TOKEN', 'REACT_APP_JWT_SECRET_KEY', 'VITE_API_KEY', 'REACT_APP_UNKNOWN']) {
    assert.throws(() => publicEnvironment({ [key]: 'private-fixture-never-log' }, 'production'), error => {
      assert.ok(error.message.includes(key));
      assert.equal(error.message.includes('private-fixture-never-log'), false);
      return true;
    });
  }
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isBuildMetadataKey, PUBLIC_KEYS, publicEnvironment } from './public-environment.mjs';

test('public API/OAuth/storage-name/download settings remain available', () => {
  const values = Object.fromEntries([...PUBLIC_KEYS].map(key => [key, 'public-fixture']));
  assert.deepEqual(publicEnvironment(values, 'production'), { NODE_ENV: 'production', ...values });
});

test('accidentally prefixed server secrets fail the build without printing values', () => {
  for (const key of ['REACT_APP_ONECOMPILER_API_KEY', 'REACT_APP_ONLINECOMPILER_API_KEY', 'REACT_APP_AIVEN_POSTGRES_URL', 'REACT_APP_JWT_SECRET_KEY', 'VITE_API_KEY', 'REACT_APP_UNKNOWN']) {
    assert.throws(() => publicEnvironment({ [key]: 'private-fixture-never-log' }, 'production'), error => {
      assert.ok(error.message.includes(key));
      assert.equal(error.message.includes('private-fixture-never-log'), false);
      return true;
    });
  }
});

test('documented Vercel Vite/CRA metadata does not fail builds or enter the public config', () => {
  const metadata = {
    VITE_VERCEL_GIT_REPO_ID: 'build-metadata-never-embed',
    VITE_VERCEL_GIT_PREVIOUS_SHA: 'build-metadata-never-embed',
    REACT_APP_VERCEL_OBSERVABILITY_CLIENT_CONFIG: 'build-metadata-never-embed',
    VITE_VERCEL_FUTURE_METADATA: 'build-metadata-never-embed',
  };
  assert.equal(isBuildMetadataKey('VITE_VERCEL_FUTURE_METADATA'), true);
  assert.equal(isBuildMetadataKey('REACT_APP_VERCEL_FUTURE_METADATA'), true);
  assert.equal(isBuildMetadataKey('VITE_NOT_VERCEL_METADATA'), false);
  const result = publicEnvironment({ ...metadata, REACT_APP_API_URL: 'https://api.example.test' }, 'production');
  assert.deepEqual(result, { NODE_ENV: 'production', REACT_APP_API_URL: 'https://api.example.test' });
  assert.equal(JSON.stringify(result).includes('build-metadata-never-embed'), false);
});

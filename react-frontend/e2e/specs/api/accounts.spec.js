// Account lifecycle: recruiter approval, password reset, email verification,
// account deletion. Email is disabled in the test stack, so tokens that would
// arrive by mail are read from the test database instead.
import { test, expect } from '@playwright/test';
import { call, login, createUser, adminToken, uniqueEmail, userId, PASSWORD } from '../../helpers/api.js';
import { db, userByEmail } from '../../helpers/db.js';

test('API-04 recruiter signup is pending until an admin verifies; reject works too', async () => {
  const pending = await createUser('recruiter', { verify: false });
  expect(pending.user.is_verified).toBe(false);

  const admin = await adminToken();
  const queue = await call('GET', '/admin/pending-recruiters', { token: admin, expect: 200 });
  expect(queue.data.pending_recruiters.map(r => r.email)).toContain(pending.email);

  await call('PUT', `/admin/users/${userId(pending)}/verify`, { token: admin, json: {}, expect: 200 });
  const relogin = await login({ email: pending.email, role: 'recruiter' });
  expect(relogin.data.user.is_verified).toBe(true);

  const toReject = await createUser('recruiter', { verify: false });
  const rejected = await call('PUT', `/admin/users/${userId(toReject)}/reject`, { token: admin, json: { reason: 'E2E rejection' } });
  expect(rejected.status).toBe(200);
  const after = await login({ email: toReject.email, role: 'recruiter' });
  expect(after.data?.user?.is_verified ?? false).toBe(false);
});

test('API-05a forgot + reset password: token from DB, old password stops working', async () => {
  const user = await createUser('candidate');
  expect((await call('POST', '/forgot-password', { json: { email: user.email } })).status).toBe(200);

  const stored = await userByEmail(user.email);
  expect(stored.reset_token).toBeTruthy();

  const bad = await call('POST', '/reset-password', { json: { token: 'not-a-token', password: 'Newpass#123', confirmPassword: 'Newpass#123' } });
  expect(bad.status).toBeGreaterThanOrEqual(400);
  const mismatch = await call('POST', '/reset-password', { json: { token: stored.reset_token, password: 'Newpass#123', confirmPassword: 'Different#1' } });
  expect(mismatch.status).toBe(400);

  const ok = await call('POST', '/reset-password', { json: { token: stored.reset_token, password: 'Newpass#123', confirmPassword: 'Newpass#123' } });
  expect(ok.status).toBe(200);
  expect((await login({ email: user.email })).status).toBe(401);
  expect((await login({ email: user.email, password: 'Newpass#123' })).status).toBe(200);

  // the token is single-use
  const reuse = await call('POST', '/reset-password', { json: { token: stored.reset_token, password: 'Another#123', confirmPassword: 'Another#123' } });
  expect(reuse.status).toBeGreaterThanOrEqual(400);
});

test('API-05b forgot-password does not reveal whether an email exists', async () => {
  const known = await createUser('candidate');
  const a = await call('POST', '/forgot-password', { json: { email: known.email } });
  const b = await call('POST', '/forgot-password', { json: { email: uniqueEmail('ghost') } });
  expect(b.status).toBe(a.status);
});

test('API-05c verify-email: valid token verifies, bad token is rejected', async () => {
  const user = await createUser('candidate');
  const token = `e2e-verify-${Math.random().toString(36).slice(2)}`; // unique: the DB outlives a single test
  const users = (await db()).collection('users');
  await users.updateOne({ email_lower: user.email }, { $set: { email_verified: false, verification_token: token } });
  expect((await call('POST', '/verify-email', { json: { token: 'wrong' } })).status).toBe(400);
  expect((await call('POST', '/verify-email', { json: {} })).status).toBe(400);
  expect((await call('POST', '/verify-email', { json: { token } })).status).toBe(200);
  expect((await userByEmail(user.email)).email_verified).toBe(true);
});

test('API-03b /me returns the profile; DELETE /me removes the account', async () => {
  const user = await createUser('candidate');
  const me = await call('GET', '/me', { token: user.token, expect: 200 });
  expect(JSON.stringify(me.data)).toContain(user.email);
  const del = await call('DELETE', '/me', { token: user.token, json: { password: PASSWORD } });
  expect([200, 204]).toContain(del.status);
  expect((await login({ email: user.email })).status).toBe(401);
});

test('API-03c a tampered or garbage token is rejected', async () => {
  const user = await createUser('candidate');
  expect((await call('GET', '/me', { token: user.token + 'x' })).status).toBe(401);
  expect((await call('GET', '/me', { token: 'garbage' })).status).toBe(401);
});

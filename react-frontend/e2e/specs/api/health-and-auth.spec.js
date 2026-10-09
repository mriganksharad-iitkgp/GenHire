import { test, expect } from '@playwright/test';
import { call, register, login, uniqueEmail, PASSWORD } from '../../helpers/api.js';

test('API-01 /health is healthy and backed by the local database', async () => {
  const res = await fetch(`${process.env.E2E_API_URL}/health`);
  expect(res.status).toBe(200);
  expect(await res.json()).toMatchObject({ status: 'healthy', database: 'connected' });
});

test('API-02 register candidate: success, duplicate, bad input', async () => {
  const email = uniqueEmail('cand');
  const ok = await register({ name: 'Api Cand', email });
  expect(ok.status).toBe(201);
  expect(ok.data.token).toBeTruthy();

  const dup = await register({ name: 'Api Cand', email });
  expect(dup.status).toBe(400);

  const otherRole = await register({ name: 'Api Cand', email, role: 'recruiter' });
  expect(otherRole.status).toBe(409);

  const weak = await call('POST', '/register', { json: { name: 'x y', email: uniqueEmail('w'), password: 'abc', confirmPassword: 'abc', userType: 'candidate' } });
  expect(weak.status).toBe(400);
  const bad = await call('POST', '/register', { json: { name: 'x y', email: 'not-an-email', password: PASSWORD, confirmPassword: PASSWORD, userType: 'candidate' } });
  expect(bad.status).toBe(400);
});

test('API-03 login: success, wrong password and wrong role give the same generic 401', async () => {
  const email = uniqueEmail('cand');
  await register({ name: 'Api Login', email });
  const ok = await login({ email });
  expect(ok.status).toBe(200);
  const me = await call('GET', '/me', { token: ok.data.token });
  expect(me.status).toBe(200);

  const wrongPw = await login({ email, password: 'Wrong#Pass1' });
  const wrongRole = await login({ email, role: 'recruiter' });
  expect(wrongPw.status).toBe(401);
  expect(wrongRole.status).toBe(401);
  expect(wrongRole.data.error).toBe(wrongPw.data.error);

  expect((await call('GET', '/me')).status).toBe(401);
});

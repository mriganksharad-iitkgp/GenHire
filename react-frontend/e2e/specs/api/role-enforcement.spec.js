import { test, expect } from '@playwright/test';
import { call, createUser, createJob, adminToken } from '../../helpers/api.js';

let candidate, recruiter, admin, job;
test.beforeAll(async () => {
  [candidate, recruiter] = await Promise.all([createUser('candidate'), createUser('recruiter')]);
  admin = await adminToken();
  job = await createJob(recruiter);
});

const ADMIN_ONLY = [
  ['GET', '/admin/stats'], ['GET', '/admin/users'], ['GET', '/admin/pending-recruiters'],
  ['GET', '/admin/jobs'], ['GET', '/admin/cost-statistics'], ['GET', '/admin/permissions'],
];

for (const [method, path] of ADMIN_ONLY) {
  test(`API-06 ${method} ${path} is admin-only`, async () => {
    expect([401, 403]).toContain((await call(method, path)).status);
    expect([401, 403]).toContain((await call(method, path, { token: candidate.token })).status);
    expect([401, 403]).toContain((await call(method, path, { token: recruiter.token })).status);
    expect((await call(method, path, { token: admin })).status).toBe(200);
  });
}

test('API-06 candidates cannot create jobs or manage invites', async () => {
  const create = await call('POST', '/jobs', { token: candidate.token, json: { title: 'x' } });
  expect([401, 403]).toContain(create.status);
  const invite = await call('POST', `/recruiter/jobs/${job._id}/invites`, { token: candidate.token, json: { emails: ['a@e2e.test'] } });
  expect([401, 403]).toContain(invite.status);
});

test('API-06 recruiters cannot apply to jobs or use candidate-only routes', async () => {
  const apply = await call('POST', `/jobs/${job._id}/apply`, { token: recruiter.token, json: {} });
  expect([400, 401, 403]).toContain(apply.status);
});

test('API-06 a recruiter cannot edit or delete another recruiter\'s job', async () => {
  const other = await createUser('recruiter');
  const edit = await call('PUT', `/jobs/${job._id}`, { token: other.token, json: { title: 'hijacked' } });
  expect([403, 404]).toContain(edit.status);
  const del = await call('DELETE', `/jobs/${job._id}`, { token: other.token });
  expect([403, 404]).toContain(del.status);
  const still = await call('GET', `/jobs/${job._id}`, { token: recruiter.token, expect: 200 });
  expect(JSON.stringify(still.data)).not.toContain('hijacked');
});

test('API-06 a candidate cannot read another candidate\'s application', async () => {
  const { saveCvDetails } = await import('../../helpers/api.js');
  const a = await createUser('candidate'); const b = await createUser('candidate');
  await saveCvDetails(a);
  const applied = await call('POST', `/jobs/${job._id}/apply`, { token: a.token, json: {}, expect: 201 });
  const peek = await call('GET', `/applications/${applied.data.application_id}`, { token: b.token });
  expect([403, 404]).toContain(peek.status);
});

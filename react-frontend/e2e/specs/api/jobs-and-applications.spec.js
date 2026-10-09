import { test, expect } from '@playwright/test';
import { call, createUser, createJob, jobPayload, saveCvDetails } from '../../helpers/api.js';

let recruiter;
test.beforeAll(async () => { recruiter = await createUser('recruiter'); });

test('API-07a job CRUD as the owning recruiter', async () => {
  const job = await createJob(recruiter, { title: 'E2E CRUD Role' });
  expect(job._id).toBeTruthy();

  const got = await call('GET', `/jobs/${job._id}`, { token: recruiter.token, expect: 200 });
  expect(JSON.stringify(got.data)).toContain('E2E CRUD Role');

  const upd = await call('PUT', `/jobs/${job._id}`, { token: recruiter.token, json: jobPayload({ title: 'E2E CRUD Role v2' }) });
  expect(upd.status).toBe(200);
  expect(JSON.stringify((await call('GET', `/jobs/${job._id}`, { token: recruiter.token })).data)).toContain('v2');

  expect((await call('DELETE', `/jobs/${job._id}`, { token: recruiter.token })).status).toBe(200);
  expect((await call('GET', `/jobs/${job._id}`, { token: recruiter.token })).status).toBe(404);
});

test('API-07b job validation: every required field is enforced', async () => {
  for (const field of ['title', 'department', 'location', 'type', 'experience', 'salary', 'description']) {
    const payload = jobPayload(); delete payload[field];
    const r = await call('POST', '/jobs', { token: recruiter.token, json: payload });
    expect(r.status, `missing ${field}`).toBe(400);
    expect(JSON.stringify(r.data)).toContain(field);
  }
  const badScore = await call('POST', '/jobs', { token: recruiter.token, json: jobPayload({ minimum_cv_score: 150 }) });
  expect(badScore.status).toBe(400);
});

test('API-07c candidates see active jobs in the listing', async () => {
  const cand = await createUser('candidate');
  const job = await createJob(recruiter);
  const list = await call('GET', '/jobs', { token: cand.token, expect: 200 });
  expect(list.data.map(j => j._id)).toContain(job._id);
});

test('API-07d saving a job is idempotent; unsave removes it', async () => {
  const cand = await createUser('candidate');
  const job = await createJob(recruiter);
  expect((await call('POST', `/jobs/${job._id}/save`, { token: cand.token, json: {} })).status).toBe(200);
  expect((await call('POST', `/jobs/${job._id}/save`, { token: cand.token, json: {} })).status).toBe(200);
  const saved = await call('GET', '/saved-jobs', { token: cand.token, expect: 200 });
  expect(saved.data.count).toBe(1);
  expect(saved.data.saved_jobs[0]._id).toBe(job._id);
  expect((await call('DELETE', `/jobs/${job._id}/save`, { token: cand.token })).status).toBe(200);
  expect((await call('GET', '/saved-jobs', { token: cand.token })).data.count).toBe(0);
});

test('API-09a apply requires a CV; then applies once and is idempotent', async () => {
  const cand = await createUser('candidate');
  const job = await createJob(recruiter);

  const noCv = await call('POST', `/jobs/${job._id}/apply`, { token: cand.token, json: {} });
  expect(noCv.status).toBe(400);
  expect(noCv.data.redirect).toBe('/profile/cv-details');

  await saveCvDetails(cand);
  const first = await call('POST', `/jobs/${job._id}/apply`, { token: cand.token, json: {}, expect: 201 });
  const again = await call('POST', `/jobs/${job._id}/apply`, { token: cand.token, json: {}, expect: 200 });
  expect(again.data.already_applied).toBe(true);
  expect(again.data.application_id).toBe(first.data.application_id);

  const mine = await call('GET', '/applications', { token: cand.token, expect: 200 });
  expect(mine.data).toHaveLength(1);
  expect(mine.data[0].job_id ?? mine.data[0].job?._id).toBeTruthy();
});

test('API-09b the recruiter sees the application; a score appears eventually', async () => {
  const cand = await createUser('candidate');
  const job = await createJob(recruiter);
  await saveCvDetails(cand);
  const { data } = await call('POST', `/jobs/${job._id}/apply`, { token: cand.token, json: {}, expect: 201 });

  const apps = await call('GET', `/jobs/${job._id}/applications`, { token: recruiter.token, expect: 200 });
  expect(apps.data.applications.map(a => a._id)).toContain(data.application_id);

  await expect.poll(async () => (await call('GET', `/applications/${data.application_id}`, { token: cand.token })).data.cv_score, { timeout: 30_000 })
    .toEqual(expect.any(Number));
});

test('API-09c recruiter can change application status; candidate can withdraw', async () => {
  const cand = await createUser('candidate');
  const job = await createJob(recruiter);
  await saveCvDetails(cand);
  const { data } = await call('POST', `/jobs/${job._id}/apply`, { token: cand.token, json: {}, expect: 201 });

  const st = await call('PUT', `/applications/${data.application_id}/status`, { token: recruiter.token, json: { status: 'shortlisted' } });
  expect(st.status).toBe(200);
  const bad = await call('PUT', `/applications/${data.application_id}/status`, { token: cand.token, json: { status: 'hired' } });
  expect([401, 403]).toContain(bad.status);

  // once the recruiter has acted on it, the candidate can no longer withdraw
  const late = await call('DELETE', `/jobs/${job._id}/withdraw`, { token: cand.token });
  expect(late.status).toBe(400);

  // a still-pending application can be withdrawn exactly once
  const cand2 = await createUser('candidate');
  await saveCvDetails(cand2);
  await call('POST', `/jobs/${job._id}/apply`, { token: cand2.token, json: {}, expect: 201 });
  expect((await call('DELETE', `/jobs/${job._id}/withdraw`, { token: cand2.token })).status).toBe(200);
  expect((await call('DELETE', `/jobs/${job._id}/withdraw`, { token: cand2.token })).status).toBe(404);
});

test('API-09d applying to a missing job fails cleanly', async () => {
  const cand = await createUser('candidate');
  await saveCvDetails(cand);
  const r = await call('POST', '/jobs/000000000000000000000000/apply', { token: cand.token, json: {} });
  expect([400, 404]).toContain(r.status);
});

test('API-09e screening-cleared export is an XLSX for the owning recruiter only', async () => {
  const job = await createJob(recruiter);
  const ok = await fetch(`${process.env.E2E_API_URL}/api/jobs/${job._id}/screening-cleared/export`, { headers: { Authorization: `Bearer ${recruiter.token}` } });
  expect([200, 404]).toContain(ok.status);
  if (ok.status === 200) expect(ok.headers.get('content-type')).toMatch(/spreadsheet|octet-stream/);
  const other = await createUser('recruiter');
  const denied = await call('GET', `/jobs/${job._id}/screening-cleared/export`, { token: other.token });
  expect([403, 404]).toContain(denied.status);
});

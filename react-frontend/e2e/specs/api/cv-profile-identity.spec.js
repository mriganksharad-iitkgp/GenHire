import { test, expect } from '@playwright/test';
import { call, createUser, uploadCv, uploadIdentityCard, adminToken, userId, cvDetails } from '../../helpers/api.js';

test('API-08a CV lifecycle: upload, list, text, preview, signed download, primary, delete', async () => {
  const cand = await createUser('candidate');
  const up = await uploadCv(cand);
  expect(up.status).toBe(201);
  const cvId = up.data.cv.cv_id;
  expect(up.data.cv.is_primary).toBe(true);

  const list = await call('GET', '/cv/list', { token: cand.token, expect: 200 });
  expect(list.data.count).toBe(1);
  expect(list.data.max_allowed).toBeGreaterThan(0);

  const text = await call('GET', `/cv/${cvId}/text`, { token: cand.token, expect: 200 });
  expect(JSON.stringify(text.data)).toContain('Jane Doe');

  // signed download URL points at the fake GCS and serves the original PDF
  const dl = await call('GET', `/cv/${cvId}/download-url`, { token: cand.token, expect: 200 });
  const file = await fetch(dl.data.download_url);
  expect(file.status).toBe(200);
  expect(Buffer.from(await file.arrayBuffer()).subarray(0, 4).toString()).toBe('%PDF');

  // second CV, then switch primary
  const second = await uploadCv(cand);
  const secondId = second.data.cv.cv_id;
  expect((await call('PUT', `/cv/${secondId}/set-primary`, { token: cand.token, json: {} })).status).toBe(200);
  const afterPrimary = (await call('GET', '/cv/list', { token: cand.token })).data.cvs;
  expect(afterPrimary.find(c => c.cv_id === secondId).is_primary).toBe(true);
  expect(afterPrimary.find(c => c.cv_id === cvId).is_primary).toBe(false);

  expect((await call('DELETE', `/cv/${cvId}`, { token: cand.token })).status).toBe(200);
  expect((await call('GET', '/cv/list', { token: cand.token })).data.count).toBe(1);
});

test('API-08b CV upload rejects non-PDF files and missing files', async () => {
  const cand = await createUser('candidate');
  const form = new FormData();
  form.append('cv_file', new Blob(['just text'], { type: 'text/plain' }), 'notes.txt');
  const wrong = await call('POST', '/cv/upload', { token: cand.token, form });
  expect(wrong.status).toBe(400);
  const none = await call('POST', '/cv/upload', { token: cand.token, form: new FormData() });
  expect(none.status).toBe(400);
});

test('API-08c one candidate cannot touch another\'s CV', async () => {
  const owner = await createUser('candidate'); const other = await createUser('candidate');
  const cvId = (await uploadCv(owner)).data.cv.cv_id;
  for (const [m, p] of [['GET', `/cv/${cvId}`], ['GET', `/cv/${cvId}/text`], ['DELETE', `/cv/${cvId}`]]) {
    const r = await call(m, p, { token: other.token });
    expect([403, 404], `${m} ${p}`).toContain(r.status);
  }
  expect((await call('GET', '/cv/list', { token: owner.token })).data.count).toBe(1);
});

test('API-08d profile and CV details round-trip', async () => {
  const cand = await createUser('candidate');
  const upd = await call('PUT', '/profile', { token: cand.token, json: { name: 'Renamed E2E', title: 'Engineer', location: 'Pune', phone: '9999999999', about: 'About me', skills: ['Python'] } });
  expect(upd.status).toBe(200);
  const prof = await call('GET', '/profile', { token: cand.token, expect: 200 });
  expect(prof.data).toMatchObject({ name: 'Renamed E2E', title: 'Engineer', location: 'Pune' });

  expect((await call('PUT', '/cv-details', { token: cand.token, json: cvDetails(), expect: 200 })).status).toBe(200);
  const details = await call('GET', '/cv-details', { token: cand.token, expect: 200 });
  expect(details.data.cv_details.skills.technical).toContain('Python');
});

test('API-08e recruiter company profile saves', async () => {
  const rec = await createUser('recruiter');
  const r = await call('PUT', '/company-profile', { token: rec.token, json: { company_name: 'E2E Corp', company_industry: 'Software', company_size: '11-50', company_website: 'https://example.com', company_location: 'Remote', company_description: 'We test things' } });
  expect(r.status).toBe(200);
  const prof = await call('GET', '/profile', { token: rec.token, expect: 200 });
  expect(JSON.stringify(prof.data)).toContain('E2E Corp');
});

test('API-14 identity card: upload locks it; only an admin can reset', async () => {
  const cand = await createUser('candidate');
  expect((await call('GET', '/identity-card', { token: cand.token, expect: 200 })).data.uploaded).toBe(false);

  const up = await uploadIdentityCard(cand);
  expect(up.status).toBe(201);
  expect(up.data.status.locked).toBe(true);

  const again = await uploadIdentityCard(cand);
  expect(again.status).toBeGreaterThanOrEqual(400);   // locked

  const img = await fetch(`${process.env.E2E_API_URL}/api/identity-card/image`, { headers: { Authorization: `Bearer ${cand.token}` } });
  expect(img.status).toBe(200);

  const admin = await adminToken();
  const view = await call('GET', `/admin/candidates/${userId(cand)}/identity-card`, { token: admin });
  expect(view.status).toBe(200);
  expect((await call('DELETE', `/admin/candidates/${userId(cand)}/identity-card`, { token: admin })).status).toBe(200);
  expect((await call('GET', '/identity-card', { token: cand.token })).data.uploaded).toBe(false);

  const denied = await call('DELETE', `/admin/candidates/${userId(cand)}/identity-card`, { token: cand.token });
  expect([401, 403]).toContain(denied.status);
});

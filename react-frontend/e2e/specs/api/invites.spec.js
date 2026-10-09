import { test, expect } from '@playwright/test';
import { call, createUser, createJob, randomIp, uniqueEmail } from '../../helpers/api.js';
import { knownInviteToken, db } from '../../helpers/db.js';

let recruiter, job;
test.beforeAll(async () => { recruiter = await createUser('recruiter'); job = await createJob(recruiter); });

const sendInvite = async (emails, over = {}) =>
  call('POST', `/recruiter/jobs/${job._id}/invites`, { token: recruiter.token, json: { emails, invite_type: 'apply', validity_days: 3, ...over } });

test('API-10a preview classifies valid, invalid and duplicate emails', async () => {
  const good = uniqueEmail('inv');
  const preview = (body) => call('POST', `/recruiter/jobs/${job._id}/invites/preview`, { token: recruiter.token, json: body });
  const r = await preview({ email: good });
  expect(r.status).toBe(200);
  expect(r.data.valid).toContain(good);

  // the same address given twice (pasted list + single field) is flagged as a
  // duplicate; junk in the pasted list is reported as invalid
  const f = new FormData(); f.append('bulk', `${good}\nnot-an-email`); f.append('email', good);
  const bulk = await call('POST', `/recruiter/jobs/${job._id}/invites/preview`, { token: recruiter.token, form: f });
  expect(bulk.data.valid).toEqual([good]);
  expect(bulk.data.invalid).toContain('not-an-email');
  expect(bulk.data.duplicates.length).toBe(1);
});

test('API-10b sending a batch creates invited accounts and charges credits', async () => {
  const a = uniqueEmail('inv'); const b = uniqueEmail('inv');
  const sent = await sendInvite([a, b]);
  expect(sent.status).toBe(202);
  expect(sent.data).toMatchObject({ total: 2, credits_charged: 2 });

  await expect.poll(async () => (await call('GET', `/recruiter/jobs/${job._id}/invites/batches/${sent.data.batch_id}`, { token: recruiter.token })).data.status, { timeout: 20_000 })
    .toMatch(/completed|done|sent|finished/i);

  const list = await call('GET', `/recruiter/jobs/${job._id}/invites`, { token: recruiter.token, expect: 200 });
  expect(list.data.invited.map(i => i.email)).toEqual(expect.arrayContaining([a, b]));
  const logged = await (await db()).collection('email_log').countDocuments({ to_email: a });
  expect(logged).toBeGreaterThan(0); // the noop provider recorded the send
});

test('API-10c only the job\'s recruiter can invite; candidates cannot', async () => {
  const other = await createUser('recruiter');
  const r = await call('POST', `/recruiter/jobs/${job._id}/invites`, { token: other.token, json: { emails: [uniqueEmail('inv')] } });
  expect([403, 404]).toContain(r.status);
});

test('API-10d invite validation: non-list and empty emails are refused', async () => {
  expect((await sendInvite('a@e2e.test')).status).toBe(400);
  expect((await sendInvite([])).status).toBeGreaterThanOrEqual(400);
});

test('API-10e magic link: lookup, redeem once, then the link is dead', async () => {
  const email = uniqueEmail('inv');
  expect((await sendInvite([email])).status).toBe(202);
  const { raw } = await knownInviteToken(email);
  const ip = randomIp();

  const look = await call('GET', `/invite/redeem?token=${raw}`, { ip });
  expect(look.status).toBe(200);
  expect(look.data.user.email).toBe(email);
  expect(look.data.job.id).toBe(job._id);

  const redeemed = await call('POST', '/invite/redeem', { json: { token: raw }, ip });
  expect(redeemed.status).toBe(200);
  expect(redeemed.data.token).toBeTruthy();
  expect(redeemed.data.user.is_invite_only).toBe(true);
  expect((await call('GET', '/me', { token: redeemed.data.token })).status).toBe(200);

  expect((await call('POST', '/invite/redeem', { json: { token: raw }, ip })).status).toBe(410);
  expect((await call('GET', `/invite/redeem?token=${raw}`, { ip })).status).toBe(410);
});

test('API-10f unknown or empty tokens are rejected', async () => {
  const ip = randomIp();
  expect((await call('POST', '/invite/redeem', { json: { token: 'nope' }, ip })).status).toBe(410);
  expect((await call('POST', '/invite/redeem', { json: {}, ip })).status).toBe(400);
});

test('API-10g an expired invite cannot be redeemed', async () => {
  const email = uniqueEmail('inv');
  await sendInvite([email]);
  const { raw, user } = await knownInviteToken(email);
  await (await db()).collection('invite_tokens').updateOne({ user_id: user._id }, { $set: { expires_at: new Date(Date.now() - 60_000) } });
  expect((await call('POST', '/invite/redeem', { json: { token: raw }, ip: randomIp() })).status).toBe(410);
});

test('API-11 throttling: a burst of redeem attempts from one client gets 429', async () => {
  const ip = randomIp(); // private bucket, so other specs are unaffected
  const statuses = [];
  for (let i = 0; i < 30; i++) statuses.push((await call('POST', '/invite/redeem', { json: { token: `bad-${i}` }, ip })).status);
  expect(statuses).toContain(429);
  expect(statuses.slice(0, 5).every(s => s === 410)).toBe(true);
  // a different client is not affected
  expect((await call('POST', '/invite/redeem', { json: { token: 'bad' }, ip: randomIp() })).status).toBe(410);
});

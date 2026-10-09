// Smoke checklist §3 (practice) and §4 (interview) — everything that can be
// verified without a human, a real face, or paid speech/LLM services:
//   · the practice launcher, readiness guide and history
//   · starting an interview (credits, preconditions) and the device-check /
//     face-registration steps with Chromium's fake camera + microphone
// Question generation, TTS/STT and evaluation live in specs/ai/*.
import { test, expect, REPORT_MODAL_BUG } from '../../fixtures/test.js';
import { call, createJob, createUser, saveCvDetails } from '../../helpers/api.js';
import { button } from '../../helpers/ui.js';

const wallet = async (user) => (await call('GET', '/payment/wallet/summary', { token: user.token })).data.data.wallet.credits_balance;

// A shortlisted application: the state in which a candidate may start an interview.
async function shortlistedApplication(recruiter, candidate, jobOver) {
  const job = await createJob(recruiter, jobOver);
  await saveCvDetails(candidate);
  const applied = await call('POST', `/jobs/${job._id}/apply`, { token: candidate.token, json: {}, expect: 201 });
  await call('PUT', `/applications/${applied.data.application_id}/status`, { token: recruiter.token, json: { status: 'shortlisted' }, expect: 200 });
  return { job, applicationId: applied.data.application_id };
}

test.describe('practice launcher', () => {
  test('UI-PRAC-01 shows roles, difficulties and proctoring; start needs a role and difficulty', async ({ asUser, createUser }) => {
    const page = await asUser(await createUser('candidate'));
    await page.goto('/practice');
    for (const h of ['Practice Interview Mode', 'Select Practice Role', 'Interview Difficulty', 'Practice Proctoring', 'Practice History']) {
      await expect(page.getByRole('heading', { name: h })).toBeVisible();
    }
    const start = button(page, 'START PRACTICE INTERVIEW');
    await expect(start).toBeDisabled();
    await page.getByText('Software Engineer', { exact: true }).click();
    await page.getByText('Easy', { exact: true }).click();
    await expect(start).toBeEnabled();
  });

  test('UI-PRAC-02 starting opens the secure-browser readiness guide, gated by a confirmation', async ({ asUser, createUser }) => {
    const page = await asUser(await createUser('candidate'));
    await page.goto('/practice');
    await page.getByText('Software Engineer', { exact: true }).click();
    await page.getByText('Medium', { exact: true }).click();
    await button(page, 'START PRACTICE INTERVIEW').click();
    await expect(page.getByRole('heading', { name: 'Get ready for your practice' })).toBeVisible();
    const next = button(page, 'Continue to CV selection');
    await expect(next).toBeDisabled();
    await page.getByRole('checkbox', { name: /installed GenHire Secure Browser/i }).check();
    await expect(next).toBeEnabled();
    await page.getByRole('button', { name: 'Close installation guide' }).click();
    await expect(page.getByRole('heading', { name: 'Get ready for your practice' })).toBeHidden();
  });

  test('UI-PRAC-03 history shows an empty state for a candidate with no sessions', async ({ asUser, createUser }) => {
    const page = await asUser(await createUser('candidate'));
    await page.goto('/practice');
    await expect(page.getByRole('heading', { name: 'Practice History' })).toBeVisible();
    await expect(page.locator('body')).toContainText(/no practice|haven't|no sessions|no history|yet/i);
  });

  test('UI-PRAC-04 practice API: history is empty and a session cannot be read by another user', async ({ createUser }) => {
    const a = await createUser('candidate'); const b = await createUser('candidate');
    const history = await call('GET', '/practice/history', { token: a.token, expect: 200 });
    expect(JSON.stringify(history.data)).toMatch(/\[\]|"sessions":\s*\[\]|"count":\s*0/);
    const report = await call('GET', '/practice/000000000000000000000000/report', { token: b.token });
    expect([403, 404]).toContain(report.status);
  });
});

test.describe('interview', () => {
  let recruiter;
  test.beforeAll(async () => { recruiter = await createUser('recruiter'); });

  test('UI-INT-01 a shortlisted application offers "Give Interview" and opens the readiness guide', async ({ asUser, createUser, bugs }) => {
    test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);
    const cand = await createUser('candidate');
    await shortlistedApplication(recruiter, cand, { title: 'Guide Role' });
    const page = await asUser(cand);
    await page.goto('/profile#applications');
    const give = page.locator('button:visible', { hasText: /interview/i }).filter({ hasNotText: /report/i }).first();
    await give.click();
    await expect(page.getByRole('heading', { name: /Get ready for your interview/ })).toBeVisible();
    await expect(button(page, 'Open Secure Browser')).toBeDisabled();
    await page.getByRole('checkbox', { name: /installed GenHire Secure Browser/i }).check();
    await expect(button(page, 'Open Secure Browser')).toBeEnabled();
  });

  test('UI-INT-02 starting an interview creates a session and debits the recruiter wallet', async ({ createUser }) => {
    const rec = await createUser('recruiter'); const cand = await createUser('candidate');
    const { applicationId } = await shortlistedApplication(rec, cand);
    const before = await wallet(rec);
    const start = await call('POST', '/interviews/start', { token: cand.token, json: { application_id: applicationId }, expect: 200 });
    expect(start.data.interview_id).toBeTruthy();
    expect(start.data.initial_questions.length).toBeGreaterThan(0);
    expect(start.data.max_questions).toBeGreaterThan(0);
    expect(before - (await wallet(rec))).toBe(start.data.credits_deducted);
  });

  test('UI-INT-03 start preconditions: someone else\'s application, unknown application and exhausted credits are refused', async ({ createUser }) => {
    const rec = await createUser('recruiter');
    const owner = await createUser('candidate'); const other = await createUser('candidate');
    const { applicationId } = await shortlistedApplication(rec, owner);
    expect([403, 404]).toContain((await call('POST', '/interviews/start', { token: other.token, json: { application_id: applicationId } })).status);
    expect((await call('POST', '/interviews/start', { token: owner.token, json: { application_id: '000000000000000000000000' } })).status).toBe(404);
    expect([400, 404]).toContain((await call('POST', '/interviews/start', { token: owner.token, json: {} })).status);

    // a recruiter wallet holds 100 credits and an interview costs 50: the third start must fail
    await call('POST', '/interviews/start', { token: owner.token, json: { application_id: applicationId }, expect: 200 });
    const second = await createUser('candidate'); const third = await createUser('candidate');
    const app2 = await shortlistedApplication(rec, second);
    await call('POST', '/interviews/start', { token: second.token, json: { application_id: app2.applicationId }, expect: 200 });
    const app3 = await shortlistedApplication(rec, third);
    const refused = await call('POST', '/interviews/start', { token: third.token, json: { application_id: app3.applicationId } });
    expect(refused.status).toBeGreaterThanOrEqual(400);
    expect(JSON.stringify(refused.data)).toMatch(/credit|unavailable/i);
  });

  test('UI-INT-04 a job that needs a second camera cannot start while mobile recording is disabled', async ({ createUser }) => {
    const rec = await createUser('recruiter'); const cand = await createUser('candidate');
    const { applicationId } = await shortlistedApplication(rec, cand, {
      proctoring_config: { dual_camera: true, eyeball_tracking: true, object_detection: true, voice_detection: true, gaze_heatmap: true, ai_detection: false },
    });
    const r = await call('POST', '/interviews/start', { token: cand.token, json: { application_id: applicationId } });
    expect(r.status).toBeGreaterThanOrEqual(400);
    expect(JSON.stringify(r.data)).toMatch(/mobile|second camera|dual/i);
  });

  test('UI-INT-05 an invited candidate who has not completed their application cannot start', async ({ createUser }) => {
    const rec = await createUser('recruiter'); const job = await createJob(rec);
    const email = `skeleton-${Date.now()}@e2e.test`;
    await call('POST', `/recruiter/jobs/${job._id}/invites`, { token: rec.token, json: { emails: [email], invite_type: 'interview' }, expect: 202 });
    const { knownInviteToken, db } = await import('../../helpers/db.js');
    const { raw, user } = await knownInviteToken(email);
    const redeemed = await call('POST', '/invite/redeem', { json: { token: raw }, ip: '10.9.9.9', expect: 200 });
    const app = await (await db()).collection('applications').findOne({ $or: [{ student_id: String(user._id) }, { student_id: user._id }] });
    const r = await call('POST', '/interviews/start', { token: redeemed.data.token, json: { application_id: String(app._id) } });
    expect(r.status).toBe(400);
    expect(r.data.error_code).toBe('application_incomplete');
  });

  test('UI-INT-06 the interview page shows a clear error and recovery links for an unknown session', async ({ asUser, createUser }) => {
    const page = await asUser(await createUser('candidate'));
    await page.goto('/interviews/not-a-real-session');
    await expect(page.getByRole('heading', { name: "We couldn't open this interview" })).toBeVisible();
    await expect(button(page, 'Retry')).toBeVisible();
    await button(page, 'Back to applications').click();
    await expect(page).toHaveURL(/\/profile/);
  });

  test('UI-INT-07 device checks: camera/mic enabled, sound confirmed, then face registration step', async ({ asUser, createUser }) => {
    const rec = await createUser('recruiter'); const cand = await createUser('candidate');
    const { applicationId } = await shortlistedApplication(rec, cand);
    const { data } = await call('POST', '/interviews/start', { token: cand.token, json: { application_id: applicationId }, expect: 200 });
    const page = await asUser(cand);
    await page.goto(`/interviews/${data.session_id}`);

    await expect(page.getByRole('heading', { name: /A few checks/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Make sure we can see and hear you' })).toBeVisible();
    await expect(button(page, 'Continue')).toBeDisabled();
    await button(page, 'Enable camera and microphone').click();
    await button(page, 'Play test sound').click();
    await button(page, 'I heard the sound').click();
    await expect(button(page, 'Continue')).toBeEnabled();
    await button(page, 'Continue').click();
    await expect(page.getByRole('heading', { name: 'Center your face in the preview' })).toBeVisible();
    await expect(button(page, 'Capture my face')).toBeVisible();
    await button(page, 'Back').click();
    await expect(page.getByRole('heading', { name: 'Make sure we can see and hear you' })).toBeVisible();
  });

  test('UI-INT-08 mobile camera pairing page rejects a missing or invalid pairing token', async ({ page }) => {
    await page.goto('/mobile-camera/some-session');
    await expect(page.locator('body')).toContainText(/no private pairing token/i);
    await page.goto('/mobile-camera/some-session?pairing_token=bogus');      // joins the real socket server
    await expect(page.locator('body')).toContainText(/invalid or expired/i);
    await page.goto('/mobile-cam/some-session?pairing_token=bogus');         // legacy alias
    await expect(page.locator('body')).toContainText(/invalid or expired/i);
  });

  test('UI-INT-09 interview list API only returns the candidate\'s own sessions', async ({ createUser }) => {
    const rec = await createUser('recruiter'); const a = await createUser('candidate'); const b = await createUser('candidate');
    const { applicationId } = await shortlistedApplication(rec, a);
    const { data } = await call('POST', '/interviews/start', { token: a.token, json: { application_id: applicationId }, expect: 200 });
    expect((await call('GET', `/interviews/${data.session_id}/session`, { token: a.token })).status).toBe(200);
    expect([403, 404]).toContain((await call('GET', `/interviews/${data.session_id}/session`, { token: b.token })).status);
  });
});

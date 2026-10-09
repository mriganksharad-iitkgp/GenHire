// Smoke checklist §2 — candidate core: dashboard, job details, apply, saved jobs, profile.
import { test, expect, REPORT_MODAL_BUG } from '../../fixtures/test.js';
import { call, createJob, createUser, saveCvDetails } from '../../helpers/api.js';
import { button } from '../../helpers/ui.js';
import { cvPdf, idCardPng } from '../../helpers/files.js';

let recruiter;
test.beforeAll(async () => { recruiter = await createUser('recruiter'); });

// Specs that open /profile are skipped while the InterviewReportModal bug blanks that page
// (see REPORT_MODAL_BUG in fixtures/test.js).

test('UI-CAND-01 dashboard lists open jobs and filters by search text', async ({ asUser, createUser }) => {
  const title = `Zebra Wrangler ${Date.now()}`;
  await createJob(recruiter, { title });
  const page = await asUser(await createUser('candidate'));
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: /Current Openings/ })).toBeVisible();
  await page.getByPlaceholder(/Search for positions/).fill(title);
  await expect(page.getByRole('heading', { name: /Current Openings \(1\)/ })).toBeVisible();
  await expect(page.locator('body')).toContainText(title);
  await page.getByPlaceholder(/Search for positions/).fill('zzz-no-such-job-zzz');
  await expect(page.getByRole('heading', { name: /Current Openings \(0\)/ })).toBeVisible();
});

test('UI-CAND-02 job details page shows the posting and its actions', async ({ asUser, createUser }) => {
  const job = await createJob(recruiter, { title: 'Details Page Engineer' });
  const page = await asUser(await createUser('candidate'));
  await page.goto(`/jobs/${job._id}`);
  await expect(page.getByRole('heading', { name: 'Details Page Engineer' })).toBeVisible();
  for (const h of ['Job Description', 'Qualifications & Requirements', 'About Company']) {
    await expect(page.getByRole('heading', { name: h })).toBeVisible();
  }
  await expect(button(page, 'Save')).toBeVisible();
});

test('UI-CAND-03 a candidate without a CV is told to complete their profile before applying', async ({ asUser, createUser }) => {
  const job = await createJob(recruiter);
  const page = await asUser(await createUser('candidate'));
  await page.goto(`/jobs/${job._id}`);
  await expect(page.getByRole('link', { name: /Update your profile first/ })).toBeVisible();
});

test('UI-CAND-04 applying to a job: it becomes an application, can be withdrawn', async ({ asUser, createUser }) => {
  const job = await createJob(recruiter, { title: 'Apply Flow Engineer' });
  const cand = await createUser('candidate');
  await saveCvDetails(cand);
  const page = await asUser(cand);
  await page.goto('/dashboard');
  await page.getByPlaceholder(/Search for positions/).fill('Apply Flow Engineer');
  await button(page, 'Apply Now').first().click();
  // the CV selection step opens; confirm the application
  const confirm = page.locator('button:visible', { hasText: /apply|submit|confirm|continue/i });
  await expect(confirm.first()).toBeVisible();
  await confirm.last().click();
  await expect.poll(async () => (await call('GET', '/applications', { token: cand.token })).data.length, { timeout: 15_000 }).toBe(1);

  await page.goto(`/jobs/${job._id}`);
  await expect(button(page, 'Withdraw Application').first()).toBeVisible();
  await button(page, 'Withdraw Application').first().click();
  const ok = page.locator('button:visible', { hasText: /^\s*(withdraw|confirm|yes)/i });
  if (await ok.count()) await ok.last().click();
  await expect.poll(async () => (await call('GET', '/applications', { token: cand.token })).data.length, { timeout: 15_000 }).toBe(0);
});

test('UI-CAND-05 save and unsave a job; it appears in the Saved Jobs tab', async ({ asUser, createUser }) => {
  const title = `Saved Role ${Date.now()}`;
  await createJob(recruiter, { title });
  const page = await asUser(await createUser('candidate'));
  await page.goto('/dashboard');
  await page.getByPlaceholder(/Search for positions/).fill(title);
  await page.getByRole('button', { name: `Save ${title} for later` }).click();
  await expect(page.getByRole('button', { name: `Remove ${title} from saved jobs` })).toBeVisible();

  await page.getByRole('tab', { name: 'Saved Jobs' }).click();
  await expect(page.getByRole('heading', { name: /Saved Jobs \(1\)/ })).toBeVisible();
  await expect(page.locator('body')).toContainText(title);

  await page.getByRole('button', { name: `Remove ${title} from saved jobs` }).click();
  await expect(page.getByRole('heading', { name: /Saved Jobs \(0\)/ })).toBeVisible();
});

test('UI-CAND-06 legacy /job/:id redirects to /jobs/:id and keeps the query string', async ({ asUser, createUser }) => {
  const job = await createJob(recruiter);
  const page = await asUser(await createUser('candidate'));
  await page.goto(`/job/${job._id}?src=email&x=1`);
  await expect(page).toHaveURL(new RegExp(`/jobs/${job._id}\\?src=email&x=1$`));
});

test('UI-CAND-07 profile page: sections render and bio data saves', async ({ asUser, createUser, bugs }) => {
  test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);
  const cand = await createUser('candidate');
  const page = await asUser(cand);
  await page.goto('/profile');
  for (const h of ['CV Information', 'Application Status', 'Identity Card', 'Bio Data']) {
    await expect(page.getByRole('heading', { name: h })).toBeVisible();
  }
  await page.locator('input[type=tel]').fill('9876543210');
  await page.locator('input[type=text]').nth(1).fill('Pune');
  await button(page, 'Update Profile').click();
  await expect.poll(async () => (await call('GET', '/profile', { token: cand.token })).data.phone, { timeout: 10_000 }).toBe('9876543210');
});

test('UI-CAND-08 profile: uploading a CV PDF lists it', async ({ asUser, createUser, bugs }) => {
  test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);
  const cand = await createUser('candidate');
  const page = await asUser(cand);
  await page.goto('/profile');
  await page.locator('input[type=file][accept=".pdf"]').setInputFiles(await cvPdf());
  await expect(page.locator('body')).toContainText('cv.pdf');
  await button(page, 'Upload CV').click();
  await expect.poll(async () => (await call('GET', '/cv/list', { token: cand.token })).data.count, { timeout: 20_000 }).toBe(1);
});

test('UI-CAND-09 profile: identity card upload locks the panel (stays locked after reload)', async ({ asUser, createUser, bugs }) => {
  test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);
  const cand = await createUser('candidate');
  const page = await asUser(cand);
  await page.goto('/profile');
  await page.locator('input[type=file][accept^="image/jpeg"]').setInputFiles(await idCardPng());
  await button(page, 'Upload Identity Card').click();
  await expect.poll(async () => (await call('GET', '/identity-card', { token: cand.token })).data.locked, { timeout: 15_000 }).toBe(true);
  await page.reload();
  await expect(page.locator('body')).toContainText(/locked|uploaded|administrator/i);
});

test('UI-CAND-10 profile: applications tab lists the application with a Details link', async ({ asUser, createUser, bugs }) => {
  test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);
  const job = await createJob(recruiter, { title: 'Profile Apps Engineer' });
  const cand = await createUser('candidate');
  await saveCvDetails(cand);
  const { data } = await call('POST', `/jobs/${job._id}/apply`, { token: cand.token, json: {}, expect: 201 });
  const page = await asUser(cand);
  await page.goto('/profile#applications');
  await expect(page.locator('body')).toContainText('Profile Apps Engineer');
  await page.getByRole('link', { name: /Details/ }).click();
  await expect(page).toHaveURL(new RegExp(`/applications/${data.application_id}$`));
});

test('UI-CAND-11 delete-account modal asks for confirmation and removes the account', async ({ asUser, createUser, bugs }) => {
  test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);
  const cand = await createUser('candidate');
  const page = await asUser(cand);
  await page.goto('/profile');
  await button(page, 'Delete Account').click();
  await expect(page.getByRole('heading', { name: /delete/i }).first()).toBeVisible();
});

test('UI-CAND-12 candidate cost statistics and team pages render', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('candidate'));
  await page.goto('/candidate/cost-statistics');
  await expect(page.getByRole('heading', { name: 'Practice Cost Statistics' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Practice Credits' })).toBeVisible();
  await page.goto('/team');
  await expect(page.getByRole('heading', { name: 'Meet the Developers' })).toBeVisible();
});

test('UI-CAND-13 navbar shows the wallet balance and links work', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('candidate'));
  await page.goto('/dashboard');
  await expect(page.locator('button:visible', { hasText: '100 credits left' }).first()).toBeVisible();
  await page.locator('a:visible', { hasText: 'Practice' }).first().click();
  await expect(page).toHaveURL(/\/practice$/);
});

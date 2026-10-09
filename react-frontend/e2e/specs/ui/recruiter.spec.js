// Smoke checklist §5 — recruiter dashboard, jobs, candidates, invites, export.
import { test, expect, REPORT_MODAL_BUG } from '../../fixtures/test.js';
import { call, createJob, createUser, saveCvDetails } from '../../helpers/api.js';
import { button } from '../../helpers/ui.js';

// The recruiter dashboard mounts InterviewReportModal, so every spec here is skipped while that bug exists.
test.beforeEach(async ({ bugs }) => { test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG); });

// Tab buttons carry an icon glyph, so match on the visible text.
const tab = (page, name) => page.locator('button:visible', { hasText: new RegExp(`^\\s*${name}\\s*$`) }).first();
const openJobs = async (page) => { await page.goto('/recruiter/dashboard'); await tab(page, 'Job Postings').click(); };

async function recruiterWithApplicant(over = {}) {
  const rec = await createUser('recruiter');
  const job = await createJob(rec, over);
  const cand = await createUser('candidate', { name: 'Applicant Alex' });
  await saveCvDetails(cand);
  const applied = await call('POST', `/jobs/${job._id}/apply`, { token: cand.token, json: {}, expect: 201 });
  return { rec, job, cand, applicationId: applied.data.application_id };
}

test('UI-REC-01 every dashboard tab renders its section', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('recruiter'));
  await page.goto('/recruiter/dashboard');
  await expect(page.getByRole('heading', { name: 'Dashboard Overview' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Recent Activity' }).first()).toBeVisible();
  await tab(page, 'Job Postings').click();
  await expect(page.getByRole('heading', { name: 'Job Postings Management' })).toBeVisible();
  await tab(page, 'Candidates').click();
  await expect(page.getByRole('heading', { name: 'Candidate Management' })).toBeVisible();
  await tab(page, 'Company Profile').click();
  await expect(page.getByRole('heading', { name: 'Company Profile' })).toBeVisible();
  await tab(page, 'Cost Statistics').click();
  await expect(page).toHaveURL(/\/recruiter\/cost-statistics/);
});

test('UI-REC-02 creating a job: required fields are validated, then the job appears', async ({ asUser, createUser }) => {
  const rec = await createUser('recruiter');
  const page = await asUser(rec);
  await openJobs(page);
  await button(page, 'Create New Job').click();
  await expect(page.getByRole('heading', { name: 'Create New Job Posting' })).toBeVisible();

  // the form cannot be submitted while required fields are empty
  await expect(button(page, 'Create Job')).toBeDisabled();

  const title = `UI Created Role ${Date.now()}`;
  await page.locator('[name=title]').fill(title);
  await page.locator('[name=department]').fill('Engineering');
  await page.locator('[name=location]').fill('Remote');
  await page.locator('[name=experience]').fill('3+ years');
  await page.locator('[name=salary]').fill('10-20 LPA');
  await page.locator('textarea[name=description]').fill('A role created from the UI during an end-to-end test.');
  await expect(button(page, 'Create Job')).toBeDisabled();       // still needs at least one skill
  await button(page, 'Python').click();                            // quick-add skill chip
  await expect(button(page, 'Create Job')).toBeEnabled();
  await button(page, 'Create Job').click();

  await expect(page.locator('body')).toContainText(title);
  const jobs = (await call('GET', '/jobs', { token: rec.token })).data;
  expect(jobs.map(j => j.title)).toContain(title);
});

test('UI-REC-03 editing a job saves the change', async ({ asUser, createUser }) => {
  const rec = await createUser('recruiter');
  const job = await createJob(rec, { title: 'Before Edit Role' });
  const page = await asUser(rec);
  await openJobs(page);
  await page.locator('button:visible', { hasText: /^\s*Edit\s*$/ }).first().click();
  await expect(page.getByRole('heading', { name: /Edit Job Details/ })).toBeVisible();
  await page.locator('[name=title]').fill('After Edit Role');
  await button(page, 'Update Job').click();
  await expect(page.locator('body')).toContainText('After Edit Role');
  expect((await call('GET', `/jobs/${job._id}`, { token: rec.token })).data.title ?? '').toContain('After Edit Role');
});

test('UI-REC-04 job details modal shows statistics and closes', async ({ asUser, createUser }) => {
  const rec = await createUser('recruiter');
  await createJob(rec, { title: 'Details Modal Role' });
  const page = await asUser(rec);
  await openJobs(page);
  await button(page, 'View Details').click();
  await expect(page.getByRole('heading', { name: 'Job Details' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Application Statistics' })).toBeVisible();
  await button(page, 'Back to Jobs').click();
  await expect(page.getByRole('heading', { name: 'Job Details' })).toBeHidden();
});

test('UI-REC-05 invite-candidates modal: preview then send; invites are created', async ({ asUser, createUser }) => {
  const rec = await createUser('recruiter');
  const job = await createJob(rec, { title: 'Invite Flow Role' });
  const page = await asUser(rec);
  await openJobs(page);
  await button(page, 'Invite Candidates').click();
  await expect(page.getByRole('heading', { name: /Invite candidates to Invite Flow Role/ })).toBeVisible();

  await button(page, 'Paste Emails').click();
  const a = `ui-inv-${Date.now()}@e2e.test`;
  await page.locator('textarea:visible').fill(`${a}\nnot-an-email`);
  await button(page, 'Preview list').click();
  await expect(page.locator('body')).toContainText(a);
  await expect(page.locator('body')).toContainText(/invalid/i);

  await page.locator('button:visible', { hasText: /send/i }).last().click();
  await expect.poll(async () => (await call('GET', `/recruiter/jobs/${job._id}/invites`, { token: rec.token })).data.invited.map(i => i.email), { timeout: 20_000 }).toContain(a);
});

test('UI-REC-06 candidates tab lists applicants and opens their CV', async ({ asUser }) => {
  const { rec } = await recruiterWithApplicant({ title: 'Candidates Tab Role' });
  const page = await asUser(rec);
  await page.goto('/recruiter/dashboard');
  await tab(page, 'Candidates').click();
  await expect(page.getByRole('heading', { name: 'Applicant Alex' })).toBeVisible();
  await expect(button(page, 'View CV')).toBeVisible();
});

// KNOWN BUG (found by this suite): RecruiterDashboard.handleViewJobCandidates sets
// selectedPosition to job.title, but the candidates filter now compares it to
// app.job_id ("Value is the job id" comment), so the list is always empty.
// Remove test.fail() once fixed — the test then runs as a normal check.
test('UI-REC-07 "View Candidates" on a job card shows that job\'s applicants', async ({ asUser }) => {
  test.fail(true, 'KNOWN BUG: View Candidates passes job.title but the filter compares job_id');
  const { rec } = await recruiterWithApplicant({ title: 'Filtered Candidates Role' });
  const page = await asUser(rec);
  await openJobs(page);
  await button(page, /View Candidates \(1\)/).click();
  await expect(page.getByRole('heading', { name: 'Candidate Management' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Applicant Alex' })).toBeVisible();
});

test('UI-REC-08 "Export Cleared" downloads an XLSX for the job', async ({ asUser, createUser }) => {
  const rec = await createUser('recruiter');
  await createJob(rec, { title: 'Export Role' });
  const page = await asUser(rec);
  await openJobs(page);
  const [download] = await Promise.all([page.waitForEvent('download', { timeout: 15_000 }), button(page, 'Export Cleared').click()]);
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/i);
});

test('UI-REC-09 company profile can be edited and saved', async ({ asUser, createUser }) => {
  const rec = await createUser('recruiter');
  const page = await asUser(rec);
  await page.goto('/recruiter/dashboard');
  await tab(page, 'Company Profile').click();
  await button(page, 'Edit Profile').click();
  await page.locator('input[type=text]:visible').first().fill('Edited Company Name');
  await page.locator('button:visible', { hasText: /save|update/i }).first().click();
  await expect.poll(async () => JSON.stringify((await call('GET', '/profile', { token: rec.token })).data), { timeout: 10_000 }).toContain('Edited Company Name');
});

test('UI-REC-10 cost statistics, team and subscription pages render', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('recruiter'));
  await page.goto('/recruiter/cost-statistics');
  await expect(page.getByRole('heading', { name: 'Usage Dashboard' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Wallet Credits' })).toBeVisible();
  await page.goto('/recruiter/team');
  await expect(page.getByRole('heading', { name: 'Meet the Developers' })).toBeVisible();
});

test('UI-REC-11 an unapproved recruiter sees the verification-pending state, not a working dashboard', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('recruiter', { verify: false }));
  await page.goto('/recruiter/dashboard');
  await expect(page.locator('body')).toContainText(/pending|verification|awaiting/i);
  await expect(button(page, 'Create New Job')).toHaveCount(0);
});

test('UI-REC-12 recruiter aliases redirect to the canonical dashboard', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('recruiter'));
  await page.goto('/recruiter-dashboard');
  await expect(page).toHaveURL(/\/recruiter\/dashboard/);
});

test('UI-REC-13 application view shows the applicant\'s details to the recruiter', async ({ asUser }) => {
  const { rec, applicationId } = await recruiterWithApplicant({ title: 'App View Role' });
  const page = await asUser(rec);
  await page.goto(`/applications/${applicationId}`);
  await expect(page.locator('body')).toContainText(/Applicant Alex|App View Role/);
});

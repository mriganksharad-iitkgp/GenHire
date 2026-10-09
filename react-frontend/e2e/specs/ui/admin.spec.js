// Smoke checklist §6 — admin portal.
import { test, expect, REPORT_MODAL_BUG } from '../../fixtures/test.js';
import { call, createUser, adminUser, uploadIdentityCard, userId, createJob } from '../../helpers/api.js';
import { idCardPng } from '../../helpers/files.js';
import { button } from '../../helpers/ui.js';

// The stack (and its DB) outlives a single test, so every name carries a unique tag.
const uniq = (base) => `${base} ${process.env.E2E_RUN_ID}${Math.random().toString(36).slice(2, 6)}`;

test.describe('admin portal', () => {
  let adminPage;
  test.beforeEach(async ({ asUser }) => { adminPage = await asUser(await adminUser()); });

  test('UI-ADM-01 overview shows stats and the quick-navigation cards', async () => {
    await adminPage.goto('/admin');
    await expect(adminPage.getByRole('heading', { name: 'Dashboard Overview' })).toBeVisible();
    await expect(adminPage.getByRole('heading', { name: 'Quick Navigation' })).toBeVisible();
    for (const h of ['Manage Candidates', 'Manage Recruiters', 'Manage Admins']) {
      await expect(adminPage.getByRole('heading', { name: h })).toBeVisible();
    }
  });

  test('UI-ADM-02 sidebar navigation reaches every admin section', async () => {
    await adminPage.goto('/admin');
    const sections = [['Candidates', /\/admin\/candidates$/], ['Recruiters', /\/admin\/recruiters$/], ['Admins', /\/admin\/admins$/],
      ['Verification', /\/admin\/verification$/], ['Cost Statistics', /\/admin\/cost-statistics$/], ['Credit Statistics', /\/admin\/credit-statistics$/], ['Overview', /\/admin$/]];
    for (const [label, url] of sections) {
      await adminPage.locator('button:visible', { hasText: new RegExp(`^\\s*${label}`) }).first().click();
      await expect(adminPage, label).toHaveURL(url);
    }
  });

  test('UI-ADM-03 candidates: search finds a candidate, row opens the detail page', async ({ createUser, bugs }) => {
    test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);
    const samName = uniq('Searchable Sam');
    const cand = await createUser('candidate', { name: samName });
    await adminPage.goto('/admin/candidates');
    await adminPage.getByPlaceholder('Search by name or email...').fill(samName);
    const row = adminPage.locator('tbody tr', { hasText: samName });
    await expect(row).toHaveCount(1);
    await row.getByText(samName).click();
    await expect(adminPage).toHaveURL(new RegExp(`/admin/candidates/${userId(cand)}$`));
    for (const h of ['Profile Information', 'Identity Card', 'Practice History']) {
      await expect(adminPage.getByRole('heading', { name: h })).toBeVisible();
    }
  });

  test('UI-ADM-04 candidate detail: identity card can be replaced and removed (reset)', async ({ createUser, bugs }) => {
    test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);
    const carlName = uniq('Card Carl');
    const cand = await createUser('candidate', { name: carlName });
    await uploadIdentityCard(cand);
    await adminPage.goto(`/admin/candidates/${userId(cand)}`);
    await expect(adminPage.getByRole('heading', { name: 'Identity Card' })).toBeVisible();

    await adminPage.locator('input[type=file]').last().setInputFiles(await idCardPng());       // replace
    await expect.poll(async () => (await call('GET', '/identity-card', { token: cand.token })).data.uploaded, { timeout: 15_000 }).toBe(true);

    await adminPage.locator('button:visible', { hasText: /Remove/ }).first().click();
    await expect(adminPage.getByRole('heading', { name: 'Remove identity card?' })).toBeVisible();
    await button(adminPage, 'Remove card').click();
    await expect.poll(async () => (await call('GET', '/identity-card', { token: cand.token })).data.uploaded, { timeout: 15_000 }).toBe(false);
  });

  test('UI-ADM-05 deleting a candidate asks for confirmation and removes them', async ({ createUser }) => {
    const doraName = uniq('Doomed Dora');
    const cand = await createUser('candidate', { name: doraName });
    await adminPage.goto('/admin/candidates');
    await adminPage.getByPlaceholder('Search by name or email...').fill(doraName);
    await adminPage.locator('tbody tr', { hasText: doraName }).getByTitle('Delete user').click();
    await expect(adminPage.getByRole('heading', { name: 'Delete Candidate' })).toBeVisible();
    await button(adminPage, 'Cancel').click();
    await expect(adminPage.getByRole('heading', { name: 'Delete Candidate' })).toBeHidden();
    expect((await call('POST', '/login', { json: { email: cand.email, password: cand.password, userType: 'candidate' } })).status).toBe(200);

    await adminPage.locator('tbody tr', { hasText: doraName }).getByTitle('Delete user').click();
    await button(adminPage, 'Delete').last().click();
    await expect(adminPage.locator('tbody tr', { hasText: doraName })).toHaveCount(0);
    expect((await call('POST', '/login', { json: { email: cand.email, password: cand.password, userType: 'candidate' } })).status).toBe(401);
  });

  test('UI-ADM-06 recruiters: list, search and detail with company + jobs', async ({ createUser }) => {
    const lenaName = uniq('Listed Lena');
    const rec = await createUser('recruiter', { name: lenaName });
    await createJob(rec, { title: 'Admin Visible Job' });
    await adminPage.goto('/admin/recruiters');
    await adminPage.getByPlaceholder(/Search by name, email, or company/).fill(lenaName);
    await adminPage.locator('tbody tr', { hasText: lenaName }).getByText(lenaName).click();
    await expect(adminPage).toHaveURL(new RegExp(`/admin/recruiters/${userId(rec)}$`));
    await expect(adminPage.getByRole('heading', { name: 'Company Information' })).toBeVisible();
    await expect(adminPage.getByRole('heading', { name: /Job Postings \(1\)/ })).toBeVisible();
  });

  test('UI-ADM-07 verification queue: approve and reject pending recruiters', async () => {
    const rexName = uniq('Reject Rex');
    const annName = uniq('Approve Ann');
    const toApprove = await createUser('recruiter', { verify: false, name: annName });
    await createUser('recruiter', { verify: false, name: rexName });
    await adminPage.goto('/admin/verification');
    await expect(adminPage.getByRole('heading', { name: 'Pending Verifications' })).toBeVisible();

    // the smallest block that holds both this recruiter's name and its buttons
    const card = (name) => adminPage.locator('div').filter({ has: adminPage.getByRole('heading', { name }) }).filter({ has: adminPage.locator('button', { hasText: 'Approve' }) }).last();
    await card(annName).locator('button', { hasText: 'Approve' }).click();
    await expect.poll(async () => (await call('POST', '/login', { json: { email: toApprove.email, password: toApprove.password, userType: 'recruiter' } })).data.user.is_verified, { timeout: 15_000 }).toBe(true);

    await card(rexName).locator('button', { hasText: 'Reject' }).click();
    const reason = adminPage.locator('textarea:visible, input[type=text]:visible').last();
    if (await reason.count()) await reason.fill('Not a real company');
    await adminPage.locator('button:visible', { hasText: /reject|confirm|submit/i }).last().click();
    await expect(adminPage.getByRole('heading', { name: rexName })).toBeHidden({ timeout: 15_000 });
  });

  test('UI-ADM-08 admins page lists admins and their privileges', async () => {
    await adminPage.goto('/admin/admins');
    await expect(adminPage.getByRole('heading', { name: 'Manage Admins' })).toBeVisible();
    await expect(adminPage.getByRole('heading', { name: 'Admin Privileges' })).toBeVisible();
    await expect(adminPage.locator('body')).toContainText('E2E Admin');
  });

  test('UI-ADM-09 cost statistics renders, switches range and exports CSV', async () => {
    await adminPage.goto('/admin/cost-statistics');
    await expect(adminPage.getByRole('heading', { name: 'Admin Cost Statistics' })).toBeVisible();
    await expect(adminPage.getByRole('heading', { name: 'Timeline' })).toBeVisible();
    await button(adminPage, 'This Month').click();
    await button(adminPage, 'Last 90 Days').click();
    const [download] = await Promise.all([adminPage.waitForEvent('download', { timeout: 15_000 }), button(adminPage, 'Export CSV').click()]);
    expect(download.suggestedFilename()).toMatch(/\.csv$/i);
  });

  test('UI-ADM-10 credit statistics renders all of its sections', async () => {
    await adminPage.goto('/admin/credit-statistics');
    for (const h of ['Admin Credit Statistics', 'Credit Overview', 'Candidate Balances (Total)', 'Recruiter Balances (Total)', 'Credit Usage by Candidate', 'Credit Usage by Recruiter']) {
      await expect(adminPage.getByRole('heading', { name: h })).toBeVisible();
    }
  });

  test('UI-ADM-11 overview flags pending recruiters and links to the queue', async () => {
    await createUser('recruiter', { verify: false });
    await adminPage.goto('/admin');
    await expect(adminPage.getByRole('heading', { name: 'Pending Verifications' })).toBeVisible();
    await button(adminPage, 'Review Now').click();
    await expect(adminPage).toHaveURL(/\/admin\/verification$/);
  });
});

// Smoke checklist §7 (payments pages — no real payment flow) and route aliases.
import { test, expect, REPORT_MODAL_BUG } from '../../fixtures/test.js';
import { call, createJob, uniqueEmail } from '../../helpers/api.js';
import { knownInviteToken } from '../../helpers/db.js';
import { button } from '../../helpers/ui.js';

test('UI-PAY-01 recruiter subscription page shows packs, bonus and tabs', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('recruiter'));
  await page.goto('/recruiter/subscription');
  await expect(page.getByRole('heading', { name: 'Recruiter Recharge Packs' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Recruiter Pro' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Recruiter Max' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Signup Bonus' })).toBeVisible();
  for (const t of ['Credit Activity', 'Payment History']) {
    await button(page, t).click();
    await expect(page.locator('body')).not.toContainText(/something went wrong/i);
  }
});

test('UI-PAY-02 candidate subscription page shows candidate packs only', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('candidate'));
  await page.goto('/candidate/subscription');
  await expect(page.getByRole('heading', { name: 'Candidate Recharge Packs' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Candidate Pro' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Candidate Max' })).toBeVisible();
  await expect(page.locator('body')).not.toContainText('Recruiter Pro');
});

test('UI-PAY-03 payment history shows an empty state for a new account', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('candidate'));
  await page.goto('/candidate/subscription');
  await button(page, 'Payment History').click();
  await expect(page.locator('body')).toContainText(/no payments|no payment history|nothing/i);
});

test('UI-PAY-04 legacy /subscription redirects to the recruiter subscription page', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('recruiter'));
  await page.goto('/subscription');
  await expect(page).toHaveURL(/\/recruiter\/subscription/);
});

test('UI-PAY-05 payment success and cancel pages render', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('candidate'));
  for (const path of ['/payment/success', '/payment/cancel']) {
    await page.goto(path);
    await expect(page.locator('#root')).not.toBeEmpty();
    await expect(page.locator('body')).not.toContainText(/something went wrong/i);
  }
});

test('UI-PAY-06 the recharge button in the navbar opens the matching subscription page', async ({ asUser, createUser, bugs }) => {
  test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);   // uses the recruiter dashboard
  const cand = await asUser(await createUser('candidate'));
  await cand.goto('/dashboard');
  await cand.locator('button:visible', { hasText: 'Recharge Wallet' }).first().click();
  await expect(cand).toHaveURL(/\/candidate\/subscription/);
  const rec = await asUser(await createUser('recruiter'));
  await rec.goto('/recruiter/dashboard');
  await rec.locator('button:visible', { hasText: 'Recharge Wallet' }).first().click();
  await expect(rec).toHaveURL(/\/recruiter\/subscription/);
});

test('UI-ROUTE-01 /interview and /application aliases resolve to their canonical routes', async ({ asUser, createUser }) => {
  const page = await asUser(await createUser('candidate'));
  await page.goto('/interviews/000000000000000000000000');
  await expect(page.locator('#root')).not.toBeEmpty();
  await page.goto('/application/000000000000000000000000');
  await expect(page).toHaveURL(/\/applications\/000000000000000000000000/);
});

test('UI-ROUTE-02 team pages: /recruiter/team for recruiters, /team is candidate-only', async ({ asUser, createUser }) => {
  const rec = await asUser(await createUser('recruiter'));
  await rec.goto('/recruiter/team');
  await expect(rec.getByRole('heading', { name: 'Meet the Developers' })).toBeVisible();
  await rec.goto('/team');
  await expect(rec).toHaveURL(/\/recruiter\/dashboard$/);        // bounced to their own home
  const cand = await asUser(await createUser('candidate'));
  await cand.goto('/team');
  await expect(cand.getByRole('heading', { name: 'Meet the Developers' })).toBeVisible();
});

test('UI-PUB-03 invite magic link signs the invited candidate in and lands on the job', async ({ page, createUser }) => {
  const rec = await createUser('recruiter');
  const job = await createJob(rec, { title: 'Magic Link Role' });
  const email = uniqueEmail('magic');
  await call('POST', `/recruiter/jobs/${job._id}/invites`, { token: rec.token, json: { emails: [email], invite_type: 'apply' }, expect: 202 });
  const { raw } = await knownInviteToken(email);

  await page.goto(`/invite/redeem?token=${raw}`);
  await expect(page).toHaveURL(new RegExp(`/jobs?/${job._id}`));
  await expect(page.getByRole('heading', { name: 'Magic Link Role' })).toBeVisible();

  // a used link now shows the error state with a way back to login
  await page.evaluate(() => sessionStorage.clear());
  await page.goto(`/invite/redeem?token=${raw}`);
  await expect(page.locator('body')).toContainText(/invalid|expired|already been used|snag/i);
  await expect(button(page, 'Go to login').or(page.locator('button:visible', { hasText: /login/i }).first())).toBeVisible();
});

test('UI-PUB-04 invite page without a token explains the problem', async ({ page }) => {
  await page.goto('/invite/redeem');
  await expect(page.locator('body')).toContainText(/missing a token/i);
});

test('UI-PUB-05 landing page links reach the auth pages', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#root')).not.toBeEmpty();
  await button(page, 'Login').first().click();
  await expect(page).toHaveURL(/\/login/);
});

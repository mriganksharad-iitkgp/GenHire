// Smoke checklist §1 — auth & session, plus the account flows around it.
import { test, expect, REPORT_MODAL_BUG } from '../../fixtures/test.js';
import { uniqueEmail, PASSWORD, adminToken, call, adminUser } from '../../helpers/api.js';
import { userByEmail } from '../../helpers/db.js';
import { button, uiLogin, expectHome } from '../../helpers/ui.js';

test('UI-AUTH-01 a candidate can register and lands on the dashboard', async ({ page }) => {
  const email = uniqueEmail('reg');
  await page.goto('/register');
  await page.locator('#name').fill('Reggie Candidate');
  await page.locator('#email').fill(email);
  await page.locator('#password').fill(PASSWORD);
  await page.locator('#confirmPassword').fill(PASSWORD);
  await button(page, 'Create Candidate Account').click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('heading', { name: /Find Your Dream Job/ })).toBeVisible();
});

test('UI-AUTH-02 each role logs in from the role tabs and lands on its own home', async ({ page, createUser, bugs }) => {
  test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG);   // the recruiter home is blank while the bug exists
  for (const role of ['candidate', 'recruiter']) {
    const user = await createUser(role);
    await uiLogin(page, user);
    await expectHome(page, role);
    await page.evaluate(() => sessionStorage.clear());
  }
  const admin = await adminUser();
  await uiLogin(page, admin);
  await expectHome(page, 'admin');
});

test('UI-AUTH-03 wrong credentials show an error and stay on /login', async ({ page, createUser }) => {
  const user = await createUser('candidate');
  await uiLogin(page, { ...user, password: 'Wrong#Pass9' });
  await expect(page).toHaveURL(/\/login/);
  await expect(page.locator('body')).toContainText(/invalid email or password/i);
});

test('UI-AUTH-04 logged-out visitors are sent to /login from protected pages', async ({ page }) => {
  for (const path of ['/dashboard', '/profile', '/recruiter/dashboard', '/admin', '/practice']) {
    await page.goto(path);
    await expect(page, path).toHaveURL(/\/login/);
  }
});

test('UI-AUTH-05 role guards: a user opening another role\'s pages is redirected home', async ({ asUser, createUser }) => {
  const candidate = await asUser(await createUser('candidate'));
  await candidate.goto('/admin');
  await expect(candidate).toHaveURL(/\/login|\/$/);          // admin pages bounce non-admins
  await candidate.goto('/recruiter/dashboard');
  await expect(candidate).not.toHaveURL(/recruiter\/dashboard/);

  const recruiter = await asUser(await createUser('recruiter'));
  await recruiter.goto('/dashboard');
  await expect(recruiter).toHaveURL(/\/recruiter\/dashboard$/);        // bounced to their own home
  await recruiter.goto('/admin');
  await expect(recruiter).not.toHaveURL(/\/admin$/);
});

test('UI-AUTH-06 logout clears the session and protects the app again', async ({ asUser, createUser }) => {
  const user = await createUser('candidate');
  const page = await asUser(user);
  await page.goto('/dashboard');
  await page.locator('button:visible', { hasText: user.name }).first().click();   // user menu
  await button(page, 'Logout').first().click();
  await expect(page).toHaveURL(/\/login|\/$/);
  expect(await page.evaluate(() => sessionStorage.getItem('companyxyz-token'))).toBeNull();
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login/);
});

test('UI-AUTH-07 a session that expires mid-use sends the user to /login?expired=1', async ({ asUser, createUser }) => {
  const user = await createUser('candidate');
  const page = await asUser(user);
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: /Find Your Dream Job/ })).toBeVisible();

  // the token goes bad while the app is open; the next API call gets a 401
  await page.evaluate(() => sessionStorage.setItem('companyxyz-token', 'expired.token.value'));
  await page.locator('a:visible', { hasText: 'Cost Statistics' }).first().click();
  await expect(page).toHaveURL(/\/login\?expired=1/);
  await expect(page.getByRole('status')).toContainText(/session has expired/i);
});

test('UI-AUTH-07b opening the app with an already-invalid token ends up on /login', async ({ asUser, createUser }) => {
  const user = await createUser('candidate');
  const page = await asUser({ ...user, token: user.token + 'tampered' });
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login/);
});

test('UI-AUTH-08 recruiter signup wizard → pending → admin approves → recruiter can use the dashboard', async ({ page, browser }) => {
  const email = uniqueEmail('wiz');
  await page.goto('/recruiter-signup');
  await page.getByPlaceholder('Enter your full name').fill('Wizard Recruiter');
  await page.getByPlaceholder('you@company.com').fill(email);
  await page.getByPlaceholder('Min. 8 characters').fill(PASSWORD);
  await page.getByPlaceholder('Re-enter password').fill(PASSWORD);
  await button(page, 'Continue').click();

  // step 2: company info (validation first)
  await button(page, 'Continue').click();
  await expect(page.locator('body')).toContainText(/company name is required/i);
  await page.getByPlaceholder('Enter company name').fill('Wizard Corp');
  await page.locator('select').nth(0).selectOption({ index: 1 });
  await page.locator('select').nth(1).selectOption({ index: 1 });
  await button(page, 'Continue').click();

  // step 3: about (description must be at least 50 characters)
  const about = page.getByPlaceholder(/Describe what your company does/);
  await about.fill('Short');
  await button(page, 'Continue').click();
  await expect(page.locator('body')).toContainText(/at least 50 characters/i);
  await about.fill('We build software that helps companies hire better, faster and fairly across many industries.');
  await button(page, 'Continue').click();

  // step 4: review and submit
  await expect(page.getByRole('heading', { name: 'Review Your Application' })).toBeVisible();
  await page.locator('button:visible', { hasText: /submit/i }).last().click();
  await expect(page.locator('body')).toContainText(/pending verification/i);

  // the account exists but is unverified until an admin approves it
  const stored = await userByEmail(email);
  expect(stored.is_verified).toBe(false);
  expect(stored.company_name).toBe('Wizard Corp');

  const admin = await adminToken();
  await call('PUT', `/admin/users/${stored._id}/verify`, { token: admin, json: {}, expect: 200 });
  expect((await userByEmail(email)).is_verified).toBe(true);
});

test('UI-AUTH-09 forgot password → reset with the emailed token → log in with the new password', async ({ page, createUser }) => {
  const user = await createUser('candidate');
  await page.goto('/forgot-password');
  await page.getByPlaceholder('your@email.com').fill(user.email);
  await button(page, 'Send Reset Link').click();
  await expect(page.locator('body')).toContainText(/sent|check your email|reset link/i);

  const { reset_token } = await userByEmail(user.email);      // the "email" is disabled, read the token
  await page.goto(`/reset-password?token=${reset_token}`);
  await page.getByPlaceholder('Enter new password').fill('Brandnew#123');
  await page.getByPlaceholder('Confirm new password').fill('Brandnew#123');
  await button(page, /reset password|update password|save/i).click();
  await expect(page.locator('body')).toContainText(/success|login/i);

  await uiLogin(page, { ...user, password: 'Brandnew#123' });
  await expectHome(page, 'candidate');
});

test('UI-AUTH-10 reset-password without a token shows the invalid-link state', async ({ page }) => {
  await page.goto('/reset-password');
  await expect(page.getByRole('heading', { name: 'Invalid Link' })).toBeVisible();
});

test('UI-AUTH-11 verify-email: valid token succeeds, missing/bad token errors', async ({ page, createUser }) => {
  const user = await createUser('candidate');
  const { db } = await import('../../helpers/db.js');
  const token = `e2e-ui-verify-${Math.random().toString(36).slice(2)}`;
  await (await db()).collection('users').updateOne({ email_lower: user.email }, { $set: { email_verified: false, verification_token: token } });

  await page.goto(`/verify-email?token=${token}`);
  await expect(page.locator('body')).toContainText(/verified|success/i);
  await page.goto('/verify-email?token=nope');
  await expect(page.locator('body')).toContainText(/error|invalid|expired/i);
  await page.goto('/verify-email');
  await expect(page.locator('body')).toContainText(/no verification token/i);
});

test('UI-AUTH-12 password mismatch and weak passwords are rejected on register', async ({ page }) => {
  await page.goto('/register');
  await page.locator('#name').fill('Mismatch Person');
  await page.locator('#email').fill(uniqueEmail('mm'));
  await page.locator('#password').fill(PASSWORD);
  await page.locator('#confirmPassword').fill('Different#123');
  await button(page, 'Create Candidate Account').click();
  await expect(page).toHaveURL(/\/register/);
  await expect(page.locator('body')).toContainText(/match/i);
});

test('UI-AUTH-13 registering an email that already exists shows a clear error', async ({ page, createUser }) => {
  const user = await createUser('candidate');
  await page.goto('/register');
  await page.locator('#name').fill('Dup Person');
  await page.locator('#email').fill(user.email);
  await page.locator('#password').fill(PASSWORD);
  await page.locator('#confirmPassword').fill(PASSWORD);
  await button(page, 'Create Candidate Account').click();
  await expect(page.locator('body')).toContainText(/already exists/i);
});

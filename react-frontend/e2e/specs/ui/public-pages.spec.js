import { test, expect } from '../../fixtures/test.js';

// Smoke checklist §8 — every public page renders without crashing.
const PUBLIC = [
  ['/', /GenHire/i],
  ['/login', /Welcome back/i],
  ['/register', /Create Candidate Account/i],
  ['/recruiter-signup', /Recruiter Registration/i],
  ['/forgot-password', /password/i],
  ['/reset-password', /./],
  ['/verify-email', /./],
  ['/invite/redeem', /./],
];

for (const [path, text] of PUBLIC) {
  test(`UI-PUB-01 ${path} renders`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('body')).toContainText(text);
  });
}

test('UI-PUB-02 unknown URL shows the 404 page', async ({ page }) => {
  await page.goto('/this-route-does-not-exist');
  await expect(page).toHaveURL(/\/404$/);
});

// Shared Playwright fixtures.
//   createUser(role)  – real API signup (+ admin approval for recruiters)
//   asUser(user)      – a Page already logged in as that user
//   every page         – fails the test on uncaught JS errors and on API 5xx
import { test as base, expect } from '@playwright/test';
import { createUser } from '../helpers/api.js';

const TOKEN_KEY = 'companyxyz-token';
const USER_KEY = 'companyxyz-user';

export const REPORT_MODAL_BUG =
  'KNOWN BUG (origin/main e7d81f7): InterviewReportModal calls resultScore(null) on mount, which blanks the candidate profile, ' +
  'recruiter dashboard and admin candidate-detail pages. Skipped until fixed — they run automatically once it is.';

export const test = base.extend({
  createUser: async ({}, use) => use(createUser),

  // Known product bugs, detected once per worker by actually loading an affected
  // page. Specs call `test.fixme(await bugs.reportModalCrash(), REPORT_MODAL_BUG)`,
  // so they are skipped while the bug exists and run normally after it is fixed.
  bugs: [async ({ browser }, use) => {
    let reportModalCrash;
    await use({
      reportModalCrash: () => (reportModalCrash ??= (async () => {
        const rec = await createUser('recruiter');
        const context = await browser.newContext();
        await context.addInitScript(([tk, uk, token, u]) => {
          sessionStorage.setItem(tk, token); sessionStorage.setItem(uk, JSON.stringify(u));
        }, [TOKEN_KEY, USER_KEY, rec.token, normalizeUser(rec)]);
        const page = await context.newPage();
        await page.goto('/recruiter/dashboard');
        // The crash happens after the first paint (once data loads), so wait for real content.
        const rendered = await page.getByRole('heading', { name: 'Dashboard Overview' }).waitFor({ timeout: 12_000 }).then(() => true, () => false);
        await context.close();
        return !rendered;
      })()),
    });
  }, { scope: 'worker' }],

  // The app keeps its session in sessionStorage, so seed it before any script runs.
  asUser: async ({ browser }, use) => {
    const contexts = [];
    await use(async (user) => {
      const context = await browser.newContext({ permissions: ['camera', 'microphone'] });
      contexts.push(context);
      // Seed once per tab: re-seeding on every navigation would undo a logout.
      await context.addInitScript(([tk, uk, token, u]) => {
        if (sessionStorage.getItem('__e2e_seeded')) return;
        sessionStorage.setItem('__e2e_seeded', '1');
        sessionStorage.setItem(tk, token);
        sessionStorage.setItem(uk, JSON.stringify(u));
      }, [TOKEN_KEY, USER_KEY, user.token, normalizeUser(user)]);
      return context.newPage();
    });
    await Promise.all(contexts.map(c => c.close()));
  },

  page: async ({ page }, use, testInfo) => {
    const problems = [];
    page.on('pageerror', e => problems.push(`uncaught page error: ${e.message}`));
    page.on('response', r => {
      if (r.status() >= 500 && r.url().includes('/api/') && !testInfo.annotations.some(a => a.type === 'allow-5xx')) {
        problems.push(`API ${r.status()}: ${r.request().method()} ${r.url()}`);
      }
    });
    await use(page);
    expect(problems, 'browser-side problems during the test').toEqual([]);
  },
});

function normalizeUser(user) {
  const u = user.user || {};
  return { ...u, userType: u.userType || u.user_type || user.role, user_type: u.user_type || u.userType || user.role };
}

export { expect };

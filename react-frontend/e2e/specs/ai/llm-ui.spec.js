// @ai — the same LLM features driven through the UI.
import { test, expect } from '../../fixtures/test.js';
import { llmStatus } from '../../helpers/ai.js';
import { button } from '../../helpers/ui.js';

test.describe('@ai UI', () => {
  test.beforeEach(async ({ bugs }, testInfo) => {
    const s = await llmStatus(); testInfo.skip(!s.ok, s.reason);
    testInfo.skip(await bugs.reportModalCrash(), 'recruiter dashboard is blank (known InterviewReportModal bug)');
  });

  test('AI-UI-01 "Create with AI" fills the job form from a prompt', async ({ asUser, createUser }) => {
    const page = await asUser(await createUser('recruiter'));
    await page.goto('/recruiter/dashboard');
    await page.locator('button:visible', { hasText: /^\s*Job Postings\s*$/ }).first().click();
    await button(page, 'Create New Job').click();
    await page.getByPlaceholder(/Senior React Developer/).fill('Senior Python backend developer, Flask and MongoDB, remote');
    await button(page, 'Generate JD').click();
    await expect(page.locator('[name=title]')).not.toHaveValue('', { timeout: 90_000 });
    await expect(page.locator('textarea[name=description]')).not.toHaveValue('');
  });
});

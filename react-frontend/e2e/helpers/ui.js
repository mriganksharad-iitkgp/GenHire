// Small UI helpers shared by the browser specs.
import { expect } from '@playwright/test';

// \\W* tolerates the emoji / icon-font glyphs buttons put before their label.
// The navbar renders every link twice (desktop + mobile menu), and icon fonts
// add invisible glyphs to button names — so match on visible text content.
export const button = (scope, text) =>
  scope.locator('button:visible', { hasText: typeof text === 'string' ? new RegExp(`^\\W*${escape(text)}\\W*$`, 'i') : text });
export const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export async function uiLogin(page, { email, password, role }) {
  await page.goto('/login');
  await button(page, role[0].toUpperCase() + role.slice(1)).click();   // role tabs
  await page.locator('#identifier').fill(email);
  await page.locator('#password').fill(password);
  await button(page, 'Sign in').click();
}

// A modal in this app is a plain div with a heading — find it by that heading.
export const modal = (page, heading) =>
  page.locator('div', { has: page.getByRole('heading', { name: heading }) }).last();

export async function expectHome(page, role) {
  const home = { candidate: /\/dashboard$/, recruiter: /\/recruiter\/dashboard$/, admin: /\/admin$/ }[role];
  await expect(page).toHaveURL(home);
}

// Test files are rendered on demand with Chromium (already installed for
// Playwright), so no binary fixtures live in git. Output is cached under
// <E2E_OUT_DIR>/fixtures.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { chromium } from '@playwright/test';

const DIR = path.join(process.env.E2E_OUT_DIR || path.join(os.tmpdir(), 'genhire-e2e-results'), 'fixtures');

async function render(name, build) {
  const file = path.join(DIR, name);
  if (fs.existsSync(file)) return file;
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch();
  try { await build(await browser.newPage(), file); } finally { await browser.close(); }
  return file;
}

export const CV_TEXT = {
  name: 'Jane Doe',
  email: 'jane.doe@example.com',
  skills: 'Python, Flask, MongoDB, Docker, AWS, SQL',
};

// A one-page, text-based CV PDF the backend's parser can read.
export const cvPdf = () => render('cv.pdf', async (page, file) => {
  await page.setContent(`<body style="font-family:Arial;font-size:14px;padding:24px">
    <h1>${CV_TEXT.name}</h1><p>Senior Python Developer — ${CV_TEXT.email}</p>
    <h3>Summary</h3><p>6 years building Flask and FastAPI services with MongoDB on AWS and Docker.</p>
    <h3>Experience</h3>
    <p><b>Acme Corp — Backend Engineer (2020-2026)</b><br>Built REST APIs, led a team of four, cut latency by 40%.</p>
    <p><b>Beta Ltd — Developer (2018-2020)</b><br>Django web applications.</p>
    <h3>Education</h3><p>B.Tech Computer Science, 2018</p>
    <h3>Skills</h3><p>${CV_TEXT.skills}</p></body>`);
  await page.pdf({ path: file, format: 'A4' });
});

// A card-like PNG for the identity-card upload.
export const idCardPng = () => render('id-card.png', async (page, file) => {
  await page.setViewportSize({ width: 640, height: 400 });
  await page.setContent(`<body style="margin:0;font-family:Arial;background:#e8eef9">
    <div style="padding:30px"><h2>E2E IDENTITY CARD</h2><p>Name: Jane Doe</p><p>ID: 0000-TEST</p>
    <div style="width:120px;height:140px;background:#9fb3d9;border-radius:8px"></div></div></body>`);
  await page.screenshot({ path: file });
});

export const readFile = (file) => fs.readFileSync(file);

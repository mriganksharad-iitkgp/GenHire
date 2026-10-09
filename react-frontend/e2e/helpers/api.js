// Thin client for the real backend, used to create test data quickly (the UI
// specs then exercise the UI on top of it) and by the API contract specs.
import fs from 'node:fs';
import { cvPdf, idCardPng } from './files.js';

const API = () => process.env.E2E_API_URL;
export const PASSWORD = 'Passw0rd!x';

export async function call(method, path, { token, json, form, expect, ip } = {}) {
  const headers = {};
  if (ip) headers['X-Forwarded-For'] = ip; // private rate-limit bucket (see harness/safety.mjs)
  if (token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json); }
  if (form) body = form;
  const res = await fetch(`${API()}/api${path}`, { method, headers, body });
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  if (expect && res.status !== expect) throw new Error(`${method} ${path} -> ${res.status} (expected ${expect}): ${text.slice(0, 300)}`);
  return { status: res.status, data, headers: res.headers };
}

export const uniqueEmail = (tag) => `${tag}-${process.env.E2E_RUN_ID}-${Math.random().toString(36).slice(2, 7)}@e2e.test`;

export async function register({ name, email, role = 'candidate', password = PASSWORD }) {
  return call('POST', '/register', { json: { name, email, password, confirmPassword: password, userType: role } });
}

export async function login({ email, role = 'candidate', password = PASSWORD }) {
  return call('POST', '/login', { json: { email, password, userType: role } });
}

export async function adminToken() {
  const r = await login({ email: process.env.E2E_ADMIN_EMAIL, password: process.env.E2E_ADMIN_PASSWORD, role: 'admin' });
  if (r.status !== 200) throw new Error(`admin login failed: ${r.status} ${JSON.stringify(r.data)}`);
  return r.data.token;
}

// Creates a user through the real API and returns { email, password, token, user, role }.
// Recruiters are approved by the seeded admin, as in production.
export async function createUser(role = 'candidate', { name, verify = true } = {}) {
  const email = uniqueEmail(role);
  const display = name || `E2E ${role} ${email.split('-')[1]}`;
  const reg = await register({ name: display, email, role });
  if (reg.status !== 201) throw new Error(`register failed: ${reg.status} ${JSON.stringify(reg.data)}`);
  if (role === 'recruiter' && verify) {
    const admin = await adminToken();
    await call('PUT', `/admin/users/${reg.data.user.id ?? reg.data.user._id ?? reg.data.user.user_id}/verify`, { token: admin, json: {}, expect: 200 });
  }
  const l = await login({ email, role });
  if (l.status !== 200) throw new Error(`login failed: ${l.status} ${JSON.stringify(l.data)}`);
  return { email, password: PASSWORD, role, name: display, token: l.data.token, user: l.data.user };
}

// ── domain helpers ────────────────────────────────────────────────────────
export const jobPayload = (over = {}) => ({
  title: `E2E Backend Engineer ${Math.random().toString(36).slice(2, 7)}`,
  department: 'Engineering', location: 'Remote', type: 'Full-time',
  experience: '3-5 years', salary: '20-30 LPA',
  description: 'Build and maintain REST APIs with Python and MongoDB.',
  status: 'active', ...over,
});

export async function createJob(recruiter, over) {
  const r = await call('POST', '/jobs', { token: recruiter.token, json: jobPayload(over), expect: 201 });
  return r.data.job;
}

export async function uploadCv(candidate) {
  const form = new FormData();
  form.append('cv_file', new Blob([fs.readFileSync(await cvPdf())], { type: 'application/pdf' }), 'jane-doe-cv.pdf');
  return call('POST', '/cv/upload', { token: candidate.token, form });
}

export async function uploadIdentityCard(user) {
  const form = new FormData();
  form.append('identity_card', new Blob([fs.readFileSync(await idCardPng())], { type: 'image/png' }), 'id-card.png');
  return call('POST', '/identity-card', { token: user.token, form });
}

export const userId = (u) => u.user.id ?? u.user._id;

// Structured CV details (what the "CV details" form saves). Lets a candidate
// satisfy the "CV required to apply" rule without depending on an LLM parse.
export const cvDetails = () => ({
  salaryExpectations: { currentSalary: '1200000', expectedSalary: '1800000', currency: 'INR', negotiable: true, salaryType: 'annual' },
  positionsHeld: [{ title: 'Backend Engineer', organization: 'Acme Corp', duration: '2020-2026', responsibilities: 'Built REST APIs', achievements: 'Cut latency 40%', teamSize: '4', reportingTo: 'CTO', location: 'Remote' }],
  education: [{ degree: 'B.Tech', institution: 'Test University', year: '2018', grade: '8.5', field: 'Computer Science' }],
  experience: [{ company: 'Acme Corp', position: 'Backend Engineer', duration: '2020-2026', description: 'Python, Flask, MongoDB', location: 'Remote' }],
  skills: { technical: ['Python', 'Flask', 'MongoDB'], soft: ['Communication'] },
  projects: [{ title: 'Hiring Platform', description: 'Built a REST API for a hiring platform', technologies: 'Python, Flask', duration: '6 months', link: '' }], achievements: [], competitions: [],
});

export async function saveCvDetails(candidate) {
  return call('PUT', '/cv-details', { token: candidate.token, json: cvDetails(), expect: 200 });
}

export const randomIp = () => `10.${Math.floor(Math.random() * 250)}.${Math.floor(Math.random() * 250)}.${Math.floor(Math.random() * 250)}`;

// A logged-in admin "user" in the same shape createUser() returns.
export async function adminUser() {
  const token = await adminToken();
  const me = await call('GET', '/me', { token, expect: 200 });
  return { email: process.env.E2E_ADMIN_EMAIL, password: process.env.E2E_ADMIN_PASSWORD, role: 'admin', token, user: me.data.user || me.data };
}

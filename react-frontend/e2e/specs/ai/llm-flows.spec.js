// @ai — flows that call real LLM providers. Assertions are deliberately loose
// (shape, ranges, non-empty text): model output is not deterministic.
import { test, expect } from '@playwright/test';
import { call, createJob, createUser, saveCvDetails, uploadCv } from '../../helpers/api.js';
import { db } from '../../helpers/db.js';
import { llmStatus } from '../../helpers/ai.js';

test.describe('@ai LLM flows', () => {
  test.beforeEach(async ({}, testInfo) => { const s = await llmStatus(); testInfo.skip(!s.ok, s.reason); });

  test('AI-01 generating a job description from a short prompt returns a usable JD', async () => {
    const rec = await createUser('recruiter');
    const r = await call('POST', '/jobs/generate-ai', { token: rec.token, json: { prompt: 'Senior Python backend developer, Flask + MongoDB, remote, 5+ years' }, expect: 200 });
    const text = JSON.stringify(r.data);
    expect(text.length).toBeGreaterThan(200);
    expect(text).toMatch(/python/i);
  });

  test('AI-02 an uploaded CV is parsed into structured details', async () => {
    const cand = await createUser('candidate');
    const up = await uploadCv(cand);
    const cvId = up.data.cv.cv_id;
    await expect.poll(async () => {
      const cv = (await call('GET', `/cv/${cvId}`, { token: cand.token })).data;
      return Boolean(cv?.cv?.parsed_details || cv?.parsed_details);
    }, { timeout: 120_000, intervals: [3000] }).toBe(true);
  });

  test('AI-03 applying produces a CV score between 0 and 100 with a breakdown', async () => {
    const rec = await createUser('recruiter'); const cand = await createUser('candidate');
    const job = await createJob(rec, { title: 'Python Backend Developer', description: 'Build Flask APIs on MongoDB. 3+ years of Python required.' });
    await saveCvDetails(cand);
    const { data } = await call('POST', `/jobs/${job._id}/apply`, { token: cand.token, json: {}, expect: 201 });
    await expect.poll(async () => (await call('GET', `/applications/${data.application_id}`, { token: cand.token })).data.cv_score_breakdown, { timeout: 120_000, intervals: [3000] }).not.toBeNull();
    const app = (await call('GET', `/applications/${data.application_id}`, { token: cand.token })).data;
    expect(app.cv_score).toBeGreaterThanOrEqual(0);
    expect(app.cv_score).toBeLessThanOrEqual(100);
  });

  test('AI-04 the "check CV match score" preview scores a candidate against a job', async () => {
    const rec = await createUser('recruiter'); const cand = await createUser('candidate');
    const job = await createJob(rec);
    await saveCvDetails(cand);
    const r = await call('POST', `/jobs/${job._id}/check-cv-score`, { token: cand.token, json: {} });
    expect(r.status).toBe(200);
    expect(JSON.stringify(r.data)).toMatch(/score/i);
  });

  test('AI-05 practice interview: start, answer one question, end, get a report', async () => {
    const cand = await createUser('candidate');
    const form = new FormData(); form.append('role', 'Software Engineer'); form.append('difficulty', 'easy');
    const start = await call('POST', '/practice/start', { token: cand.token, form });
    expect(start.status, JSON.stringify(start.data)).toBe(200);
    const sessionId = start.data.session_id || start.data.interview_id;
    const question = start.data.initial_questions?.[0] || start.data.question;
    expect(sessionId).toBeTruthy();

    const answer = await call('POST', `/practice/${sessionId}/answer`, { token: cand.token, json: { question, answer: 'I have five years of Python experience building REST APIs with Flask and MongoDB.' } });
    expect(answer.status, JSON.stringify(answer.data)).toBe(200);
    const end = await call('POST', `/practice/${sessionId}/end`, { token: cand.token, json: {} });
    expect(end.status).toBe(200);
    await expect.poll(async () => (await call('GET', `/practice/${sessionId}/report`, { token: cand.token })).status, { timeout: 120_000, intervals: [3000] }).toBe(200);
    expect((await call('GET', '/practice/history', { token: cand.token })).data).toBeTruthy();
  });

  test('AI-06 real interview over the API: activate, answer, end, recruiter sees a report', async () => {
    const rec = await createUser('recruiter'); const cand = await createUser('candidate');
    const job = await createJob(rec, { title: 'AI Interview Role' });
    await saveCvDetails(cand);
    const applied = await call('POST', `/jobs/${job._id}/apply`, { token: cand.token, json: {}, expect: 201 });
    await call('PUT', `/applications/${applied.data.application_id}/status`, { token: rec.token, json: { status: 'shortlisted' }, expect: 200 });
    const start = await call('POST', '/interviews/start', { token: cand.token, json: { application_id: applied.data.application_id }, expect: 200 });
    const sessionId = start.data.session_id;

    // Face capture needs OpenCV and a real face, which is out of scope here; the
    // backend only requires the resulting field, so record that step as done.
    await (await db()).collection('interviews').updateOne({ session_id: sessionId }, { $set: { identity_verification: { status: 'skipped' } } });
    const activated = await call('POST', `/interviews/${sessionId}/activate`, { token: cand.token, json: { device_checks: { camera_ready: true, microphone_ready: true, speaker_ready: true } } });
    expect(activated.status, JSON.stringify(activated.data)).toBe(200);

    const q1 = start.data.initial_questions[0];
    const ans = await call('POST', `/interviews/${sessionId}/answer`, { token: cand.token, json: { question: q1, answer: 'I am a backend engineer with six years of Python and MongoDB experience.' } });
    expect(ans.status, JSON.stringify(ans.data)).toBe(200);
    const end = await call('POST', `/interviews/${sessionId}/end`, { token: cand.token, json: {} });
    expect(end.status).toBe(200);

    await expect.poll(async () => (await call('GET', `/applications/${applied.data.application_id}/interview-report`, { token: rec.token })).status, { timeout: 120_000, intervals: [3000] }).toBe(200);
  });
});

test.describe('@ai speech', () => {
  test('AI-07 text-to-speech and transcription', async ({}, testInfo) => {
    testInfo.skip(true, 'TTS/STT use Google Cloud Speech, and this repo ships no Google Cloud credentials (the .env has none). Add a service-account key to enable.');
  });
});

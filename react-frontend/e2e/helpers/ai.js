// Gate for the @ai specs: they only run with `npm run test:e2e:ai` AND when a
// real LLM provider actually answers. One cheap probe per worker tells us why
// not (exhausted credits, bad key, wrong model…) so the skip message is useful.
import { call, createUser } from './api.js';

let probe;
export function llmStatus() {
  // global-setup already probed (once, before the run) and shared the result
  if (process.env.E2E_LLM_STATUS) return Promise.resolve(JSON.parse(process.env.E2E_LLM_STATUS));
  return (probe ??= (async () => {
    if (process.env.E2E_AI !== '1') return { ok: false, reason: 'AI specs are off — run `npm run test:e2e:ai` to include them (spends real LLM credits).' };
    const rec = await createUser('recruiter');
    const r = await call('POST', '/jobs/generate-ai', { token: rec.token, json: { prompt: 'Backend developer' } });
    if (r.status === 200) return { ok: true };
    const detail = String(r.data?.details || r.data?.error || r.status).replace(/\s+/g, ' ');
    return { ok: false, reason: `No LLM provider answered (${r.status}). ${detail.slice(0, 400)}` };
  })());
}

// Use at the top of an ai spec: test.beforeAll(requireLlm)
export async function requireLlm({}, testInfo) {
  const s = await llmStatus();
  testInfo.skip(!s.ok, s.reason);
}

// Runs once, before any test. With --ai it probes the LLM providers here (not
// inside a test): the real call can take ~15s and the backend is a single
// process, so doing it mid-run would stall unrelated tests.
import { llmStatus } from '../helpers/ai.js';

export default async function globalSetup() {
  if (process.env.E2E_AI !== '1') return;
  const status = await llmStatus();
  process.env.E2E_LLM_STATUS = JSON.stringify(status);   // inherited by the test workers
  console.log(status.ok ? '  • LLM probe: a provider answered — @ai specs will run' : `  • LLM probe failed — @ai specs will be skipped.\n    ${status.reason}`);
}

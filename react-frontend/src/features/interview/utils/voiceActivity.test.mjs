import test from "node:test";
import assert from "node:assert/strict";
import { createVoiceTurn, voicePolicy } from "./voiceActivity.js";

test("no response sends once after ten seconds of listening", () => {
  const turn = createVoiceTurn({}, 20000);
  assert.equal(turn.sample(0, 29999).submit, false);
  assert.deepEqual(turn.sample(0, 30000), { spoke: false, submit: true, skip: true, remaining: 0, threshold: 6 });
  assert.equal(turn.sample(0, 31000).submit, false);
});
test("sustained speech followed by five seconds of silence sends answer", () => {
  const turn = createVoiceTurn({}, 0);
  for (const now of [1000, 1120, 1240, 2000]) turn.sample(12, now);
  assert.equal(turn.sample(0, 6999).submit, false);
  const result = turn.sample(0, 7000);
  assert.equal(result.submit, true); assert.equal(result.skip, false);
});
test("steady setup noise and isolated clicks do not reset silence", () => {
  const turn = createVoiceTurn({}, 0, 4);
  turn.sample(20, 1000); turn.sample(20, 1300);
  for (const now of [2000, 3000, 4000]) turn.sample(5, now);
  turn.sample(30, 5000); turn.sample(5, 5120);
  assert.equal(turn.sample(5, 6300).submit, true);
});
test("speech resumes countdown and configured settings govern each new turn", () => {
  const turn = createVoiceTurn({ silence_seconds: 7, initial_wait_seconds: 15 }, 0);
  assert.equal(turn.sample(0, 11000).submit, false);
  turn.sample(15, 12000); turn.sample(15, 12300); turn.sample(0, 13000);
  turn.sample(15, 16000); turn.sample(15, 16300);
  assert.equal(turn.sample(0, 20000).submit, false);
  assert.equal(turn.sample(0, 23300).submit, true);
  assert.equal(voicePolicy({ silence_seconds: null }).silence_seconds, 5);
  assert.equal(voicePolicy({ initial_wait_seconds: "bad" }).initial_wait_seconds, 10);
});

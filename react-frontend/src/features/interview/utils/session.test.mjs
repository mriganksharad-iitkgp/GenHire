import test from "node:test";
import assert from "node:assert/strict";
import { interviewRequest, interviewScore, isPracticeSession, mediaMimeType, microphoneLevel, mobilePairingUrl, recordingPartId, reconcileAnswer, scorePercent, socketAcknowledgement, terminalPhase } from "./session.js";

test("score contract preserves unavailable, zero and genuine low percentages", () => {
  assert.equal(scorePercent(null), null); assert.equal(scorePercent(""), null); assert.equal(scorePercent("NaN"), null);
  assert.equal(scorePercent(false), null); assert.equal(scorePercent([]), null);
  assert.equal(scorePercent(0), 0); assert.equal(scorePercent(1), 1); assert.equal(scorePercent(0.7), 1);
  assert.equal(scorePercent(101), 100); assert.equal(scorePercent(-2), 0);
  assert.equal(interviewScore({ interview_score: 0 }), 0); assert.equal(interviewScore({}), null);
});

test("practice and terminal recovery use server status including abandoned", () => {
  assert.equal(isPracticeSession({ search: "?practice=true" }), true);
  assert.equal(isPracticeSession({ search: "" }, { is_practice: true }), true);
  assert.equal(isPracticeSession({ search: "" }), false);
  assert.equal(terminalPhase({ status: "abandoned" }), "discarded");
  assert.equal(terminalPhase({ status: "interview_ended" }), "completed");
  assert.equal(terminalPhase({ status: "active" }), null);
});

test("reconcile an accepted POST after timeout instead of resubmitting against next question", () => {
  assert.deepEqual(reconcileAnswer({ current_question: "Q2", question_count: 2 }, "Q1", "A1"), { accepted: true, question: "Q2", questionCount: 2 });
  assert.equal(reconcileAnswer({ current_question: "Q1", last_answer: { question: "Q1", answer: "A1" } }, "Q1", "A1").accepted, true);
  assert.equal(reconcileAnswer({ current_question: "Q1", last_answer: { question: "Q1", answer: "Different" } }, "Q1", "A1").accepted, false);
  assert.deepEqual(reconcileAnswer({ status: "completed" }, "Q1", "A1"), { accepted: true, terminal: "completed" });
  assert.deepEqual(reconcileAnswer({ status: "finishing", last_answer: { question: "Q1", answer: "A1", result: { interview_complete: true } } }, "Q1", "A1"), { accepted: true, finish: true });
});

test("companion link includes private signed token and encoded session; no token has no link", () => {
  assert.equal(mobilePairingUrl({ session_id: "123" }, "https://genhire.test"), "");
  const url = new URL(mobilePairingUrl({ session_id: "a/b", mobile_pairing_token: "signed.token" }, "https://genhire.test"));
  assert.equal(url.pathname, "/mobile-camera/a%2Fb"); assert.equal(url.searchParams.get("pairing_token"), "signed.token");
});

test("recording retry part identifiers are URL safe, bounded and distinct", () => {
  const values = new Set(Array.from({ length: 100 }, recordingPartId)); assert.equal(values.size, 100);
  for (const value of values) assert.match(value, /^[A-Za-z0-9_-]{1,64}$/);
});

test("microphone check requires captured audio energy; silence stays zero", () => {
  assert.equal(microphoneLevel(new Uint8Array(1024).fill(128)), 0);
  assert.ok(microphoneLevel(new Uint8Array([138, 118, 140, 116])) >= 4);
  assert.equal(microphoneLevel(new Uint8Array()), 0);
});

test("recording chooses formats supported by the browser including Safari MP4", () => {
  assert.equal(mediaMimeType("audio", { isTypeSupported: (type) => type === "audio/mp4" }), "audio/mp4");
  assert.equal(mediaMimeType("video", { isTypeSupported: (type) => type === "video/mp4" }), "video/mp4");
  assert.equal(mediaMimeType("audio", null), "");
});

test("monitoring readiness requires successful server acknowledgement", async () => {
  await assert.rejects(socketAcknowledgement({ connected: false }, "start", {}), /reconnecting/);
  const success = { connected: true, emit: (event, payload, ack) => ack({ ok: true, session_status: "active" }) };
  assert.equal((await socketAcknowledgement(success, "start", {})).session_status, "active");
  const denied = { connected: true, emit: (event, payload, ack) => ack({ ok: false, error_code: "unauthorized_session" }) };
  await assert.rejects(socketAcknowledgement(denied, "start", {}), (failure) => failure.code === "unauthorized_session");
  await assert.rejects(socketAcknowledgement({ connected: true, emit() {} }, "start", {}, 5), /did not respond/);
});

test("REST recovery keeps server session identifier and error code", async (context) => {
  context.mock.method(globalThis, "fetch", async () => ({ ok: false, status: 409, json: async () => ({ error: "Resume session", error_code: "session_recovery_required", session_id: "existing" }) }));
  await assert.rejects(interviewRequest("/api", "/start", "token"), (failure) => failure.status === 409 && failure.details.session_id === "existing" && failure.code === "session_recovery_required");
});

test("JSON and recording requests keep correct content type and auth", async (context) => {
  const calls = []; context.mock.method(globalThis, "fetch", async (url, options) => { calls.push({ url, options }); return { ok: true, json: async () => ({ ok: true }) }; });
  await interviewRequest("/api", "/activate", "owner", { method: "POST", body: JSON.stringify({ camera_ready: true }) });
  await interviewRequest("/api", "/upload", null, { method: "POST", body: new FormData(), headers: { "X-Mobile-Pairing-Token": "signed" } });
  assert.equal(calls[0].options.headers.Authorization, "Bearer owner"); assert.equal(calls[0].options.headers["Content-Type"], "application/json");
  assert.equal(calls[1].options.headers["Content-Type"], undefined); assert.equal(calls[1].options.headers["X-Mobile-Pairing-Token"], "signed");
});

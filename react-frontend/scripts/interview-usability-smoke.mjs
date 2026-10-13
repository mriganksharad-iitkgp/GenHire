// Real components with isolated API, socket and media fixtures. No accounts,
// providers, cameras or billable interviews are used by these checks.
import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "esbuild";
import { JSDOM } from "jsdom";

const cwd = process.cwd();
const tmp = await mkdtemp(path.join(cwd, ".interview-ui-"));
assert.ok(path.resolve(tmp).startsWith(path.resolve(cwd) + path.sep));
const { window: win } = new JSDOM('<html><body><div id="root"></div></body></html>', { url: "http://localhost:3000", pretendToBeVisual: true });
for (const key of ["window", "document", "navigator", "sessionStorage", "localStorage", "HTMLElement", "Element", "Node", "Event", "MouseEvent", "getComputedStyle"]) {
  Object.defineProperty(globalThis, key, { value: key === "window" ? win : win[key], configurable: true, writable: true });
}
globalThis.FileReader = class {
  readAsDataURL(blob) { blob.arrayBuffer().then(bytes => { this.result = `data:${blob.type};base64,${Buffer.from(bytes).toString("base64")}`; this.onload?.(); }).catch(() => this.onerror?.()); }
};
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
win.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
win.scrollTo = () => {};
win.document.documentElement.requestFullscreen = async () => {
  Object.defineProperty(document, "fullscreenElement", { configurable: true, get: () => document.documentElement });
};
win.document.exitFullscreen = async () => { delete document.fullscreenElement; };
Object.defineProperty(win.HTMLVideoElement.prototype, "videoWidth", { get: () => 640 });
Object.defineProperty(win.HTMLVideoElement.prototype, "videoHeight", { get: () => 480 });
Object.defineProperty(win.HTMLVideoElement.prototype, "currentTime", { get: () => performance.now() / 1000 });
Object.defineProperty(win.HTMLMediaElement.prototype, "readyState", { get: () => 4 });
win.HTMLMediaElement.prototype.play = async () => {};
win.HTMLCanvasElement.prototype.getContext = () => ({ drawImage() {} });
win.HTMLCanvasElement.prototype.toDataURL = () => "data:image/jpeg;base64,Zml4dHVyZQ==";

const React = await import("react");
const { act } = React;
const { createRoot } = await import("react-dom/client");
const { MemoryRouter, Routes, Route, useLocation } = await import("react-router-dom");
const e = React.createElement;
const log = console.log, logError = console.error;
console.log = () => {};
let renderErrors = [];
console.error = (...args) => renderErrors.push(args.map(String).join(" "));
let root, compiled, currentLocation, passes = 0;
let apiCalls, dualRequired, micSound, recordings, currentStream, socket, serverStatus;
let speechFailure, reportPending, answerFailure, uploadFailure, applicationsFailure, applicationStatus, applicationProcessingStatus, pairingVersion;
let mediaRequests, mediaFailure, audioSuspended, identityCaptured, socketEvents;
let fixtureQuestionNumber = 1, holdQuestionAudio = false, playingAudio;
let detectedFaces = [], detectionUnavailable = false;
globalThis.__faceDetectorFixture = {
  FilesetResolver: { forVisionTasks: async () => ({}) },
  FaceDetector: { createFromOptions: async () => {
    if (detectionUnavailable) throw new Error("fixture unavailable");
    return { detectForVideo: () => ({ detections: detectedFaces }), close() {} };
  } },
};
const now = Date.now;

function track(kind) { return { kind, readyState: "live", muted: false, onended: null, stop() { this.readyState = "ended"; }, getSettings: () => ({ sampleRate: 48000 }) }; }
class FixtureStream {
  constructor(tracks = [track("video"), track("audio")]) { this.tracks = tracks; }
  getTracks() { return this.tracks; }
  getVideoTracks() { return this.tracks.filter(item => item.kind === "video"); }
  getAudioTracks() { return this.tracks.filter(item => item.kind === "audio"); }
}
class FixtureRecorder extends win.EventTarget {
  static isTypeSupported(type) { return type.includes("webm"); }
  constructor(stream, options = {}) { super(); this.mimeType = options.mimeType || "audio/webm"; this.state = "inactive"; recordings.push(this); }
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["fixture"], { type: this.mimeType }) });
    this.onstop?.(); this.dispatchEvent(new win.Event("stop"));
  }
}
class FixtureAudioContext {
  state = audioSuspended ? "suspended" : "running"; currentTime = 0; destination = {};
  resume = async () => { if (!audioSuspended) this.state = "running"; }; close = async () => {};
  createAnalyser() { const context = this; return { fftSize: 1024, getByteTimeDomainData(samples) { samples.fill(micSound && context.state === "running" ? 133 : 128); } }; }
  createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
  createOscillator() { return { connect() {}, frequency: {}, start() {}, stop() {} }; }
  audioWorklet = { addModule: async () => {} };
  createGain() { return { connect() {}, disconnect() {}, gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} } }; }
}
class FixturePCMNode {
  port = { onmessage: null, postMessage: message => { if (message.type === "flush") this.port.onmessage?.({ data: { type: "flushed" } }); } };
  connect() {} disconnect() {}
}
globalThis.AudioWorkletNode = win.AudioWorkletNode = FixturePCMNode;
globalThis.MediaStream = win.MediaStream = FixtureStream;
globalThis.MediaRecorder = win.MediaRecorder = FixtureRecorder;
win.AudioContext = FixtureAudioContext;
globalThis.Audio = win.Audio = class {
  currentTime = 0;
  async play() { playingAudio = this; this.onplaying?.(); if (holdQuestionAudio) return; this.timer = setTimeout(() => { this.currentTime = .05; this.onended?.(); }, 25); }
  pause() { clearTimeout(this.timer); }
};
Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { async getUserMedia() { mediaRequests++; if (mediaFailure) throw new win.DOMException("Permission denied", "NotAllowedError"); currentStream = new FixtureStream(); return currentStream; } } });
globalThis.__interviewTestSocket = () => {
  const handlers = new Map();
  socket = { connected: true, on(name, fn) { handlers.set(name, [...(handlers.get(name) || []), fn]); return this; }, off(name, fn) { handlers.set(name, (handlers.get(name) || []).filter(item => item !== fn)); return this; }, emit(name, payload, ack) { socketEvents.push({ name, payload }); ack?.({ ok: true }); return this; }, disconnect() { this.connected = false; }, connect() { this.connected = true; queueMicrotask(() => socket.fire("connect")); }, fire(name, data) { (handlers.get(name) || []).forEach(fn => fn(data)); } };
  queueMicrotask(() => socket.fire("connect"));
  return socket;
};
function sessionPayload() {
  return { session_id: "ui-session", current_question: "Describe a recent project.", max_questions: 12, question_count: fixtureQuestionNumber,
    engine_available: true, identity_captured: identityCaptured, dual_proctoring_required: dualRequired,
    mobile_pairing_token: `fixture-pairing-${pairingVersion}`, question_timeout_seconds: 300, status: serverStatus };
}
globalThis.fetch = win.fetch = async (url, options = {}) => {
  apiCalls.push({ url: String(url), options });
  const pathname = new URL(String(url), "http://localhost:5000").pathname;
  let data = {}, status = 200;
  if (pathname.endsWith("/session")) data = sessionPayload();
  if (pathname.endsWith("/transcribe")) data = { transcript: "I built a reliable Python service." };
  if (pathname.endsWith("/synthesize")) data = speechFailure ? {} : { audio_base64: "ZmFrZQ==", timepoints: [{ time_seconds: 0, char_end: 8 }] };
  if (pathname.endsWith("/activate")) { serverStatus = "active"; data = { current_question: "Describe a recent project.", question_deadline: Date.now() / 1000 + 300 }; }
  if (pathname.endsWith("/answer")) {
    status = answerFailure ? 503 : 200;
    data = answerFailure ? { error: "Temporary answer service failure" } : fixtureQuestionNumber === 12 ? { interview_complete: true } : { next_question: "What did you learn?", progress: { questions_asked: 1 }, question_deadline: Date.now() / 1000 + 300 };
  }
  if (pathname.endsWith("/end")) { data = serverStatus === "terminated" ? { status: "interview_terminated", message: "The monitoring policy ended this attempt. You cannot repeat this interview for the same application." } : { status: "completed", interview_score: 0, cv_score: 0, proctoring_score: 0 }; serverStatus = data.status; }
  if (pathname.endsWith("/end") && reportPending) { reportPending = false; data = {status:"finishing",report_pending:true}; status = 202; }
  if (pathname.endsWith("/upload-recording")) status = uploadFailure ? 503 : 200;
  if (pathname.endsWith("/applications")) {
    status = applicationsFailure ? 503 : 200;
    data = [{ _id: "ui-application", job_title: "Fixture Engineer", status: applicationStatus, processing_status: applicationProcessingStatus, applied_at: "2026-10-01T00:00:00Z",
      report_available: applicationStatus === "interviewed", job_details: { company: "Fixture Company", type: "Full-time" } }];
  }
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
};
function Probe() { currentLocation = useLocation(); return null; }
function text() { return document.body.textContent; }
function button(label, scope = document) { return [...scope.querySelectorAll("button")].find(node => node.textContent.trim() === label); }
async function settle(ms = 60) { await act(async () => { await new Promise(resolve => setTimeout(resolve, ms)); }); }
async function click(node) { assert.ok(node, "Expected clickable control"); await act(async () => node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }))); await settle(); }
async function keyboard(key, shiftKey = false) { await act(async () => document.dispatchEvent(new win.KeyboardEvent("keydown", { key, shiftKey, bubbles: true, cancelable: true }))); await settle(); }
async function mount(component, options = {}) {
  if (root) await act(async () => root.unmount());
  Date.now = now; renderErrors = []; apiCalls = []; dualRequired = options.dual || false; micSound = true; recordings = [];
  speechFailure = !!options.speechFailure; reportPending = false; serverStatus = "setup"; answerFailure = false; uploadFailure = false; applicationsFailure = false; applicationStatus = "shortlisted"; applicationProcessingStatus = options.processingStatus || "completed"; pairingVersion = 1;
  fixtureQuestionNumber = options.questionNumber || 1; holdQuestionAudio = !!options.holdAudio; playingAudio = null;
  mediaRequests = 0; mediaFailure = options.mediaFailure || false; audioSuspended = options.audioSuspended || false; identityCaptured = options.identityCaptured !== false; socketEvents = [];
  detectedFaces = options.faces || []; detectionUnavailable = options.detectionUnavailable || false;
  sessionStorage.clear(); sessionStorage.setItem("companyxyz-token", "fixture-token");
  sessionStorage.setItem("companyxyz-user", JSON.stringify({ user_type: "candidate", userType: "candidate" }));
  root = createRoot(document.getElementById("root"));
  await act(async () => root.render(e(compiled.AppProviders, null, e(MemoryRouter, { initialEntries: [options.path || "/interviews/ui-session"] }, e(Probe), component))));
  await settle();
}
async function activeInterview(options = {}) {
  await mount(e(compiled.Chat, { interviewId: "ui-session" }), options);
  await settle(180); assert.equal(mediaRequests, 1);
  await click(button("Continue")); await click(button("I heard the sound", document.querySelector('[role="dialog"]')));
  if (options.dual) { await act(async () => socket.fire("mobile_status_dashboard", { ready: true, status: "connected" })); assert.ok(button("Continue"), text() + "\n" + renderErrors.join("\n")); await click(button("Continue")); }
  await click(document.querySelector('input[type="checkbox"]'));
  micSound = false; await settle(750); await click(button("Start interview"));
  assert.ok(document.querySelector('[aria-label="Interview conversation"]'));
}
async function check(name, fn) {
  await fn();
  assert.equal(renderErrors.filter(message => !message.includes("not wrapped in act")).length, 0, renderErrors.join("\n"));
  passes++; log(`PASS ${name}`);
}
try {
  const exports = { KioskLaunchGuide: "features/interview/components/KioskLaunchGuide", Chat: "features/interview/pages/Chat", MobileRecorder: "features/interview/pages/MobileRecorder", Applications: "features/candidate/pages/Applications", Modal: "shared/components/ui/Modal", ConfirmDialog: "shared/components/ui/ConfirmDialog", InterviewReportModal: "features/interview/components/InterviewReportModal", AppProviders: "app/providers" };
  const entry = Object.entries(exports).map(([name, file]) => `export {${name === "AppProviders" ? name : "default as " + name}} from ${JSON.stringify(file)};`).join("\n");
  const output = await build({ stdin: { contents: entry, resolveDir: cwd, loader: "jsx" }, bundle: true, write: false,
    outfile: path.join(tmp, "bundle.mjs"), platform: "node", format: "esm", packages: "external",
    alias: Object.fromEntries(["app", "features", "shared", "assets"].map(name => [name, path.join(cwd, "src", name)])),
    loader: { ".js": "jsx", ".png": "dataurl", ".svg": "dataurl", ".jpg": "dataurl" },
    define: { "process.env": JSON.stringify({ NODE_ENV: "test", REACT_APP_API_URL: "http://localhost:5000" }) },
    plugins: [{ name: "socket-fixture", setup(plugin) {
      plugin.onResolve({ filter: /^socket.io-client$/ }, () => ({ path: "socket", namespace: "fixture" }));
      plugin.onLoad({ filter: /.*/, namespace: "fixture" }, () => ({ contents: "export const io=(...args)=>globalThis.__interviewTestSocket(...args);export default io;", loader: "js" }));
      plugin.onResolve({ filter: /^@mediapipe\/tasks-vision$/ }, () => ({ path: "face-detector", namespace: "face-fixture" }));
      plugin.onLoad({ filter: /.*/, namespace: "face-fixture" }, () => ({ contents: "export const {FaceDetector,FilesetResolver}=globalThis.__faceDetectorFixture;", loader: "js" }));
      // Native Node imports the CJS wrapper; Vite unwraps its default export.
      // The named export is the same real QR component, not a visual stub.
      plugin.onResolve({ filter: /^react-qr-code$/ }, args => args.namespace === "qr-interop" ? { path: args.path, external: true } : { path: args.path, namespace: "qr-interop" });
      plugin.onLoad({ filter: /.*/, namespace: "qr-interop" }, () => ({ contents: 'export {QRCode as default} from "react-qr-code";', loader: "js" }));
    } }] });
  await writeFile(path.join(tmp, "bundle.mjs"), output.outputFiles.find(file => file.path.endsWith(".mjs")).text);
  compiled = await import(pathToFileURL(path.join(tmp, "bundle.mjs")));
  const style = document.createElement("style");
  style.textContent = (await readFile("src/shared/styles/portal-theme.css", "utf8")) + output.outputFiles.find(file => file.path.endsWith(".css")).text;
  document.head.appendChild(style);

  await check("launch guide preserves installation help but closes on return from the secure browser", async () => {
    localStorage.setItem("genhire:kiosk-installed:v1", "confirmed");
    let closed = 0;
    await mount(e(compiled.KioskLaunchGuide, { isOpen: true, onClose: () => closed++, onOpen: () => window.dispatchEvent(new Event("genhire:kiosk-launch")) }));
    await act(async () => { window.dispatchEvent(new Event("blur")); window.dispatchEvent(new Event("focus")); });
    assert.equal(closed, 0, "Installation help must remain open before launch");
    await click(button("Open Secure Browser"));
    await act(async () => { window.dispatchEvent(new Event("blur")); window.dispatchEvent(new Event("focus")); });
    assert.equal(closed, 1);
    assert.equal(sessionStorage.getItem("companyxyz-token"), "fixture-token");
  });
  await check("launch failures stay recoverable in the guide", async () => {
    await mount(e(compiled.KioskLaunchGuide, { isOpen: true, onClose: () => {}, onOpen: () => { throw new Error("launch failure"); } }));
    await click(button("Open Secure Browser"));
    assert.ok(text().includes("The secure browser could not open"));
    assert.ok(!button("Open Secure Browser").disabled);
  });
  await check("automatic device permission leads through speaker confirmation and face capture without a hidden Continue gate", async () => {
    await mount(e(compiled.Chat, { interviewId: "ui-session" }), { identityCaptured: false }); await settle(180);
    assert.equal(mediaRequests, 1); assert.ok(!button("Enable camera and microphone")); assert.ok(!button("Continue").disabled);
    assert.ok(text().includes("Continue to confirm your speakers")); await click(button("Continue"));
    assert.ok(document.querySelector('[role="dialog"]')); assert.ok(text().includes("Can you hear the test sound?"));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/activate")).length, 0);
    await click(button("I heard the sound", document.querySelector('[role="dialog"]')));
    assert.ok(button("Take photo manually")); await click(button("Take photo manually"));
    assert.ok(text().includes("Review your photo"));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/register-face")).length, 0);
    await click(button("Use photo and continue"));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/register-face")).length, 1);
    await click(document.querySelector('input[type="checkbox"]')); micSound = false; await click(button("Start interview"));
    const activation = apiCalls.find(call => call.url.endsWith("/activate"));
    assert.deepEqual(JSON.parse(activation.options.body), { camera_ready: true, microphone_ready: true, speaker_ready: true });
  });
  await check("a centered face is captured automatically, can be retaken, and uploads only after confirmation", async () => {
    const centered = { boundingBox: { originX: 210, originY: 100, width: 200, height: 220 } };
    await mount(e(compiled.Chat, { interviewId: "ui-session" }), { identityCaptured: false, faces: [centered] }); await settle(180);
    await click(button("Continue")); await click(button("I heard the sound", document.querySelector('[role="dialog"]')));
    await settle(1700);
    assert.ok(text().includes("Review your photo")); assert.ok(document.querySelector('img[alt="Your captured face"]'));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/register-face")).length, 0);
    await click(button("Retake photo")); assert.ok(text().includes("Center your face in the preview"));
    detectedFaces = [centered, centered]; await settle(500); assert.ok(text().includes("Only you should be visible"));
    assert.ok(!button("Use photo and continue")); detectedFaces = [centered]; await settle(1700);
    await click(button("Use photo and continue"));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/register-face")).length, 1);
    assert.ok(button("Start interview"));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/speech/synthesize")).length, 1);
  });
  await check("unavailable local detection keeps a manual photo and retake path", async () => {
    await mount(e(compiled.Chat, { interviewId: "ui-session" }), { identityCaptured: false, detectionUnavailable: true }); await settle(180);
    await click(button("Continue")); await click(button("I heard the sound", document.querySelector('[role="dialog"]')));
    assert.ok(text().includes("Automatic capture is unavailable")); assert.ok(!button("Take photo manually").disabled);
    await click(button("Take photo manually")); await click(button("Retake photo")); await click(button("Take photo manually"));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/register-face")).length, 0);
    await click(button("Use photo and continue")); assert.ok(button("Start interview"));
  });
  await check("permission denial offers an explicit retry without repeated automatic popups", async () => {
    await mount(e(compiled.Chat, { interviewId: "ui-session" }), { mediaFailure: true }); await settle(180);
    assert.equal(mediaRequests, 1); assert.ok(text().includes("permission was denied")); assert.ok(button("Continue").disabled);
    mediaFailure = false; await click(button("Retry device checks")); await settle(180);
    assert.equal(mediaRequests, 2); assert.ok(!button("Continue").disabled);
  });
  await check("losing a device during speaker confirmation keeps setup blocked and permits recovery", async () => {
    await mount(e(compiled.Chat, { interviewId: "ui-session" })); await settle(180); await click(button("Continue"));
    await act(async () => { const camera = currentStream.getVideoTracks()[0]; camera.stop(); camera.onended(); }); await settle();
    const dialog = document.querySelector('[role="dialog"]'); assert.ok(button("I heard the sound", dialog).disabled);
    assert.ok(dialog.textContent.includes("A device was disconnected"));
    await click(button("Back to device checks", dialog)); await click(button("Retry device checks")); await settle(180);
    await click(button("Continue")); await click(button("I heard the sound", document.querySelector('[role="dialog"]')));
    assert.ok(button("Start interview")); assert.equal(apiCalls.filter(call => call.url.endsWith("/activate")).length, 0);
  });
  await check("a suspended audio context releases the busy state and can be resumed by checking the microphone", async () => {
    await mount(e(compiled.Chat, { interviewId: "ui-session" }), { audioSuspended: true }); await settle(180);
    assert.ok(button("Continue").disabled); assert.ok(button("Check microphone")); assert.ok(!button("Retry device checks").disabled);
    audioSuspended = false; await click(button("Check microphone")); await settle(180);
    assert.ok(!button("Continue").disabled); assert.equal(mediaRequests, 1);
  });
  await check("a required phone cannot be skipped before server-confirmed camera readiness", async () => {
    await mount(e(compiled.Chat, { interviewId: "ui-session" }), { dual: true }); await settle(180);
    await click(button("Continue")); await click(button("I heard the sound", document.querySelector('[role="dialog"]')));
    assert.ok(text().includes("Waiting for your phone")); assert.ok(button("Continue").disabled); assert.ok(document.querySelector("svg"));
    await act(async () => socket.fire("mobile_status_dashboard", { ready: false, status: "connected" }));
    assert.ok(button("Continue").disabled); assert.equal(apiCalls.filter(call => call.url.endsWith("/activate")).length, 0);
    await act(async () => socket.fire("mobile_status_dashboard", { ready: true, status: "connected" }));
    await click(button("Continue")); assert.ok(button("Start interview"));
  });
  await check("the signed phone companion automatically requests devices after joining and reports live tracks", async () => {
    await mount(e(Routes, null, e(Route, { path: "/mobile-camera/:sessionId", element: e(compiled.MobileRecorder) })), { path: "/mobile-camera/ui-session?pairing_token=fixture-pairing" }); await settle(180);
    assert.equal(mediaRequests, 1); assert.ok(text().includes("Your second camera is ready")); assert.ok(!button("Enable camera and microphone"));
    const joining = socketEvents.find(event => event.name === "join_mobile_session");
    assert.equal(joining.payload.pairing_token, "fixture-pairing");
    const ready = socketEvents.find(event => event.name === "mobile_status_update" && event.payload.status === "ready");
    assert.equal(ready.payload.camera_ready, true); assert.equal(ready.payload.microphone_ready, true);
    await settle(1050); assert.ok(socketEvents.some(event => event.name === "mobile_proctoring_frame"));
  });

  await check("phone camera recovery restarts recording and uploads both retained parts", async () => {
    await mount(e(Routes, null, e(Route, { path: "/mobile-camera/:sessionId", element: e(compiled.MobileRecorder) })), { path: "/mobile-camera/ui-session?pairing_token=fixture-pairing" }); await settle(180);
    await act(async () => socket.fire("mobile_recording_action", { action: "start" }));
    assert.equal(recordings.length, 1); assert.equal(recordings[0].state, "recording");
    const lostTrack = currentStream.getVideoTracks()[0]; lostTrack.muted = true;
    await act(async () => lostTrack.onmute());
    await click(button("Retry camera and microphone"));
    assert.equal(recordings[0].state, "inactive"); assert.equal(recordings.length, 2);
    assert.equal(recordings[1].state, "recording"); assert.equal(mediaRequests, 2);
    await act(async () => socket.fire("mobile_recording_action", { action: "stop" })); await settle(120);
    assert.equal(apiCalls.filter(call => call.url.endsWith("/upload-mobile-recording")).length, 2);
    assert.ok(text().includes("Recording saved"));
  });
  await check("unavailable question audio stays visible until the candidate retries or chooses text", async () => {
    await activeInterview({ speechFailure: true });
    assert.ok(button("Play question")); assert.ok(button("Send answer").disabled);
    assert.equal(socketEvents.filter(event => event.name === "speech_live_start").length, 0);
    speechFailure = false; await click(button("Play question"));
    assert.ok(socketEvents.some(event => event.name === "speech_live_start"));
  });
  await check("a slow report is polled with JSON until persisted completion", async () => {
    await activeInterview(); reportPending = true;
    await click(button("End interview")); await click(button("Finish interview", document.querySelector('[role="dialog"]')));
    await settle(2150);
    const requests = apiCalls.filter(call => call.url.endsWith("/end"));
    assert.equal(requests.length, 2); assert.equal(requests[0].options.body, "{}");
    assert.ok(text().includes("Interview complete"));
  });
  await check("voice-only conversation shows live captions and final spoken answers", async () => {
    await activeInterview(); assert.ok(!button("Type answer")); assert.ok(!document.querySelector("textarea"));
    const live = socketEvents.find(event => event.name === "speech_live_start"); assert.ok(live);
    await act(async () => socket.fire("speech_live_transcript", { stream_id: live.payload.stream_id, transcript: "I built a reliable" }));
    assert.ok(text().includes("I built a reliable")); micSound = true; await settle(600); micSound = false;
    await click(button("Send answer"));
    const submitted = apiCalls.find(call => call.url.endsWith("/answer")); assert.ok(submitted, text());
    assert.equal(JSON.parse(submitted.options.body).answer, "I built a reliable Python service.");
    assert.ok(text().includes("What did you learn?")); assert.ok(text().includes("I built a reliable Python service."));
  });
  await check("ten seconds without speech advances without invoking transcription", async () => {
    await activeInterview(); const began = now(); Date.now = () => began + 10100;
    await settle(200);
    const submitted = apiCalls.find(call => call.url.endsWith("/answer"));
    assert.ok(submitted, text()); assert.equal(JSON.parse(submitted.options.body).answer, "");
    assert.equal(apiCalls.filter(call => call.url.endsWith("/transcribe")).length, 0);
  });
  await check("five seconds after sustained speech submits once and asks the next question", async () => {
    await activeInterview(); micSound = true; await settle(600); micSound = false;
    const stopped = now(); Date.now = () => stopped + 5100; await settle(220);
    const submitted = apiCalls.filter(call => call.url.endsWith("/answer"));
    assert.equal(submitted.length, 1, text());
    assert.equal(JSON.parse(submitted[0].options.body).answer, "I built a reliable Python service.");
    assert.ok(text().includes("What did you learn?"));
  });
  await check("question twelve waits for audio completion and saves the answer before ending", async () => {
    await activeInterview({ questionNumber: 12, holdAudio: true });
    assert.ok(text().includes("Question 12 of 12"));
    const began = now(); playingAudio.currentTime = 40; Date.now = () => began + 40000; await settle(200);
    assert.equal(apiCalls.filter(call => call.url.endsWith("/answer")).length, 0);
    await act(async () => playingAudio.onended()); await settle();
    assert.ok(text().includes("Start speaking within 10s"));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/end")).length, 0);
    const live = socketEvents.find(event => event.name === "speech_live_start");
    await act(async () => socket.fire("speech_live_transcript", { stream_id: live.payload.stream_id, transcript: "I built a reliable Python service" }));
    await settle(200); Date.now = () => began + 44000; await settle(200);
    assert.equal(apiCalls.filter(call => call.url.endsWith("/answer")).length, 0);
    await click(button("Send answer"));
    assert.equal(JSON.parse(apiCalls.find(call => call.url.endsWith("/answer")).options.body).answer, "I built a reliable Python service.");
    assert.equal(apiCalls.filter(call => call.url.endsWith("/end")).length, 1);
    assert.ok(text().includes("Interview complete"));
  });
  await check("reports pair candidate answers with preparation examples and support older reports", async () => {
    await mount(e(compiled.InterviewReportModal, { isOpen: true, onClose() {}, report: { interview_score: 0, evaluation: {
      per_question_evaluations: [{ question_number: 1, question: "Why this job?", answer: "", suggested_answer: "My Python project relates to this role. [add your actual result]", improvement_tip: "Explain your motivation." },
        { question: "How do you collaborate?", answer: "We worked together." }], qualitative_assessment: "Review your answers." } } }));
    assert.ok(text().includes("A stronger answer to practice"));
    assert.ok(text().includes("[add your actual result]"));
    assert.ok(text().includes("No answer provided"));
    assert.ok(text().includes("Suggested answers were not generated for this older report."));
  });
  await check("a failed spoken submission keeps the exact final transcript for retry", async () => {
    await activeInterview(); micSound = true; await settle(600); micSound = false; answerFailure = true;
    await click(button("Send answer")); assert.ok(button("Send saved answer"));
    answerFailure = false; await click(button("Send saved answer"));
    const answers = apiCalls.filter(call => call.url.endsWith("/answer")); assert.equal(answers.length, 2);
    assert.equal(answers[0].options.body, answers[1].options.body);
  });
  await check("phone monitoring gaps warn without blocking or ending the voice interview", async () => {
    await activeInterview({ dual: true });
    await act(async () => socket.fire("mobile_disconnected")); await settle();
    assert.ok(!text().includes("Reconnect your devices")); assert.ok(text().includes("Phone monitoring was interrupted"));
    assert.ok(document.querySelector('[aria-label="Interview voice activity"]'));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/end")).length, 0);
    assert.ok(recordings.some(recorder => recorder.state === "recording"));
  });
  await check("a disconnected laptop retains its spoken recording and can resume", async () => {
    await activeInterview(); micSound = true; await settle(600); micSound = false;
    await act(async () => { currentStream.getVideoTracks()[0].stop(); currentStream.getVideoTracks()[0].onended(); }); await settle();
    assert.ok(button("Resume interview").disabled); micSound = true;
    await click(button("Retry device checks")); await settle(180); micSound = false;
    await click(button("Resume interview")); assert.ok(!text().includes("Reconnect your devices"));
    assert.ok(button("Send saved answer")); assert.ok(!document.querySelector("textarea"));
  });
  await check("warnings dismiss after 1.8 seconds while counts remain visible", async () => {
    await activeInterview();
    await act(async () => socket.fire("proctoring_alert", { type: "head_turn", source: "desktop", message: "Keep your face visible." }));
    assert.ok(text().includes("Look toward the interview screen.")); await settle(1900);
    assert.ok(!text().includes("Look toward the interview screen."));
  });
  await check("more than five recorded interruptions never automatically end or pause", async () => {
    await activeInterview();
    await act(async () => socket.fire("interview_integrity", { session_id: "ui-session", count: 8,
      counts_by_type: { tab_switch: 6, mobile_unavailable: 2 }, auto_termination: false,
      losses: { mobile: { message: "Phone monitoring stopped." } } })); await settle();
    assert.ok(text().includes("Recorded interruptions8")); assert.ok(!text().includes("Reconnect your devices"));
    assert.ok(!text().includes("of 5")); assert.equal(apiCalls.filter(call => call.url.endsWith("/end")).length, 0);
  });
  await check("failed recording uploads warn before closing and offer themed leave or retry", async () => {
    await activeInterview(); micSound = true; await settle(600); micSound = false; await click(button("Send answer"));
    uploadFailure = true; await click(button("End interview")); await click(button("Finish interview")); await settle();
    assert.ok(text().includes("recording upload failed"));
    const leaving = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(leaving); assert.equal(leaving.defaultPrevented, true);
    await click(button("Back to applications")); assert.ok(text().includes("Leave without uploading the recording?")); await click(button("Cancel"));
    uploadFailure = false; await click(button("Retry upload")); assert.ok(text().includes("Your recording was saved"));
    const safe = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(safe); assert.equal(safe.defaultPrevented, false);
    assert.equal(currentLocation.pathname, "/interviews/ui-session");
  });
  await check("confirmation focus stays inside and returns to the trigger; busy dialogs cannot dismiss", async () => {
    function Harness() {
      const [open, setOpen] = React.useState(false); const [busy, setBusy] = React.useState(false);
      return e("div", null, e("button", { onClick: () => setOpen(true) }, "Open confirmation"),
        e(compiled.ConfirmDialog, { isOpen: open, title: "Confirm action", message: "Keep your changes.", isLoading: busy, onClose: () => setOpen(false), onConfirm: () => setBusy(true) }));
    }
    await mount(e(Harness)); const trigger = button("Open confirmation"); trigger.focus(); await click(trigger);
    const dialog = document.querySelector('[role="dialog"]'); assert.equal(document.activeElement, dialog); assert.equal(document.body.style.overflow, "hidden");
    await keyboard("Tab", true); assert.equal(document.activeElement, button("Confirm"));
    await keyboard("Tab"); assert.equal(document.activeElement, document.querySelector('[aria-label="Close dialog"]'));
    await keyboard("Escape"); assert.ok(!document.querySelector('[role="dialog"]')); assert.equal(document.activeElement, trigger); assert.equal(document.body.style.overflow, "");
    await click(trigger); await click(button("Confirm")); await keyboard("Escape");
    await click(document.querySelector('[role="dialog"]').parentElement); assert.ok(document.querySelector('[role="dialog"]'));
  });
  await check("nested confirmations only close the top dialog and remain visible in fullscreen", async () => {
    function Harness() {
      const [child, setChild] = React.useState(false);
      return e(compiled.Modal, { isOpen: true, closeOnEsc: false, ariaLabel: "Parent" },
        e("button", { onClick: () => setChild(true) }, "Open child"),
        e(compiled.ConfirmDialog, { isOpen: child, title: "Child", onClose: () => setChild(false), onConfirm() {} }));
    }
    const full = document.createElement("div"); document.body.appendChild(full);
    Object.defineProperty(document, "fullscreenElement", { configurable: true, get: () => full });
    await mount(e(Harness)); button("Open child").focus(); await click(button("Open child")); assert.equal(full.querySelectorAll('[role="dialog"]').length, 2);
    await keyboard("Escape"); assert.equal(full.querySelectorAll('[role="dialog"]').length, 1); assert.equal(document.activeElement.textContent, "Open child");
    assert.equal(document.body.style.overflow, "hidden");
    await act(async () => root.unmount()); root = null;
    delete document.fullscreenElement; full.remove(); assert.equal(document.body.style.overflow, "");
  });
  await check("application return refreshes status and refresh failure preserves existing cards", async () => {
    await mount(e(compiled.Applications)); assert.ok(text().includes("Ready for interview")); assert.ok(text().includes("Review my profile"));
    applicationStatus = "interviewed";
    await act(async () => document.dispatchEvent(new Event("visibilitychange"))); await settle(); assert.ok(text().includes("Your interview has been submitted"));
    assert.ok(!button("Give Interview"));
    const before = apiCalls.filter(call => call.url.endsWith("/applications")).length;
    const refresh = document.querySelector('[aria-label="Refresh applications"]');
    await act(async () => { refresh.dispatchEvent(new MouseEvent("click", { bubbles: true })); refresh.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    await settle(); assert.equal(apiCalls.filter(call => call.url.endsWith("/applications")).length, before + 1);
    applicationsFailure = true; await click(document.querySelector('[aria-label="Refresh applications"]'));
    renderErrors = renderErrors.filter(message => message.startsWith("Error loading applications:") === false);
    assert.ok(text().includes("previously loaded applications are shown below")); assert.ok(text().includes("Fixture Engineer"));
    applicationsFailure = false; await click(button("Retry")); assert.ok(!text().includes("previously loaded"));
  });
  await check("invited applications waiting for a CV direct the candidate to their profile", async () => {
    await mount(e(compiled.Applications), { processingStatus: "awaiting_candidate" });
    assert.ok(text().includes("Complete your profile and upload a CV"));
    assert.ok(!text().includes("Your CV assessment is processing"));
    assert.ok(document.querySelector('a[href="/profile"]'));
  });
  log(`${passes} interview usability checks passed (fixture APIs, sockets and media; real hardware remains unverified).`);
} finally {
  Date.now = now;
  if (root) await act(async () => root.unmount());
  console.log = log; console.error = logError;
  delete globalThis.__interviewTestSocket;
  win.close();
  await rm(tmp, { recursive: true, force: true });
}

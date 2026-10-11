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
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
win.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
win.scrollTo = () => {};
Object.defineProperty(win.HTMLVideoElement.prototype, "videoWidth", { get: () => 640 });
Object.defineProperty(win.HTMLVideoElement.prototype, "videoHeight", { get: () => 480 });
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
let answerFailure, uploadFailure, applicationsFailure, applicationStatus, applicationProcessingStatus, pairingVersion;
let mediaRequests, mediaFailure, audioSuspended, identityCaptured, socketEvents;
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
  createMediaStreamSource() { return { connect() {} }; }
  createOscillator() { return { connect() {}, frequency: {}, start() {}, stop() {} }; }
  createGain() { return { connect() {}, gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} } }; }
}
globalThis.MediaStream = win.MediaStream = FixtureStream;
globalThis.MediaRecorder = win.MediaRecorder = FixtureRecorder;
win.AudioContext = FixtureAudioContext;
Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { async getUserMedia() { mediaRequests++; if (mediaFailure) throw new win.DOMException("Permission denied", "NotAllowedError"); currentStream = new FixtureStream(); return currentStream; } } });
globalThis.__interviewTestSocket = () => {
  const handlers = new Map();
  socket = { connected: true, on(name, fn) { handlers.set(name, fn); return this; }, off() { return this; }, emit(name, payload, ack) { socketEvents.push({ name, payload }); ack?.({ ok: true }); return this; }, disconnect() { this.connected = false; }, connect() { this.connected = true; queueMicrotask(() => handlers.get("connect")?.()); }, fire(name, data) { handlers.get(name)?.(data); } };
  queueMicrotask(() => socket.fire("connect"));
  return socket;
};
function sessionPayload() {
  return { session_id: "ui-session", current_question: "Describe a recent project.", max_questions: 10, question_count: 1,
    engine_available: true, identity_captured: identityCaptured, dual_proctoring_required: dualRequired,
    mobile_pairing_token: `fixture-pairing-${pairingVersion}`, question_timeout_seconds: 300, status: serverStatus };
}
globalThis.fetch = win.fetch = async (url, options = {}) => {
  apiCalls.push({ url: String(url), options });
  const pathname = new URL(String(url), "http://localhost:5000").pathname;
  let data = {}, status = 200;
  if (pathname.endsWith("/session")) data = sessionPayload();
  if (pathname.endsWith("/activate")) { serverStatus = "active"; data = { current_question: "Describe a recent project.", question_deadline: Date.now() / 1000 + 300 }; }
  if (pathname.endsWith("/answer")) {
    status = answerFailure ? 503 : 200;
    data = answerFailure ? { error: "Temporary answer service failure" } : { next_question: "What did you learn?", progress: { questions_asked: 1 }, question_deadline: Date.now() / 1000 + 300 };
  }
  if (pathname.endsWith("/end")) { serverStatus = "completed"; data = { status: "completed", interview_score: 0, cv_score: 0, proctoring_score: 0 }; }
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
async function typeAnswer(value) {
  const input = document.querySelector("#typed-answer"); assert.ok(input);
  await act(async () => { Object.getOwnPropertyDescriptor(win.HTMLTextAreaElement.prototype, "value").set.call(input, value); input.dispatchEvent(new Event("input", { bubbles: true })); });
}
async function keyboard(key, shiftKey = false) { await act(async () => document.dispatchEvent(new win.KeyboardEvent("keydown", { key, shiftKey, bubbles: true, cancelable: true }))); await settle(); }
async function mount(component, options = {}) {
  if (root) await act(async () => root.unmount());
  Date.now = now; renderErrors = []; apiCalls = []; dualRequired = options.dual || false; micSound = true; recordings = [];
  serverStatus = "setup"; answerFailure = false; uploadFailure = false; applicationsFailure = false; applicationStatus = "shortlisted"; applicationProcessingStatus = options.processingStatus || "completed"; pairingVersion = 1;
  mediaRequests = 0; mediaFailure = options.mediaFailure || false; audioSuspended = options.audioSuspended || false; identityCaptured = options.identityCaptured !== false; socketEvents = [];
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
  micSound = false; await click(button("Start interview"));
  assert.ok(document.querySelector('[aria-label="Answer format"]'));
}
async function check(name, fn) {
  await fn();
  assert.equal(renderErrors.filter(message => !message.includes("not wrapped in act")).length, 0, renderErrors.join("\n"));
  passes++; log(`PASS ${name}`);
}
try {
  const exports = { Chat: "features/interview/pages/Chat", MobileRecorder: "features/interview/pages/MobileRecorder", Applications: "features/candidate/pages/Applications", Modal: "shared/components/ui/Modal", ConfirmDialog: "shared/components/ui/ConfirmDialog", AppProviders: "app/providers" };
  const entry = Object.entries(exports).map(([name, file]) => `export {${name === "AppProviders" ? name : "default as " + name}} from ${JSON.stringify(file)};`).join("\n");
  const output = await build({ stdin: { contents: entry, resolveDir: cwd, loader: "jsx" }, bundle: true, write: false,
    outfile: path.join(tmp, "bundle.mjs"), platform: "node", format: "esm", packages: "external",
    alias: Object.fromEntries(["app", "features", "shared", "assets"].map(name => [name, path.join(cwd, "src", name)])),
    loader: { ".js": "jsx", ".png": "dataurl", ".svg": "dataurl", ".jpg": "dataurl" },
    define: { "process.env": JSON.stringify({ NODE_ENV: "test", REACT_APP_API_URL: "http://localhost:5000" }) },
    plugins: [{ name: "socket-fixture", setup(plugin) {
      plugin.onResolve({ filter: /^socket.io-client$/ }, () => ({ path: "socket", namespace: "fixture" }));
      plugin.onLoad({ filter: /.*/, namespace: "fixture" }, () => ({ contents: "export const io=(...args)=>globalThis.__interviewTestSocket(...args);export default io;", loader: "js" }));
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

  await check("automatic device permission leads through speaker confirmation and face capture without a hidden Continue gate", async () => {
    await mount(e(compiled.Chat, { interviewId: "ui-session" }), { identityCaptured: false }); await settle(180);
    assert.equal(mediaRequests, 1); assert.ok(!button("Enable camera and microphone")); assert.ok(!button("Continue").disabled);
    assert.ok(text().includes("Continue to confirm your speakers")); await click(button("Continue"));
    assert.ok(document.querySelector('[role="dialog"]')); assert.ok(text().includes("Can you hear the test sound?"));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/activate")).length, 0);
    await click(button("I heard the sound", document.querySelector('[role="dialog"]')));
    assert.ok(button("Capture my face")); await click(button("Capture my face"));
    assert.equal(apiCalls.filter(call => call.url.endsWith("/register-face")).length, 1);
    await click(document.querySelector('input[type="checkbox"]')); micSound = false; await click(button("Start interview"));
    const activation = apiCalls.find(call => call.url.endsWith("/activate"));
    assert.deepEqual(JSON.parse(activation.options.body), { camera_ready: true, microphone_ready: true, speaker_ready: true });
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

  await check("typing does not trigger voice auto-submission and advances the same interview", async () => {
    await activeInterview(); await click(button("Type answer")); await typeAnswer("I built a reliable service.");
    const voice = recordings.find(recorder => recorder.mimeType.startsWith("audio")); assert.equal(voice.state, "inactive");
    const clock = now(); Date.now = () => clock + 31000; await settle(200);
    assert.equal(apiCalls.filter(call => call.url.endsWith("/answer")).length, 0);
    assert.ok(text().includes("Automatic answer submission is off")); assert.ok(text().includes("Question time remaining"));
    await click(button("Send text answer"));
    const answers = apiCalls.filter(call => call.url.endsWith("/answer")); assert.equal(answers.length, 1);
    assert.deepEqual(JSON.parse(answers[0].options.body), { question: "Describe a recent project.", answer: "I built a reliable service." });
    assert.ok(text().includes("What did you learn?")); assert.equal(document.querySelector("#typed-answer").value, "");
    assert.equal(recordings.filter(recorder => recorder.mimeType.startsWith("audio")).length, 1);
    Date.now = now;
  });
  await check("a failed typed submission keeps the exact answer for retry", async () => {
    await activeInterview(); await click(button("Type answer")); await typeAnswer("My saved draft."); answerFailure = true;
    await click(button("Send text answer")); assert.ok(button("Retry saved answer")); assert.equal(document.querySelector("#typed-answer").value, "My saved draft.");
    answerFailure = false; await click(button("Retry saved answer"));
    const answers = apiCalls.filter(call => call.url.endsWith("/answer")); assert.equal(answers.length, 2);
    assert.equal(answers[0].options.body, answers[1].options.body); assert.ok(text().includes("What did you learn?"));
  });
  await check("changing answer format protects both an unsent recording and a typed draft", async () => {
    await activeInterview(); micSound = true; await settle(180); micSound = false;
    await click(button("Type answer")); assert.ok(text().includes("Switch to a typed answer?"));
    const clock = now(); Date.now = () => clock + 9000; await settle(200);
    assert.equal(apiCalls.filter(call => call.url.endsWith("/answer")).length, 0);
    await click(button("Switch to typing")); assert.ok(document.querySelector("#typed-answer"));
    await typeAnswer("Keep my draft."); await click(button("Speak answer")); assert.ok(text().includes("Switch to a spoken answer?"));
    await click(button("Cancel")); assert.equal(document.querySelector("#typed-answer").value, "Keep my draft.");
    Date.now = now;
  });
  await check("phone reconnection provides a fresh pairing code and retains the typed draft", async () => {
    await activeInterview({ dual: true }); await click(button("Type answer")); await typeAnswer("Keep this draft.");
    await act(async () => socket.fire("mobile_disconnected")); await settle();
    assert.ok(text().includes("Reconnect your devices")); assert.ok(button("Resume interview").disabled);
    assert.ok(document.querySelector('[role="dialog"] svg')); assert.equal(document.querySelectorAll("video").length, 1);
    pairingVersion = 2; await click(button("Refresh phone pairing code"));
    assert.ok(apiCalls.filter(call => call.url.endsWith("/session")).length >= 2);
    assert.equal(apiCalls.filter(call => call.url.endsWith("/start")).length, 0);
    await act(async () => socket.fire("mobile_status_dashboard", { ready: true, status: "connected" })); await click(button("Resume interview"));
    assert.equal(document.querySelector("#typed-answer").value, "Keep this draft."); assert.equal(document.querySelectorAll("video").length, 1);
    await click(button("End interview")); assert.ok(text().includes("Your typed draft has not been submitted")); await click(button("Cancel"));
  });
  await check("a disconnected laptop can be checked again before resuming", async () => {
    await activeInterview(); await click(button("Type answer"));
    await act(async () => { currentStream.getVideoTracks()[0].stop(); currentStream.getVideoTracks()[0].onended(); }); await settle();
    assert.ok(button("Resume interview").disabled); micSound = true;
    await click(button("Retry device checks")); await settle(180); assert.ok(!button("Resume interview").disabled);
    micSound = false; await click(button("Resume interview")); assert.ok(!text().includes("Reconnect your devices"));
    assert.ok(document.querySelector("#typed-answer"));
  });
  await check("failed recording uploads warn before closing and offer themed leave or retry", async () => {
    await activeInterview(); await click(button("Type answer")); await typeAnswer("Submitted answer."); await click(button("Send text answer"));
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

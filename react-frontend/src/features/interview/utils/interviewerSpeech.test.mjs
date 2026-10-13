import test from "node:test";
import assert from "node:assert/strict";
import { playInterviewerSpeech } from "./interviewerSpeech.js";
import { proctoringNotice } from "./proctoringNotice.js";

const settle = () => new Promise(resolve => setTimeout(resolve, 65));
test("late audio errors cannot replay a completed question over the candidate", async () => {
  let audio, ended = 0, rejectPlay;
  globalThis.window = { speechSynthesis: { speak: assert.fail }, SpeechSynthesisUtterance: class {} };
  globalThis.Audio = class { currentTime = 0; constructor() { audio = this; }
    play() { return new Promise((resolve, reject) => { rejectPlay = reject; }); } pause() {} };
  const player = playInterviewerSpeech({ text: "Question ten", data: { audio_base64: "fixture" },
    onPlaying() {}, onCaption() {}, onAnalyser() {}, onDone: () => ended++, onError: assert.fail });
  const lateError = audio.onerror; audio.onended();
  lateError(); rejectPlay(new Error("late media failure")); await settle();
  assert.equal(ended, 1); assert.equal(audio.onerror, null); player.cancel();
});
test("AI captions follow audio timepoints and listening waits for actual completion", async () => {
  let audio, playing = 0, ended = 0, caption = "";
  globalThis.window = {};
  globalThis.Audio = class { currentTime = 0; constructor() { audio = this; } async play() { this.onplaying?.(); } pause() {} };
  const player = playInterviewerSpeech({ text: "Hello candidate", data: { audio_base64: "fixture", timepoints: [{ time_seconds: 0, char_end: 5 }, { time_seconds: 1, char_end: 15 }] },
    onPlaying: () => playing++, onCaption: value => { caption = value; }, onAnalyser() {}, onDone: () => ended++, onError: assert.fail });
  await settle(); assert.equal(caption, "Hello"); assert.equal(playing, 1); assert.equal(ended, 0);
  audio.currentTime = 1.2; await settle(); assert.equal(caption, "Hello candidate"); assert.equal(ended, 0);
  audio.onended(); assert.equal(ended, 1); player.cancel();
});

test("missing server audio uses native voice boundaries; total failure does not silently listen", () => {
  let utterance, caption, errors = 0, ended = 0;
  globalThis.window = { SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    speechSynthesis: { speak(value) { utterance = value; }, cancel() {} } };
  const player = playInterviewerSpeech({ text: "Explain your design", onPlaying() {}, onCaption: value => { caption = value; },
    onAnalyser() {}, onDone: () => ended++, onError: () => errors++ });
  utterance.onstart(); utterance.onboundary({ charIndex: 0 }); assert.equal(caption, "Explain");
  utterance.onerror(); assert.equal(errors, 1); assert.equal(ended, 0); player.cancel();
});

test("unmount stops playback, timers and stale callbacks", async () => {
  let audio, updates = 0;
  globalThis.window = {};
  globalThis.Audio = class { currentTime = 0; constructor() { audio = this; } async play() {} pause() { this.paused = true; } };
  const player = playInterviewerSpeech({ text: "Question", data: { audio_base64: "fixture" }, onPlaying() {}, onCaption: () => updates++,
    onAnalyser() {}, onDone: assert.fail, onError: assert.fail });
  player.cancel(); await settle(); assert.equal(updates, 0); assert.equal(audio.paused, true); assert.equal(audio.onended, null);
});

test("monitoring warnings name the camera, correction and uncertainty", () => {
  const phone = proctoringNotice("detected", "multiple_faces", "mobile");
  assert.match(phone.title, /Phone/); assert.match(phone.message, /may be visible/); assert.match(phone.message, /reflections/);
  assert.equal(phone.recorded, true); assert.equal(proctoringNotice("Audio retry", "notice").recorded, false);
  assert.equal(proctoringNotice("Phone disconnected", "interruption", "monitoring").title, "Interview connection warning");
  assert.equal(proctoringNotice("", "tab_switch").title, "Laptop focus warning");
});

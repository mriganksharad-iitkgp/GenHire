import test from "node:test";
import assert from "node:assert/strict";
import { startLiveCaptions } from "./liveCaptions.js";

test("captions buffer microphone onset, serialize packets and recover after room rejoin", async () => {
  let node, startAck, packetAck, caption = "", note = "";
  const handlers = new Map(), events = [];
  globalThis.window = { location: { origin: "https://test.example" } };
  globalThis.MediaStream = class {};
  globalThis.AudioWorkletNode = class { constructor() { node = this; } port = {}; connect() {} disconnect() {} };
  const socket = { connected: true, on: (name, listener) => handlers.set(name, listener), off: name => handlers.delete(name),
    emit(name, data, ack) { events.push({ name, data }); if (name === "speech_live_start") startAck = ack;
      else if (name === "speech_live_audio") packetAck = ack; else ack?.({ ok: true }); } };
  const context = { resume: async () => {}, audioWorklet: { addModule: async () => {} },
    createMediaStreamSource: () => ({ connect() {}, disconnect() {} }), createGain: () => ({ gain: {}, connect() {}, disconnect() {} }) };
  const controller = await startLiveCaptions(context, { getAudioTracks: () => [] }, socket, "owned",
    value => { caption = value; }, value => { note = value; });
  const sendPCM = () => node.port.onmessage({ data: { type: "audio", buffer: new ArrayBuffer(6400) } });
  sendPCM(); sendPCM(); assert.equal(events.filter(event => event.name === "speech_live_audio").length, 0);
  startAck({ ok: true }); await new Promise(resolve => setImmediate(resolve));
  assert.equal(events.filter(event => event.name === "speech_live_audio").length, 1);
  packetAck({ ok: true }); await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(events.filter(event => event.name === "speech_live_audio").map(event => event.data.sequence), [0, 1]);
  packetAck({ ok: true }); await new Promise(resolve => setImmediate(resolve));
  let id = events.find(event => event.name === "speech_live_start").data.stream_id;
  handlers.get("speech_live_transcript")({ stream_id: id, transcript: "I built an API." });
  socket.connected = false; handlers.get("disconnect")(); sendPCM(); assert.match(note, /recording continues/);
  socket.connected = true; const reconnect = controller.reconnect(); startAck({ ok: true }); await reconnect;
  id = events.filter(event => event.name === "speech_live_start").at(-1).data.stream_id;
  assert.equal(events.filter(event => event.name === "speech_live_audio").at(-1).data.sequence, 0);
  packetAck({ ok: true });
  handlers.get("speech_live_transcript")({ stream_id: id, transcript: "It uses Python." });
  assert.equal(caption, "I built an API. It uses Python."); assert.equal(note, "");
  controller.cancel(); assert.equal(handlers.size, 0); assert.equal(node.port.onmessage, null);
  assert.equal(events.at(-1).name, "speech_live_cancel");
});

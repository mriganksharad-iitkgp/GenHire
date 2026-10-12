import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

test("real worklet resamples stereo input to bounded mono PCM packets", async () => {
  let Processor; const packets = [];
  const context = vm.createContext({ sampleRate: 48000,
    AudioWorkletProcessor: class { port = { postMessage: data => packets.push(data) }; },
    registerProcessor: (name, implementation) => { assert.equal(name, "interview-pcm"); Processor = implementation; } });
  vm.runInContext(await readFile(new URL("../../../../public/assets/interview-pcm-worklet.js", import.meta.url), "utf8"), context);
  const worklet = new Processor();
  for (let i = 0; i < 375; i++) worklet.process([[new Float32Array(128).fill(.5), new Float32Array(128).fill(.25)]]);
  worklet.port.onmessage({ data: { type: "flush" } });
  const audio = packets.filter(packet => packet.type === "audio").flatMap(packet => [...new Int16Array(packet.buffer)]);
  assert.equal(audio.length, 16000); assert.ok(audio.slice(1).every(value => value === 12288));
  assert.ok(packets.filter(packet => packet.type === "audio").every(packet => packet.buffer.byteLength <= 6400));
  assert.equal(packets.at(-1).type, "flushed");
});

/* Real microphone PCM; reconnectable, ordered and bounded. The answer recorder is independent. */
/* global globalThis */
import { recordingPartId, socketAcknowledgement } from "./session.js";

const modules = new WeakMap();
export async function startLiveCaptions(context, stream, socket, sessionId, onText, onUnavailable) {
  if (!context?.audioWorklet || !globalThis.AudioWorkletNode || !socket) {
    onUnavailable("Live captions are unavailable on this device. Your recorded answer will be transcribed when sent.");
    return null;
  }
  let id = "", sequence = 0, stopped = false, ready = false, starting = false, inFlight = false;
  let source, node, mute, retryTimer, retries = 0, text = "", prefix = "", packets = [];
  const note = () => onUnavailable("Live captions are reconnecting. Keep speaking; your answer recording continues.");
  const restart = () => {
    if (stopped || retryTimer) return;
    if (retries >= 3) { onUnavailable("Live captions are temporarily unavailable. Your full recorded answer will be transcribed when sent."); return; }
    retries += 1;
    retryTimer = setTimeout(() => { retryTimer = null; reconnect(); }, 1500);
  };
  const pump = async () => {
    if (stopped || !ready || !socket.connected || inFlight || !packets.length) return;
    inFlight = true; const streamId = id; const packet = packets.shift();
    try {
      await socketAcknowledgement(socket, "speech_live_audio", { stream_id: streamId, sequence: sequence++, audio: packet }, 3000);
    } catch {
      if (streamId === id && !stopped) { ready = false; note(); restart(); }
    } finally { if (streamId === id) { inFlight = false; pump(); } }
  };
  const reconnect = async () => {
    if (stopped || starting || !socket.connected) return;
    starting = true; ready = false;
    if (id) socket.emit("speech_live_cancel", { stream_id: id });
    prefix = text; id = recordingPartId(); sequence = 0; inFlight = false;
    try {
      await socketAcknowledgement(socket, "speech_live_start", { session_id: sessionId, stream_id: id }, 6000);
      if (!stopped) { ready = true; pump(); }
      else socket.emit("speech_live_cancel", { stream_id: id });
    } catch { if (!stopped) { note(); restart(); } }
    finally { starting = false; }
  };
  const listener = data => {
    if (data.stream_id !== id || stopped) return;
    if (data.error) { ready = false; note(); restart(); }
    else { text = [prefix, data.transcript || ""].filter(Boolean).join(" "); onText(text); onUnavailable(""); retries = 0; }
  };
  const disconnect = () => { ready = false; note(); };
  const cleanup = () => {
    stopped = true; clearTimeout(retryTimer); packets = [];
    socket.off("speech_live_transcript", listener); socket.off("disconnect", disconnect);
    if (node) node.port.onmessage = null;
    source?.disconnect(); node?.disconnect(); mute?.disconnect();
    if (id && socket.connected) socket.emit("speech_live_cancel", { stream_id: id });
  };
  try {
    await context.resume();
    if (!modules.has(context)) modules.set(context, context.audioWorklet.addModule(new URL("/assets/interview-pcm-worklet.js", window.location.origin).href)
      .catch(error => { modules.delete(context); throw error; }));
    await modules.get(context);
    socket.on("speech_live_transcript", listener); socket.on("disconnect", disconnect);
    source = context.createMediaStreamSource(new MediaStream(stream.getAudioTracks()));
    node = new AudioWorkletNode(context, "interview-pcm", { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] });
    mute = context.createGain(); mute.gain.value = 0;
    node.port.onmessage = event => {
      if (stopped || event.data.type !== "audio") return;
      // Buffer at most six seconds during reconnect; MediaRecorder retains the full answer.
      if (packets.length >= 30) { packets.shift(); note(); }
      packets.push(event.data.buffer); pump();
    };
    source.connect(node); node.connect(mute); mute.connect(context.destination);
    reconnect();
    return { reconnect, cancel: cleanup, async stop() { cleanup(); return { transcript: text, complete: false }; } };
  } catch {
    cleanup(); onUnavailable("Live captions could not start. Your recorded answer will still be transcribed when sent."); return null;
  }
}

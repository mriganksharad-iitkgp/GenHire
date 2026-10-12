/* global globalThis */
import { recordingPartId, socketAcknowledgement } from "./session";

const modules = new WeakMap();
export async function startLiveCaptions(context, stream, socket, sessionId, onText, onUnavailable) {
  if (!context?.audioWorklet || !globalThis.AudioWorkletNode || !socket?.connected) {
    onUnavailable("Live captions are unavailable on this connection. Your recording will still be transcribed when you send it.");
    return null;
  }
  const id = recordingPartId(); let sequence = 0, stopped = false, ready = false, flushed;
  let source, node, mute;
  const listener = data => {
    if (data.stream_id !== id || stopped) return;
    if (data.error) onUnavailable(data.error); else onText(data.transcript || "");
  };
  const disconnect = () => onUnavailable("Live captions are reconnecting. Your answer recording continues.");
  const cleanup = () => {
    stopped = true; socket.off("speech_live_transcript", listener); socket.off("disconnect", disconnect);
    if (node) node.port.onmessage = null;
    source?.disconnect(); node?.disconnect(); mute?.disconnect();
  };
  try {
    await context.resume();
    if (!modules.has(context)) modules.set(context, context.audioWorklet.addModule(new URL("/assets/interview-pcm-worklet.js", window.location.origin).href));
    await modules.get(context);
    await socketAcknowledgement(socket, "speech_live_start", { session_id: sessionId, stream_id: id }, 5000); ready = true;
    socket.on("speech_live_transcript", listener); socket.on("disconnect", disconnect);
    source = context.createMediaStreamSource(new MediaStream(stream.getAudioTracks()));
    node = new AudioWorkletNode(context, "interview-pcm", { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] });
    mute = context.createGain(); mute.gain.value = 0;
    node.port.onmessage = event => {
      if (event.data.type === "flushed") { flushed?.(); return; }
      if (!stopped && socket.connected && event.data.type === "audio") socket.emit("speech_live_audio", {
        stream_id: id, sequence: sequence++, audio: event.data.buffer }, response => {
          if (!stopped && response?.ok === false) {
            cleanup(); onUnavailable("Live captions are temporarily unavailable. Your recorded answer is still saved.");
          }
        });
    };
    source.connect(node); node.connect(mute); mute.connect(context.destination);
    return { async stop() {
      if (stopped) return null;
      await new Promise(resolve => { const timer = setTimeout(resolve, 500); flushed = () => { clearTimeout(timer); resolve(); }; node.port.postMessage({ type: "flush" }); });
      source.disconnect(); node.disconnect(); mute.disconnect();
      try { return await socketAcknowledgement(socket, "speech_live_end", { stream_id: id, last_sequence: sequence - 1 }, 10000); }
      finally { cleanup(); }
    }, cancel() { cleanup(); if (ready && socket.connected) socket.emit("speech_live_end", { stream_id: id, last_sequence: sequence - 1 }); } };
  } catch {
    cleanup(); if (ready) socket.emit("speech_live_end", { stream_id: id, last_sequence: sequence - 1 });
    onUnavailable("Live captions are temporarily unavailable. Your recorded answer is retained for transcription.");
    return null;
  }
}

/* global globalThis */
// Interview-specific normalization keeps practice, reloads and real sessions
// on the same contract without guessing scores or reopening paid sessions.
export function isPracticeSession(location, session = {}) {
  return session.is_practice === true || location.state?.isPractice === true ||
    new URLSearchParams(location.search).get("practice") === "true";
}

export function scorePercent(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const numeric = Number(value);
  return Math.round(Math.max(0, Math.min(100, numeric)));
}

export function terminalPhase(session = {}) {
  if (["completed", "interview_ended"].includes(session.status)) return "completed";
  if (["abandoned", "discarded", "interview_discarded"].includes(session.status)) return "discarded";
  return null;
}

export function recordingPartId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}`;
}

// Transport connection alone does not prove that the server authorized a room.
export function socketAcknowledgement(socket, event, payload, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    if (!socket?.connected) { reject(new Error("Interview monitoring is reconnecting. Please retry in a moment.")); return; }
    const timeout = setTimeout(() => reject(new Error("Interview monitoring did not respond. Please retry.")), timeoutMs);
    socket.emit(event, payload, (response) => {
      clearTimeout(timeout);
      if (!response?.ok) {
        const error = new Error(response?.error || "Interview monitoring could not be started. Reconnect your devices and retry.");
        error.code = response?.error_code; reject(error); return;
      }
      resolve(response);
    });
  });
}

export function reconcileAnswer(session, question, answer) {
  const terminal = terminalPhase(session);
  if (terminal) return { terminal, accepted: true };
  const current = session.current_question || session.initial_questions?.[0];
  const previous = session.last_answer;
  if (previous?.question === question && previous.answer === answer && previous.result?.interview_complete) return { accepted: true, finish: true };
  return { accepted: (!!current && current !== question) ||
    (!!previous && previous.question === question && previous.answer === answer),
    question: current, questionCount: session.question_count || 1 };
}

export function interviewScore(result = {}) {
  const evaluation = result.evaluation || {};
  const scores = evaluation.quantitative_scores;
  return scorePercent(result.interview_score ?? result.final_score ?? evaluation.final_score ??
    evaluation.quantitative?.average_relevance_score ??
    (typeof scores === "number" ? scores : scores?.average ?? scores?.overall));
}

export function mediaMimeType(kind, recorder = globalThis.MediaRecorder) {
  if (!recorder) return "";
  const types = kind === "audio"
    ? ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm", "audio/mp4"]
    : ["video/webm;codecs=vp8,opus", "video/webm", "video/mp4"];
  return types.find((type) => recorder.isTypeSupported(type)) || "";
}

export function mobilePairingUrl(session, origin) {
  if (!session?.session_id || !session?.mobile_pairing_token) return "";
  const url = new URL(`/mobile-camera/${encodeURIComponent(session.session_id)}`, origin);
  url.searchParams.set("pairing_token", session.mobile_pairing_token);
  return url.toString();
}

export function microphoneLevel(samples) {
  if (!samples.length) return 0;
  const rms = Math.sqrt(samples.reduce((total, sample) => total + ((sample - 128) / 128) ** 2, 0) / samples.length);
  return Math.min(100, Math.round(rms * 450));
}

export async function blobBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () => reject(new Error("Could not read your recorded answer."));
    reader.readAsDataURL(blob);
  });
}

// Safari records AAC/MP4. Decode and send a real PCM WAV rather than labelling
// compressed bytes LINEAR16 (which made those candidates' transcription fail).
export async function transcriptionAudio(blob, stream) {
  const mime = blob.type;
  const sampleRate = stream.getAudioTracks()[0]?.getSettings().sampleRate || 48000;
  if (mime.includes("webm") || mime.includes("ogg")) {
    return { audio_base64: await blobBase64(blob), sample_rate_hertz: sampleRate,
      encoding: mime.includes("ogg") ? "OGG_OPUS" : "WEBM_OPUS" };
  }
  const AudioContextClass = globalThis.AudioContext || globalThis.webkitAudioContext;
  const context = new AudioContextClass();
  try {
    const buffer = await context.decodeAudioData(await blob.arrayBuffer());
    const samples = new Float32Array(buffer.length);
    for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
      const input = buffer.getChannelData(channel);
      for (let index = 0; index < samples.length; index += 1) samples[index] += input[index] / buffer.numberOfChannels;
    }
    const bytes = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(bytes);
    const write = (offset, value) => [...value].forEach((character, i) => view.setUint8(offset + i, character.charCodeAt(0)));
    write(0, "RIFF"); view.setUint32(4, bytes.byteLength - 8, true); write(8, "WAVE"); write(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, buffer.sampleRate, true); view.setUint32(28, buffer.sampleRate * 2, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, samples.length * 2, true);
    samples.forEach((sample, index) => view.setInt16(44 + index * 2, Math.max(-1, Math.min(1, sample)) * (sample < 0 ? 32768 : 32767), true));
    return { audio_base64: await blobBase64(new Blob([bytes], { type: "audio/wav" })),
      sample_rate_hertz: buffer.sampleRate, encoding: "LINEAR16" };
  } finally { await context.close(); }
}

export async function interviewRequest(apiBase, path, token, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${apiBase}${path}`, { ...options, signal: controller.signal,
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...options.headers } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.error || data.message || "This action could not be completed. Please retry.");
      error.status = response.status; error.code = data.error_code; error.details = data; throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The server is taking longer than expected. Your saved answers are safe. Please retry.");
    throw error;
  } finally { clearTimeout(timeout); }
}

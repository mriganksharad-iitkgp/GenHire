/* Captions follow provider word timestamps / native speech boundaries, never a typing timer. */
export function playInterviewerSpeech({ text, data, context, onPlaying, onCaption, onAnalyser, onDone, onError }) {
  let audio, utterance, source, analyser, timer, cancelled = false, finished = false, fallback = false;
  let lastTime = -1, stalledAt = Date.now();
  const release = () => { clearInterval(timer); source?.disconnect(); analyser?.disconnect(); onAnalyser(null); };
  const done = () => { if (cancelled || finished) return; finished = true; release(); onCaption(text); onDone(); };
  const fail = () => { if (cancelled || finished) return; finished = true; release(); onError("The question could not be played. Choose Play question to retry, or continue with the question text."); };
  const native = () => {
    if (cancelled || fallback) { fail(); return; }
    fallback = true; release(); if (audio) { audio.onended = null; audio.onerror = null; audio.pause(); }
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) { fail(); return; }
    utterance = new window.SpeechSynthesisUtterance(text); utterance.lang = "en-US";
    let started = false;
    utterance.onstart = () => { if (!cancelled) { started = true; stalledAt = Date.now(); onPlaying(); } };
    utterance.onboundary = event => { if (!cancelled) {
      const end = text.indexOf(" ", event.charIndex + 1); onCaption(text.slice(0, end < 0 ? text.length : end));
    } };
    utterance.onend = done; utterance.onerror = fail;
    timer = setInterval(() => { if ((!started && Date.now() - stalledAt > 6000) || Date.now() - stalledAt > 90000) { window.speechSynthesis.cancel(); fail(); } }, 500);
    stalledAt = Date.now(); window.speechSynthesis.speak(utterance);
  };
  async function start() {
    if (!data?.audio_base64) { native(); return; }
    audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
    const points = (data.timepoints || []).filter(point => Number.isFinite(point.time_seconds) && Number.isFinite(point.char_end));
    audio.onplaying = () => { if (!cancelled) { stalledAt = Date.now(); onPlaying(); if (!points.length) onCaption(text); } };
    audio.onended = done; audio.onerror = native;
    try {
      if (context?.createMediaElementSource && context.state !== "closed") {
        await context.resume(); if (cancelled) return;
        // Create the analyser before redirecting the audio element.
        analyser = context.createAnalyser(); analyser.fftSize = 1024;
        source = context.createMediaElementSource(audio);
        try { source.connect(analyser); analyser.connect(context.destination); onAnalyser(analyser); }
        catch { source.disconnect(); source.connect(context.destination); }
      }
      timer = setInterval(() => {
        if (cancelled || finished) return;
        if (audio.currentTime !== lastTime) { lastTime = audio.currentTime; stalledAt = Date.now(); }
        if (Date.now() - stalledAt > 8000) { native(); return; }
        let end = 0;
        for (const point of points) if (point.time_seconds <= audio.currentTime) end = Math.max(end, point.char_end);
        if (end) onCaption(text.slice(0, end));
      }, 50);
      await audio.play();
    } catch { native(); }
  }
  start();
  return { cancel() { cancelled = true; release(); if (audio) { audio.onended = null; audio.onerror = null; audio.onplaying = null; audio.pause(); audio.src = ""; }
    if (utterance) { utterance.onend = null; utterance.onerror = null; utterance.onboundary = null; utterance.onstart = null; window.speechSynthesis.cancel(); } } };
}

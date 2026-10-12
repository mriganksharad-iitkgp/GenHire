export function voicePolicy(value = {}) {
  const number = (key, fallback, min, max) => value?.[key] != null && value[key] !== "" && Number.isFinite(Number(value[key])) ? Math.max(min, Math.min(max, Number(value[key]))) : fallback;
  return { silence_seconds: number("silence_seconds", 5, 2, 30), initial_wait_seconds: number("initial_wait_seconds", 10, 5, 120),
    max_answer_seconds: number("max_answer_seconds", 180, 30, 180), speech_level: number("speech_level", 6, 2, 50), speech_hold_ms: number("speech_hold_ms", 240, 120, 1000) };
}

// Require sustained activity above the setup noise floor, so isolated clicks
// and steady fan noise do not repeatedly reset the silence deadline.
export function createVoiceTurn(settings, startedAt, noiseFloor = 0) {
  const policy = voicePolicy(settings);
  const threshold = Math.max(policy.speech_level, Math.min(40, noiseFloor * 2.5 + 1));
  let aboveSince = null, lastSpeech = startedAt, spoke = false, submitted = false;
  return { sample(level, now) {
    if (level >= threshold) {
      aboveSince ??= now;
      if (now - aboveSince >= policy.speech_hold_ms) { spoke = true; lastSpeech = now; }
    } else aboveSince = null;
    const remaining = spoke ? policy.silence_seconds - (now - lastSpeech) / 1000 : policy.initial_wait_seconds - (now - startedAt) / 1000;
    const submit = !submitted && (remaining <= 0 || now - startedAt >= policy.max_answer_seconds * 1000);
    if (submit) submitted = true;
    return { spoke, submit, skip: !spoke, remaining: Math.max(0, Math.ceil(remaining)), threshold };
  } };
}

# Interview turn recovery — 13 October 2026

## Confirmed causes

- The deployed backend exhausted its 512 MiB memory limit at 02:50:38 IST; Cloud Run terminated the instance and started another.
- This restart broke caption/monitoring connections and delayed pending requests until startup completed around 02:51:37.
- The report endpoint subsequently returned 202, then 200 at 02:51:44; the recording upload also succeeded.
- DeepSeek returned HTTP 402, insufficient balance; Gemini returned HTTP 429, depleted prepayment credits.
- Groq was reachable with the existing key, but the question adapter's 256-token output allowance also included GPT-OSS reasoning tokens.
- Three synthetic probes reproduced empty Groq output with `finish_reason=length`; the generic adapter error concealed the reason.
- Failed next-question retries launched two background scoring calls before generation, consuming more quota without advancing.
- The old fixed voice gate could reset silence on brief noise. Defaults were eight seconds after speech and 30 seconds without speech.
- Captions recognized isolated three-second windows with little overlap; full-answer recognition later had more context and could correct them.
- That sustained caption cadence was about 22.5 requests/minute, above Groq's published free Whisper limit of 20 RPM before final transcription.
- Separate ZeptoMail logs report exhausted email credits; this affects notifications, not question generation.

## Applied live

- Cloud Run `hrtech` memory increased from **512 MiB to 2 GiB** using the existing deployment identity.
- Recovery revision **hrtech-00160-j8z** is ready; image, identity, secrets, CPU and concurrency were preserved.
- Public `/health` and Google-login OPTIONS preflight both returned **HTTP 200** after recovery.
- This provides memory headroom, not a concurrent-interview capacity benchmark. Monitor memory under representative laptop/phone load.
- Cloud Build access returned **403** for this credential. The source changes below have **not** been deployed in this session.

## Source and kiosk changes

- Questions default to 1024 output tokens and low reasoning effort on GPT-OSS; empty/truncated replies trigger fallback with a safe diagnostic label.
- Each provider has a four-second configured timeout; the whole question operation has a 14-second caller budget.
- Questions still come directly from the LLM using CV, JD and conversation history; no RAG, embeddings or question-bank selection is introduced.
- Scoring starts after successful generation; failed retries do not create duplicate scoring jobs.
- Optional LlamaIndex readers/providers load only when used, reducing unnecessary interview startup imports.
- Sustained microphone activity is measured above the setup noise floor; isolated clicks do not reset the silence countdown.
- Auto-submit defaults: **five seconds of silence after speech**, or an empty answer after **ten seconds with no speech**.
- The initial clock starts **after Alex's audio ends**, so listening to the question does not consume thinking time.
- Timings arrive from the backend session API; experiments do not require rebuilding the kiosk for each value.
- Captions run every four seconds with up to eight seconds of overlapping audio context.
- Word timestamps replace overlapping draft words instead of appending duplicate recognition; confirmed earlier text supplies a short context hint.
- Likely silence hallucinations are filtered using Whisper confidence; live text is labelled **Draft captions**.
- The full recording remains the final transcription source. Draft words can still change with context; perfect recognition is not guaranteed.
- Existing voice sphere, playback, monitoring warnings and saved-answer retry remain available.

## Timing experiments

These non-secret settings were added to `python-backend/.env`, `.env.production` and `.env.example`:

```dotenv
INTERVIEW_SILENCE_SECONDS="5"
INTERVIEW_INITIAL_WAIT_SECONDS="10"
INTERVIEW_MAX_ANSWER_SECONDS="180"
INTERVIEW_SPEECH_LEVEL="6"
INTERVIEW_SPEECH_HOLD_MS="240"
INTERVIEW_QUESTION_MAX_TOKENS="1024"
INTERVIEW_PROVIDER_TIMEOUT_SECONDS="4"
INTERVIEW_QUESTION_BUDGET_SECONDS="14"
```

Restart the local backend after editing. In production, set these Cloud Run variables and deploy the updated backend code.
Editing local dotenv does not update Cloud Run. Preserve the existing Redis Secret Manager reference.
Allowed ranges: silence 2–30 s, initial wait 5–120 s, recording 30–180 s, speech level 2–50, sustained speech 120–1000 ms.
Five/ten seconds are the requested defaults; try silence 7 and initial wait 15–20 if candidates need longer thinking pauses.

## Measured latency and billing

Small synthetic probes using the configured local API clients measured:

| Operation | Response time |
| --- | --- |
| First question including unavailable DeepSeek/Gemini attempts | 9.75 s |
| Subsequent question generation | 1.27–1.39 s |
| Groq provider portion across three successful turns | 1.27–1.69 s |
| Google TTS for a short test phrase | 1.08 s |
| Groq transcription of that phrase with word timestamps | 0.75 s |

These developer-machine probes are not production guarantees or load tests.
A practical warm-service estimate is **8–12 seconds from stopping speech to hearing the next question**, including the deliberate five-second silence wait.
Failover, long recordings/context, network latency, concurrent load or cold starts can increase that time.
Draft captions first appear after four seconds of audio plus recognition/network time; this is incremental file recognition, not token-by-token streaming ASR.

- **DeepSeek balance:** restores the primary provider and avoids unavailable-provider attempts before Groq; it does not improve Groq captions.
- **Groq paid capacity:** raises applicable account limits and helps concurrent interviews/captions avoid quota interruptions; check actual limits in the console.
- **Same speech model:** purchasing capacity does not itself change accuracy. Audio clarity, context, language hints and model choice matter.
- **Gemini:** this project's prepaid credits are also depleted; a valid key alone is insufficient.
- **Infrastructure:** provider credits cannot prevent Cloud Run memory restarts; memory is a separate setting and cost.
- While providers are unfunded, `LLM_PROVIDER_PRIORITY="groq,deepseek,gemini"` is an optional experiment to avoid first-request failover delay. This order was not changed automatically.

References: [Groq speech API](https://console.groq.com/docs/speech-to-text), [Groq rate limits](https://console.groq.com/docs/rate-limits), [DeepSeek errors](https://api-docs.deepseek.com/quick_start/error_codes/), [Cloud Run memory](https://cloud.google.com/run/docs/configuring/memory-limits).

## Release and verification

1. Commit/push backend changes through the existing GitHub → Cloud Build workflow; verify the resulting revision retains **2 GiB** memory.
2. Publish the updated web build for browser interviews.
3. Install **kiosk 1.2.7**, `secure-browser-kiosk/dist/Genhire.exe`, then reopen the interview. Existing installations keep their bundled UI until replaced.
4. Verify five seconds of silence sends once; ten seconds without speech after Alex finishes sends an empty answer.
5. Complete a deployed interview with laptop and phone connected and inspect memory/provider diagnostics. Verification here consumed no real candidate attempt.

Installer: **102,581,846 bytes**, SHA-256 `386d2b7dcbc90a78bc8227c5eee02582bc547a33a261ca4b3820f9ec207cbe1a`.
The matching `.sha256` is beside it. The hosted installer has not been replaced.
All 24 bundled UI/assets files match the build output byte-for-byte; packaged application version is 1.2.7.
Validation: 176 backend tests (full suite plus added focused tests), 28 frontend helpers, 24 interview UI scenarios, seven kiosk security tests, lint, both builds, and native Electron audio/WebGL/caption/cleanup checks.
Native responsive checks covered 1400, 900 and 391-pixel windows; physical-camera accuracy and production concurrency require a deployed acceptance run.

# Interview voice sphere and live captions

Updated 13 October 2026; shared website/kiosk UI in release 1.2.6.

## Release 1.2.6: causes and repairs

- The old four-second question budget expired while providers failed over; first and subsequent questions now use one direct LLM call with CV, JD and previous Q/A as context, without question banks, retrieval, embeddings or an extra context-extraction call.
- Question output is bounded to 256 tokens; each configured provider has a four-second request deadline within a fourteen-second completion budget. Provider failures preserve the current answer for retry instead of ending the interview.
- A synthetic live probe on 12 October found DeepSeek HTTP 402 (billing), Gemini ResourceExhausted (quota), and a successful Groq question in 0.73 seconds. These are observations, not a latency guarantee; restore provider balance/quota in the respective accounts.
- Billing/quota failures enter the existing five-minute provider cooldown so every question does not repeat the failing call. Provider usage writes run through a bounded background queue; in-memory pending telemetry can be lost on process termination and is not a durable billing queue.
- The client previously abandoned Google speech at the same four-second deadline as the server, and could silently enter listening after playback failed. Google synthesis now has an eight-second RPC deadline and the UI allows twelve seconds, followed by native speech fallback and explicit retry/text-continuation controls if audio remains unavailable.
- Candidate PCM buffering now starts before the stream acknowledgement, retains up to six seconds during short reconnects, and rejoins only after the owned socket room is ready. A single in-flight packet preserves ordering; long outages explicitly report unavailable captions while the whole-answer recorder continues.
- Per-packet Redis throttling was removed from the 200 ms caption path; authenticated stream ownership, start quotas, packet size, elapsed-audio bounds, recognition slots and queue bounds remain enforced.
- Completion previously posted no JSON body while Flask unconditionally parsed JSON, causing HTTP 415. Both bodyless and object-JSON requests are now accepted, and the client sends `{}` explicitly.
- Report evaluation runs in a bounded background pool; HTTP 202 responses are polled rather than keeping an HTTP request open during scoring. A Mongo lease and process-local single-flight guard coordinate retries; this is not a durable external task queue. After a process crash, retry can reclaim the session when the three-minute lease expires.
- Report generation waits up to thirty seconds for outstanding answer evaluations and uses a separate twenty-second prose budget. The UI polls for up to two minutes, then offers retry; incomplete evaluation is labelled rather than assigned invented scores.

## Experience and rendering

`Chat.jsx` shows AI questions and the candidate's live spoken captions on the
left. The right column contains the camera, reusable `VoiceSphere`, device status,
interruption totals and a phone recovery link. Small screens stack these panels.
Typed answer controls are removed; recorded speech remains the submission source.
Saved transcript turns are restored from the owned interview session.

`VoiceSphere.jsx` uses the single new dependency **Three.js 0.180.0**; no Fiber,
postprocessing or animation package is required. A custom shader renders 2,800
dotted points on a rotating 3D sphere, using the existing lavender/blue/mint theme.

| State | Visual and audio source |
| --- | --- |
| Idle | Subtle breathing; zero voice amplitude |
| Listening | Blue waves driven by the existing microphone analyser |
| Processing | Purple ambient particles during real requests; zero voice amplitude |
| AI speaking | Mint pulses measured from the actual AI HTML audio element |
| Interrupted | Motion and measured amplitude settle while devices recover |

RMS measurements use Web Audio time-domain samples and smooth attack/release.
The sphere never invents voice levels, opens a second microphone, or closes the
caller's context. Pixel density is bounded, hidden pages skip draws, reduced-motion
preferences limit movement, and missing WebGL displays a static dotted fallback.
Unmount disposes GPU resources, observers and animation frames; Chat disconnects
speaker nodes and closes its own microphone/context when the interview finishes.

## Recognition path and setup

The existing backend `GoogleSpeechService` supplies configured STT and Google
question TTS. Keep the current `STT_PROVIDER=groq`, `GROQ_API_KEY` and
`GROQ_STT_MODEL=whisper-large-v3-turbo`, or deliberately select/configure the
existing Google STT path. TTS still needs Google ADC and the enabled TTS API.
All provider credentials stay on the backend; no new frontend secret is needed.

An AudioWorklet reuses the checked microphone and resamples its real input to
16 kHz mono PCM in 200 ms packets. Serve `/assets/interview-pcm-worklet.js` on the
HTTPS website and bundled kiosk loopback server. The existing kiosk CSP permits
this local asset; media is never fetched from an unrelated origin.

Owner-bound `speech_live_start`, `speech_live_audio`, `speech_live_end` and `speech_live_cancel` Socket.IO
events carry audio to the configured service. The backend uses three-second WAV
windows with a short overlap, removes repeated caption phrases, and sends text
only to the authenticated desktop socket. Phone and other-candidate sockets
cannot start or receive these captions. Rate limits, packet/sample bounds,
eight recognition slots, bounded queues and cancellation limit resource use.

The current Whisper endpoint transcribes complete files, so captions update in
small batches: expect roughly **three seconds plus provider/network latency**,
not guaranteed word-by-word instant text. AI captions follow Google SSML word
timepoints and actual audio playback position. Native speech fallback uses real
word-boundary events where supported; a legacy response without timepoints shows
the full text when playback starts. No simulated typing or amplitude is used.
See [Google SSML timepoints](https://docs.cloud.google.com/text-to-speech/docs/ssml).
Sending an answer
uses the retained whole recording and the existing `/speech/transcribe` path for
its final authoritative transcript, correcting provisional caption differences.

If captions, sockets or the worklet fail, the UI explains the loss while the
answer recorder continues. Final transcription and retry remain available.
Socket reconnection starts a fresh owned stream while preserving prior captions;
unmount cancels caption processing and releases the additional nodes
without stopping the shared microphone. Audio/text are not logged by the new
caption service; existing provider usage auditing and final answer storage apply.

Incremental windows add provider requests alongside final whole-answer ASR.
Groq bills each request for at least ten seconds, including shorter windows;
allow for this extra usage in cost/quota planning. This is documented in
[Groq Speech to Text](https://console.groq.com/docs/speech-to-text).

## Verification

Run frontend `npm test`, `npm run lint` and `npm run test:interview-ui`, then backend
`venv\Scripts\python.exe -m unittest discover -s tests`. Prepare native fixtures
with frontend `npm run test:voice-runtime:prepare`, then run kiosk
`npm run test:voice-runtime` (unset `ELECTRON_RUN_AS_NODE` for Electron launches).
The native test uses a generated silent-output tone and fixture camera, and
verifies timed question captions during playback, all five WebGL states, real analyser response, the real AudioWorklet,
voice-only layout and disposal. It calls no paid speech provider.

Before release acceptance, speak several real answers on the installed kiosk,
check caption delay/accuracy against the final transcript, test microphone loss
and socket reconnection, confirm question audio intensity changes the sphere,
and finish with both recordings uploaded. Follow the full phone/camera checks in
[monitoring policy](interview-monitoring-policy.md).

# Interview flow audit

Audit date: 8 October 2026. Implementation tracking: [interview-flow-plan.md](interview-flow-plan.md).

## Critical defects found

| Area | Defect | Required correction |
| --- | --- | --- |
| Session access | Answer submission and proctoring events do not consistently verify ownership | Owner-bound REST/socket access before any mutation |
| Mobile | Session ID is treated as pairing authorization, with no live readiness gate | Signed expiring companion capability, single session, camera heartbeat |
| Timing | Setup consumes question deadlines; optional calibration/CDN blocks startup | Separate setup/activation; bound providers; optional calibration |
| Camera | Preview mount and reacquisition races | Reuse a checked media stream and release it on terminal state |
| Engine | Mutable generator context shared across interviews | Independent context and serialized transitions per session |
| Scoring | Face capture and unproctored practice produce unearned 100 | Scores only from analyzed evidence; show disabled/incomplete status |
| Objects | Config promises object detection without a functioning model | Optional configured detector with availability in report |
| Completion | Recording transcoding/upload blocks results | Parallel finalization and direct browser-supported recordings |
| Config | Dual-camera absent and AI flag dropped by normalization | Strict boolean normalization for all supported flags |
| Kiosk | External models block setup and practice face capture is skipped | Guided media checks, shared activation/pairing/report contracts |

## Expected candidate journey

1. Review the session requirements and install/open the GenHire kiosk using the configured official installer.
2. Grant camera/microphone access; see live video, microphone activity, a speaker test and network status.
3. Capture a clear single face. Explain monitoring and identity review before activation.
4. When the recruiter requires two devices, scan the expiring QR link, grant phone camera access, position it to show the workspace, and wait for a fresh live-camera heartbeat.
5. Activate the interview. Start answer deadlines here, deliver a short greeting and relevant questions, preserve retry semantics and display recoverable failures.
6. Submit results without waiting for optional recording processing. Show actual scores or clear pending/unavailable states, evaluation, monitoring coverage and warning evidence.

## Reference behavior checked

- [HackerRank desktop setup](https://candidatesupport.hackerrank.com/articles/5105545533-attempting-tests-using-hackerrank-desktop-app): guided download, permissions and readiness before beginning.
- [HackerRank interview entry](https://support.hackerrank.com/articles/8630831551): compatibility and camera/microphone setup before the interview.
- [Browser media constraints](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia): mobile/browser capture needs a secure context and explicit permissions.

## Verification results

Implementation and local checks completed on 8 October 2026:

| Check | Result |
| --- | --- |
| Backend behavioral suite, Python 3.12 | 74 passed; isolated Mongo/provider stubs, no production interviews charged |
| Frontend interview contracts | 10 passed: score/null handling, accepted-answer reconciliation, signed phone URLs, MIME support, microphone energy, ACKs and HTTP auth |
| Kiosk security contracts | 2 passed: public bundle allowlist/path traversal and safe launch addresses |
| Frontend lint | Zero errors and warnings |
| Web and kiosk production UI bundles | Passed |
| Windows NSIS installer | Local packaging passed with installed official Electron 40.6.1; unsigned installer requires OS/device acceptance before publishing |
| Actual local object-model execution | Available; expected raw output; blank frames return no detections; 178 ms cold, 91 ms warm mean (five frames) |
| Browser visual verification | Unavailable: no enabled browser surfaces in this session |
| Laptop + phone hardware and live providers | Pending acceptance environment |

The previous Python 3.14 environment failed SDK/protobuf compatibility checks.
Use Python 3.11/3.12 (production Docker uses 3.11). The isolated local test
environment used `python-backend/requirements-test.txt` with Python 3.12.

## Deployment acceptance matrix

Run these in an isolated, HTTPS environment with the updated kiosk installer,
Mongo/GCS, speech/LLM credentials and the provisioned detector. Record device,
OS/browser, timings and report IDs for each pass; do not use real candidate data.

- [ ] New candidate: install/open kiosk, upload required identity card, check live camera/microphone/speaker, capture one face and reach the first question.
- [ ] Real job with `dual_camera=false`: no phone requirement. Repeat with `true`: stale heartbeat, camera permission only without frames, and unauthorized pairing must fail activation.
- [ ] Android Chrome and iPhone Safari: pair, position the side camera, background/lock the phone, recover permissions/network, stop and retry native recording upload.
- [ ] Laptop: denied/busy/disconnected camera/microphone, silent mic, blocked speakers, lost socket/offline connection, restored stream, and emergency kiosk exit.
- [ ] Bring a phone/book or a second person into view; check debounced source-labelled warnings and report counts. Measure false positives with normal desk items, varied lighting/skin tones and a permitted companion positioned outside the laptop view.
- [ ] Submit a spoken answer, retry failed transcription, type an answer, repeat a question, retry after a timed-out accepted answer, and finish after the last answer.
- [ ] Practice and real: duplicate start/end requests, zero-answer refunds, slow rubric/CV/identity services, recording storage failure, stale cleanup racing completion, and API restart with persisted answers.
- [ ] Verify actual scores, unavailable/pending/disabled states, late score refresh, recruiter saved reports, identity images and recording parts.
- [ ] Measure click-to-interactive-setup and activation-to-first-question separately at p50/p95 under deployment load. Target 5–10 seconds after required user checks; installation/permission time is separate. The isolated engine setup test enforces under one second without network providers.

Object weights are excluded from Git and must be provisioned before deployment.
Voice detection, true eyeball tracking, optional DeepFace continuity and gaze
heatmaps need separately working pipelines to achieve full coverage; the new
camera path truthfully reports their absence. Current engine/monitoring state
is process-local, so multi-instance live resumption requires a later shared
state implementation. No deployed speed or detection-accuracy claim is made.

## Local deliverables

- Windows installer: `secure-browser-kiosk/dist/Genhire.exe` (97,000,512 bytes).
- Installer SHA256: `793a77f843f01ea5aa0f77b83b16f77e67017bc293457cf5cd00063deea17f51`;
  checksum file: `secure-browser-kiosk/dist/Genhire.exe.sha256`.
- Final packaged ASAR contains the current compiled UI assets; legacy renderer
  and credential files are excluded. Packaging, syntax and contract checks do
  not replace testing the installed application on the target OS.
- The live Flask route-manifest check boots Mongo and application services.
  Run/review it in the isolated acceptance environment rather than against the
  currently shared development/production configuration.

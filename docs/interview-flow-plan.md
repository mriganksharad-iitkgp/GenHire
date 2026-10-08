# Interview flow implementation plan

Started: 8 October 2026. Status: implementation and local verification complete; deployment/device acceptance remains pending.

## Outcome and acceptance criteria

Recruiters can choose laptop-only or required laptop + mobile proctoring when creating or editing a job. Existing jobs remain laptop-only. Both interview types use a guided setup: kiosk installation/opening, laptop camera/microphone/speaker/network checks, a face capture, required phone pairing when enabled, then explicit interview activation. Setup must not consume answer time. Fast startup means reaching an interactive setup promptly and beginning the conversation promptly after required permissions and checks; user installation/permissions cannot be promised within 5–10 seconds.

The interview must retain answers across retries, protect session ownership, show useful connection/device recovery, avoid blocking on optional gaze services or large recording conversion downloads, and explain observed proctoring warnings. Reports must show interview, CV, and proctoring results with truthful unavailable/pending states, evidence and coverage. Detection results are advisory evidence for recruiter review, never proof of cheating.

## Code audit findings

- The UI can request media before its preview mounts, then acquire it again; setup is represented by unchecked assertions rather than live device checks.
- Question deadlines begin before setup finishes. Eye calibration and recording conversion unnecessarily block the conversation and completion.
- Phone links hardcode development origins; some sockets point at a separate server without mobile handlers. Pairing is session-ID-only and does not prove live camera readiness.
- A registered face can yield 100 proctoring points without any analyzed frames; practice reports also fabricate 100. Object warnings are not backed by an active object detector.
- Desktop proctoring controls lack session-owner authentication. The answer endpoint needs the same ownership protection as the question endpoint.
- Shared mutable question-generator state can mix candidate contexts. Background extraction can stall the first real question and evaluation may aggregate placeholder marks.
- The kiosk has a separate runtime with blocking external model/calibration dependencies and incomplete recovery; both runtimes need the same contracts.
- Recruiter configuration normalization drops AI detection and has no dual-camera option.

## Implementation sequence

1. [x] Read the repository and trace web, kiosk, practice, real, socket and report paths.
2. [x] Create this plan and `interview-flow-audit.md` with findings and validation requirements.
3. [x] Add validated recruiter configuration (`dual_camera` default false; preserve AI detection), creation/edit UI, and server-provided session policy.
4. [x] Add secure phone pairing, real camera readiness/heartbeat, owner-authenticated desktop streams, and server activation gates for real and practice interviews.
5. [x] Replace setup assertions with real laptop checks, face capture, and optional/required mobile setup; guide first-time kiosk installation and reopening.
6. [x] Remove startup blockers; isolate candidate engine context, reset time at activation, bound external speech calls, and keep optional gaze/recording work off critical paths.
7. [x] Repair detection/scoring: lazy models, multiple/no-face and configured prohibited-object warnings, debounce events, report detector availability and observed coverage.
8. [x] Repair lifecycle/retries: ownership, repeated start/end/answer behavior, device/network failures, safe completion and recording upload failures.
9. [x] Present interview/CV/proctoring scores, evaluation and evidence consistently at completion and in saved reports.
10. [x] Run focused backend tests, frontend build/lint, kiosk syntax checks and applicable local integration checks; update the audit and this checklist with exact results and remaining deployment requirements.

## Work ownership

- Primary: plan/audit, job configuration/UI, real/practice API lifecycle and result integration.
- Proctoring: pairing, sockets, detection/scoring services, focused tests.
- Interview frontend: setup, camera/mobile pages, conversation/recovery and completion UI.
- Engine/kiosk: candidate context isolation, latency fixes, kiosk setup and onboarding.

## Validation and limits

Use isolated tests with fake collections/media/model providers for security, readiness, score coverage, session timing and retry invariants. Build the existing React app and check changed files for lint failures. Hardware-dependent acceptance requires a laptop and phone over HTTPS with deployed detector dependencies and credentials; record those as pending rather than inventing results. Measure setup/start and answer timings using recorded server/UI metrics. Do not publish/deploy changes during this work.

## Progress log

- Initial audit completed; parallel implementation areas assigned with explicit file ownership and shared API contracts.
- Recruiter configuration, ownership/activation contracts and signed phone pairing implemented. Phone readiness requires a decoded camera preview plus a fresh heartbeat; socket connection alone does not pass.
- Real-start database lease and active-session reuse prevent duplicate paid sessions. Accepted answer responses are persisted for exact retry replay; repeated completion returns stored results.
- Practice CV scoring moved into the background. Both result paths now return measured scores or explicit pending/unavailable status, with deferred rubric refresh when answer evaluation is still running.
- First 11 lifecycle/policy regressions passed. Production frontend build passed at this intermediate point; final validation will be repeated after remaining UI/kiosk integration changes.
- Review found additional setup/finishing cleanup states and bootstrap terminal-status mismatches; these are being corrected before final verification.
- Completed shared React runtime in the kiosk: desktop setup, conversation, recovery and report behavior now comes from the same components. Bundled UI/assets are the only files exposed by the loopback HTTP server. Deep links are queued until the renderer is ready.
- Replaced automatic downloads/focus heuristics with an explicit installation guide for real and practice interviews. Real session creation now happens after the kiosk opens. Practice installation guidance precedes CV selection/session creation.
- Provisioned the official YOLOv8n artifact locally and validated raw `[1,84,8400]` output in OpenCV. Blank-frame inference on this development laptop: 178 ms cold, 91 ms warm mean over five frames. This checks operation/latency, not detection accuracy.
- Corrected natural-language consonant classification, missing transcription retry controls, stale-cleanup races, CV modal closure and supplemental gaze uploads overwriting authoritative monitoring scores.
- Latest verification: 74 backend tests pass on Python 3.12; 10 frontend contract tests and two kiosk security tests pass. Frontend lint reports zero warnings/errors. Web and kiosk production bundles build successfully.
- Browser visual automation is unavailable in this session (no enabled browser surfaces). Real camera/microphone, Android/iOS, kiosk OS restrictions, production network latency and model accuracy remain explicit acceptance checks in the audit.
- Local Windows NSIS installer packaging succeeded using the installed official Electron 40.6.1 runtime after a release-download DNS failure. Installer delivery and device acceptance are separate from publishing; no deployment was performed.
- Final-answer timeout/reload recovery now proceeds to completion instead of asking an already accepted final question. Returning from kiosk completion waits for active uploads and warns before discarding a failed buffered recording; it opens the dashboard and closes the finished kiosk so another interview can launch normally.
- Final installer rebuilt with the latest shared UI; packaged asset verification and credential exclusion passed. Checksum is recorded in the audit. Final lint/build, 74 backend tests, 12 JavaScript contracts and changed-file whitespace checks passed. The temporary local preview server was stopped.

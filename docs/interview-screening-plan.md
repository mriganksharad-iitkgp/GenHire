# Screening sequence and preparation report - 13 October 2026

## Twelve-question contract

| Question | Purpose |
| --- | --- |
| 1 | Brief introduction; Alex introduces himself once. |
| 2 | CV project, internship or experience aligned with the JD. |
| 3 | Follow-up on Q2's answer: one deeper decision, result or trade-off. |
| 4-5 | Two distinct, JD-relevant CV experiences or aspects. |
| 6 | Practical assessment of an essential JD competency. |
| 7 | Follow-up on Q6's answer: deeper application of that competency. |
| 8-9 | Two other JD requirements or responsibilities. |
| 10 | HR behavioral question. |
| 11 | Follow-up on Q10's answer: decision, lesson or outcome. |
| 12 | Distinct HR motivation/goals question. Wait for the answer before completion. |

Questions remain LLM-generated from CV, JD and committed Q/A history. There is no RAG or question-bank lookup.
Follow-ups use fixed positions (3, 7, 11), avoiding a separate planning call. They must probe a new aspect rather than repeat an answered question. A skipped parent answer leads to a simpler hypothetical on that competency; the model must not invent candidate statements.
The stage follows completed answers. Repeats and failed generation do not advance it. Exactly twelve answers (including explicit no-response skips) complete a new attempt.
The checkpoint persists the question limit; legacy attempts without that field retain their previous ten-question length on recovery.
The JD defines role relevance and expected level throughout; CV-match and interview scores remain separate report fields.

### Startup and return fixes

The validator required a literal question mark, rejecting valid spoken instructions such as `Please introduce yourself.` Greeting removal could also consume the question if it shared a sentence with `I'm Alex`. Both paths now have regression coverage. Invalid output gets at most one repair inside the same total deadline; an unrepaired opening shows a retry message instead of validator instructions.

The browser launch carries `returnToExistingTab`. The updated kiosk closes on Back rather than opening another browser tab (login is deliberately scoped to the original tab). Keep the launching tab open and select it after the kiosk closes if the operating system does not foreground it. Arbitrary tab selection in another browser is not guaranteed; if the tab was closed, reopen GenHire and log in normally.
The launch guide closes after leaving for the native app and returning. Application/practice pages refresh on window focus as well as visibility changes. Opening installation help before launch does not dismiss the guide. Failed launches show a retryable message.

## Causes and changes

- The old repeat detector matched `again`, `repeat`, or `already explained` anywhere in an answer, discarded that answer and replayed the question. It now accepts only a standalone request such as `Could you repeat the question?`.
- The generator included its opening-introduction instruction on every turn. Opening and later-turn rules are now separate, with exactly one application-supplied greeting.
- Exact text equality was the only duplicate check. Normalized wording and token overlap now reject close repeats. One repair is allowed within the existing total generation deadline. The prompt also excludes competencies already answered; this is not a guarantee of perfect semantic detection.
- A late media error or rejected play promise could invoke fallback speech after playback ended. Finished playback now detaches handlers and rejects stale callbacks.
- Sustained quieter speech could fall below the onset threshold and be mistaken for silence. The detector now uses a lower release threshold and new caption words as additional speech evidence. Identical caption snapshots cannot indefinitely extend an answer.
- All questions receive a fresh local recording window after playback ends. A regression test holds question-twelve audio for 40 seconds, verifies no answer/end request, then saves the tenth answer before report generation.
- Cloud Run workers with an older in-memory question count now import a newer persisted checkpoint, preserving completed local evaluations and rebuilding the full conversation history. A completed tenth-answer checkpoint also restores for reporting without inventing an eleventh question.

The attached report alone cannot establish exactly which audio/timing event cut off the historical tenth answer. These fixes address identified code paths; a deployed microphone test is still needed.

## Preparation answers

The existing background completion worker now requests one structured report containing the assessment and a suggested answer plus improvement tip for every recorded question, including skipped questions. This call does not delay live next-question generation.

- Uses CV, JD, actual question/answer pairs and verified scoring coverage.
- Gives each answer a stable one-based question number; missing, duplicate or invalid mappings are rejected.
- Requires explicit placeholders or hypothetical wording for unsupported personal claims, rather than invented achievements or metrics.
- Suggested answers never replace candidate evidence or affect the score.
- New report fields: `preparation_status`, and per-question `question_number`, `question_metadata`, `suggested_answer`, `improvement_tip`, `suggested_answer_status`.
- Original records and available scores remain visible when providers cannot generate preparation material. Older reports show that suggestions were not generated; this change does not rewrite historical interviews.
- Report generation has a separate 4096-token output allowance and a 35-second caller budget. Existing asynchronous `/end` polling remains in place.

## Current validation and rollout

The twelve-question lifecycle test verifies all section boundaries and follow-up metadata, waits for answer twelve, and checks that generation failures do not advance the attempt. Intro prompt tests cover missing question marks, same-sentence greetings, repair and friendly failure.

Restart the local backend for the new generator/config. Deploy the backend and frontend, and install the rebuilt kiosk for the return-tab change. Existing installed kiosks do not receive bundled UI updates from a backend deployment.

## Release 1.2.9 verification

Passed: 186 backend tests in the full run plus two added focused regressions (188 distinct tests); 33 frontend helper tests; 28 interview UI scenarios including answer twelve and launch-return recovery; seven kiosk security tests; lint; web and kiosk production builds.
A small synthetic live-provider probe generated an introduction in 2.88 seconds and its CV follow-up in 1.03 seconds. This is not a production latency guarantee. Initial restricted-network attempts failed; the permitted network probe succeeded. No candidate interview was created.

Install `secure-browser-kiosk/dist/Genhire.exe` (version **1.2.9**). Installer: **102,581,890 bytes**; SHA-256 `a51b298dc895d9ebbdd6c3778256a9f1f5b9a7ccc0152bb029685e25906ef9e6`. The matching `.sha256` is beside the installer.

These changes and builds are local. Production source and the hosted installer have not been published here. Existing Cloud Run memory configuration was not changed. Real phone/laptop hardware and operating-system browser focus still require an acceptance run.

Acceptance: keep the original applications tab open, complete all twelve questions including the three follow-ups, return from the kiosk, and verify the original tab is still logged in, its launch dialog closes and its report becomes available. If the report is still processing, refresh the applications list when it finishes.

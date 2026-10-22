# OA and application UI refinement — 22 October 2026

The local source now uses a compact application type scale: 14px body text, 13px controls, 12px supporting text, 20px assessment titles and 22px page headings. The marketing homepage retains its display typography. Mobile form fields use 16px text to avoid browser zoom.

## What changed

### Shared theme follow-up

OA, interviews and the secure-browser entry screen now share one GenHire brand component. Assessment colours now reference the same indigo/lavender theme tokens as the portals instead of a separate purple palette. Cards, dialogs, headers, pagination, toast statuses, loading indicators and empty-state actions use shared colours and geometry. Candidate/recruiter pages use the shared font and card radius.

Interview setup, transcripts and monitoring panels have tighter padding and section gaps while retaining 44px session controls. OA dark mode keeps its readable slate surfaces and inherits the same brand structure. This changes presentation, not session admission, monitoring, timing or submission behavior.

The full frontend `npm run check:oa` passed again after this follow-up, including interview interaction tests, portals, lint and both production builds. Desktop/mobile browser fixtures confirmed matching OA/interview palette tokens, no JavaScript exceptions and no horizontal overflow at 390px. The interview visual fixture uses representative conversation markup with real production styles; real interview behavior is exercised by the automated interaction suite. Kiosk tests (10), native formatter/CSP check and Windows installer packaging also passed again. Logs: `.tmp/theme-*.log`.

- Coding, SQL and MCQ questions share consistent typography, smaller section gaps and compact sample tables. MCQ options use only the space their content requires.
- The assessment landing page has shorter instructions, a compact section overview and a clearer entry action. The workspace retains GenHire colours, light/dark themes, question navigation, review flags, autosave status and resizable problem/editor panels.
- The editor provides **Format code**, undo, redo, find, reset confirmation, font size and editor focus. **Shift+Alt+F** formats code. Formatting is an undoable edit; it does not discard newer edits while a formatter is loading.
- Python, C, C++, Java, JavaScript/Node.js and SQL formatting runs locally using bundled engines. Source is not sent to a formatting service. Invalid formatting leaves edits intact. Built-in starter/reference programs and SQL schemas now use readable multiline source; new AI drafts are instructed to do the same.
- Job creation/editing share a compact form with section navigation, collapsed optional templates, smaller question editors and compact MCQ option rows. The existing authoring, pricing and review workflow remains in place.
- Shared portal typography, form controls, help text and interaction states apply across application pages. The normal candidate OA still follows secure-browser launch requirements; the localhost developer preview remains a separate development-only tool.
- Interview preparation now caches both heuristic and model-derived metadata in Redis, with separate mode/model keys. Permissions, wallets, submissions and grades continue to use their authoritative database paths. See [Redis verification](REDIS_AND_DOCKER_READINESS.md).

## Verified locally

- Full frontend `npm run check:oa`: regression suites, lint, production web and kiosk builds, and developer-preview exclusion passed.
- Backend: **493 tests, 490 passed, 3 opt-in skips**. Shared-cache suite: **10 passed**.
- Browser checks: desktop/mobile, light/dark, coding/SQL/MCQ/landing and job creation/editor layouts; no horizontal overflow in the tested mobile workspace. Format → undo → redo and find passed with no JavaScript exceptions.
- Kiosk: **10 native security/asset tests passed**. All six formatter engines passed in hidden Electron under the production CSP, including WASM loading, string-literal preservation and invalid-Python rejection.
- Linux image `genhire-backend:oa-refinement-20261022`: build, actual Gunicorn startup, HTTP health, installed dependency consistency, cross-process Redis sharing, authentication guard and Redis-outage readiness passed with disposable Mongo/Redis containers.
- Windows installer rebuilt. All **38** bundled web files match the fresh kiosk build byte for byte. Private dotenv and developer-preview artifacts are excluded.

These checks do not replace real candidate-device, camera, invitation, provider, cloud-IAM and cohort acceptance. No production deployment or upload was performed.

## Your next steps

1. Preview locally using [the developer testing instructions](OA_LOCAL_DEVELOPER_TESTING.md). Start the harness and open the fresh URL it prints; previous temporary URLs expire when that process stops.
2. Review and push source through your usual deployment workflow. A page already open on **genhire.in** uses the deployed version; local source changes appear there after a successful deployment. Check the current job form after deployment and a fresh reload.
3. Upload [the rebuilt Windows installer](secure-browser-kiosk/dist/Genhire.exe) and its [checksum](secure-browser-kiosk/dist/Genhire.exe.sha256) using [the deployment handoff](DEPLOYMENT_BUILD_CHECK.md). Version remains **1.3.0**, matching the configured kiosk release ID. Existing installed copies need an update.
4. Verify a real secure launch on Windows after installing the new file. No new environment fields are required for these UI/cache changes. Preserve the production Upstash secret, Aiven CA mount and existing runtime configuration.

Installer size: **104,566,497 bytes**. SHA-256: `c7b134cf90ac72ffbd2b5b33cb550858ba4d388785ebeeacffba0a0fe2269d79`. Authenticode: **NotSigned**; no signing certificate is configured.

Verification logs are in ignored `.tmp/oa-density-*.log` and `.tmp/oa-refinement-*.log` files.

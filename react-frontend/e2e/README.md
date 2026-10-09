# End-to-end tests

Browser + API tests that run the **real** GenHire stack on your machine. They
cover the flows in [`docs/SMOKE_CHECKLIST.md`](../../docs/SMOKE_CHECKLIST.md)
and also exercise the Flask backend directly.

```bash
cd react-frontend
npm run test:e2e          # everything except the paid AI specs (~1 minute)
npm run test:e2e:ai       # …plus specs that call real LLM providers (costs credits)
npm run test:e2e:ui       # Playwright's interactive UI mode
npm run test:e2e -- specs/ui/auth.spec.js         # any Playwright args work
```

## Prerequisites

* Node 18+ and the frontend dependencies (`cd react-frontend && npm install`).
* The backend virtualenv with its requirements installed
  (`cd python-backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt`,
  see [`docs/onboarding.md`](../../docs/onboarding.md)). The runner checks this and prints the fix if it's wrong.
* Nothing else: no Docker, no MongoDB install, no cloud credentials, nothing to seed. The database is
  created empty on every run and the harness seeds its own admin account into it.
* A working LLM key in `python-backend/.env` only if you run `npm run test:e2e:ai`.

That one command starts everything, runs the tests and shuts everything down.
The first run installs the test tooling (`e2e/package.json`) and downloads
Chromium and a MongoDB binary (~200 MB, once).

The test tooling has its **own `package.json` on purpose**: `mongodb-memory-server`
downloads a MongoDB binary in its `postinstall`, which must never run as part
of the production (Vercel) `npm install` of `react-frontend`.

## What is real, what is faked

| Piece | In the tests | Why |
|---|---|---|
| Backend (`python-backend`) | **Real, unmodified** (own port 5100) | This is what we want to test. |
| Frontend | **Real** Vite dev server (own port 3100) | Your normal dev servers on 3000/5000 can keep running. |
| MongoDB | Throw-away **in-memory** instance | Your Atlas dev cluster is never touched. Fresh and empty every run. |
| Google Cloud Storage | Small in-process **fake** (`harness/fake-gcs.mjs`) | The backend refuses to boot without GCS; the fake speaks just enough of the API. |
| Email | `EMAIL_PROVIDER=noop` | Nothing is sent. Tests read reset / verification tokens from the test DB instead. |
| Payments (Razorpay) | Not configured | Payment *pages* are tested, not real payments. |
| LLM providers | Dummy keys → calls fail instantly. **Real** keys only with `--ai`. | No stray spend. |
| Webcam / microphone | Chromium's fake devices | No hardware needed. |

### Safety
`harness/safety.mjs` builds the backend's environment **from scratch**. The
backend always loads `python-backend/.env`, which on a dev machine points at
Atlas, a live Razorpay key and a real mail provider — so every secret-looking
key found in `.env` is blanked first, and the run aborts if the Mongo URI isn't
local, email isn't `noop`, or any payment/email key is still set. Only the LLM
keys are copied over, and only with `--ai`.

## Layout

```
e2e/
  package.json, playwright.config.js
  harness/     the one-command runner: run.mjs, stack.mjs, safety.mjs, fake-gcs.mjs, seed_admin.py, global-setup.mjs
  fixtures/    test.js — logged-in pages per role, fail-on-error guards, known-bug probe
  helpers/     api.js (create users/jobs/CVs via the real API), db.js, files.js (generated PDF/PNG), ui.js, ai.js
  specs/api/   backend contract tests (no browser)
  specs/ui/    browser flows, one file per area of the smoke checklist
  specs/ai/    @ai specs (real LLMs)
```

Test IDs map to the smoke checklist: `API-xx` backend, `UI-AUTH`/`CAND`/`REC`/`ADM`/`PAY`/`PUB`/`PRAC`/`INT`/`ROUTE`, `AI-xx`.

## Writing tests

* Create data through the **API helpers** (`createUser`, `createJob`, …) and test the *UI* on top of it. Every test makes its own users; names/emails are unique per run.
* Use `asUser(user)` for a page that is already logged in (the app keeps its session in `sessionStorage`; the fixture seeds it).
* Prefer `getByRole` / `getByPlaceholder` / visible text. Many buttons carry icon glyphs, so the `button(page, 'Label')` helper in `helpers/ui.js` matches on visible text. Nav links exist twice (desktop + mobile menu) — use `:visible` / `.first()`.
* The test database lives for the whole run — never assert on global counts or fixed names.
* Every page fails its test on an uncaught JS error or an API 5xx. For an *expected* 5xx, add `test.info().annotations.push({ type: 'allow-5xx' })`.
* Test output (traces, reports, logs) goes to the OS temp dir, **not** the repo: Vite watches the project and reloads the page under test whenever a file appears in it. The run prints the exact folder at the end (`npx playwright show-report <dir>/report` to open it).
* To iterate on a single spec without restarting the stack each time:
  `node e2e/harness/run.mjs --stack-only`, then in another shell, from `react-frontend/e2e`,
  `set -a; . $TMPDIR/genhire-e2e-results/stack.env; set +a; npx playwright test specs/ui/auth.spec.js`.

## Known product bugs this suite found

Specs that hit them are skipped (`test.fixme`) or marked as expected failures
(`test.fail`) with a comment — they **start running / flip automatically once the
bug is fixed**. Expected failures show as `✘` in the list reporter but count as passed.

1. **Blank pages: `InterviewReportModal` crashes on mount** (`features/interview/components/InterviewReportModal.jsx`, `resultScore(report)` with `report === null`; introduced by `e7d81f7`). The candidate profile, the recruiter dashboard and the admin candidate-detail page all render blank, because the root `ErrorBoundary`'s fallback renders a `<Link>` outside the Router and crashes too. One-line fix: `resultScore(report || {})`. Gated by the `bugs.reportModalCrash()` probe in `fixtures/test.js`.
2. **"View Candidates (N)" on a job card shows "No applications found"** — `RecruiterDashboard.handleViewJobCandidates` sets the filter to `job.title`, the filter compares `job_id`. (`UI-REC-07`, `test.fail`.)
3. **`GET /api/admin/system/stats` returns 500** — `if self.interviews_collection:` is invalid on PyMongo 4 collections (`controllers/admin/base.py`). (`API-12d2`, `test.fail`.)

## What is not covered (and why)

* Real payments (Razorpay) and real email delivery.
* Text-to-speech / speech-to-text: both use Google Cloud, and there are no Google credentials in the repo's `.env`.
* Face capture in the interview (`Capture my face`): needs `opencv-python-headless` in the backend venv (the runner warns if it's missing) and a real face; the `@ai` interview spec records that step directly in the test DB.
* The "identity card required before an interview" rule: the stack runs with `FACE_VERIFICATION_MODE=off`.
* Running a full live interview in the secure kiosk app.

## Troubleshooting

* **"Port … is in use"** — the stack uses 27117 (Mongo), 4443 (fake GCS), 5100 (API), 3100 (web). Stop whatever holds them.
* **Backend won't start** — read `<results dir>/logs/backend.log`. A missing package usually means `pip install -r requirements.txt` in `python-backend`.
* **`@ai` specs skipped** — the run prints why (the provider's own error, e.g. exhausted credits). Fix the key in `python-backend/.env` and re-run.

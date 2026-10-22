# Four deployment checks — 22 October 2026

Remote results inspected for commit `4ba5239d3ff32c1b0d980696d0e47f5c725b96bf`:

| Check | Observed result | Fix |
| --- | --- | --- |
| Vercel | Failed at Vite configuration: `VITE_VERCEL_GIT_REPO_ID` rejected | Discard exact documented Vercel metadata names before exposing application env values; unknown keys and server secrets still fail |
| OA local readiness / frontend-and-kiosk | Failed spawning ignored local `python-backend/venv/bin/python` | Provision Python 3.12 and PyMongo on the runner; select it through the already-supported `GENHIRE_TEST_PYTHON` setting |
| OA local readiness / backend | Failed importing `fakeredis`; WebSocket heartbeat test lacked `websocket-client` | Declare `fakeredis[lua]` and `websocket-client` in test-only requirements |
| genhire-main-deploy / GCP | **SUCCESS**, including Build, Push and Deploy | No cloud configuration change required by these fixes |

Vercel documents its injected metadata in [framework environment variables](https://vercel.com/docs/environment-variables/framework-environment-variables). The build now discards those values instead of embedding them. This covers both Vite and CRA names, with an explicit list rather than a broad prefix exemption. Regression tests confirm unknown similarly named secrets are still rejected without printing values.

Both supported Vercel root configurations now use `npm ci` to install the committed lockfile reproducibly. The frontend CI job also injects a synthetic Vercel metadata key to exercise this deployment case on future runs.

No private env values need to be changed. The npm dependency audit notices and platform-generated npm configuration warnings shown in the screenshot are separate from the fatal env guard error; this patch does not claim a clean dependency audit.

The failed historical commit will retain its failed checks. The fixes must be committed and pushed to trigger four new checks; rerunning that old commit cannot pick up changed source. A push to `main` also invokes the linked production Vercel/GCP deployments.

Local verification logs: `.tmp/four-checks-frontend.log`, `.tmp/four-checks-clean-fixtures.log`, `.tmp/four-checks-backend.log`, `.tmp/four-checks-env-tests.log`. Remote diagnostic downloads are ignored under `.tmp/github-*.log`.

## Verification completed

- Full frontend `npm run check:oa` with synthetic Vercel metadata: **passed**, including lint, application regressions, production web/kiosk builds and developer-preview exclusion. Production assets contain neither synthetic metadata value.
- UI fixture suites in a fresh isolated Python environment containing only PyMongo and its dependencies (plus Windows timezone data): **passed**. They do not require the application's private dotenv or a database.
- Full backend suite against disposable local Mongo, with the same opt-in load setting as CI: **493 tests, 491 passed, 2 paid acceptance tests skipped**. Redis/cache and actual WebSocket heartbeat checks passed; the 100-client load phases had no errors. This is local validation, not a production capacity assertion.
- Environment tooling: **24 passed**. Kiosk security/assets: **10 passed**. Workflow YAML and both Vercel configs validated.
- Existing deployed Cloud Run `/health`: **HTTP 200**, database connected, request protection available.

All three observed source/configuration causes are fixed locally. New remote green results can only be confirmed after the fixed commit is pushed and all four services finish their checks. No credentials, runtime acceptance flags or cloud IAM settings were changed.

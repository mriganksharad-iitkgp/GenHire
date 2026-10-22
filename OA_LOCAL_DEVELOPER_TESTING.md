# Local OA testing without taking an exam

The developer preview uses the real candidate `Assessment` component and Monaco editor, prefilled answers, production answer validation/revision receipts, immutable submission, public-run service, Mongo execution queue, OnlineCompiler adapter, typed SQL comparison and deterministic scoring.

It creates a disposable loopback MongoDB replica set and a synthetic already-started practice attempt: **3 coding + 2 SQL + 20 MCQ**. There is no login, invitation delivery, secure-browser launch, visible countdown, real wallet charge or production database access. The normal application backend does not need to be running. This is developer testing, not production isolation acceptance or a real candidate result.

## Start it

From the repository root, in one PowerShell terminal:

```powershell
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/oa_preview.py
```

In a second terminal:

```powershell
cd react-frontend
npm.cmd start -- --host 127.0.0.1 --strictPort
```

Open the **complete developer URL printed by the first command**. It starts with `http://localhost:3000/dev/oa#token=...`. The token authorizes only this local disposable harness; no compiler credential enters the browser. The page remembers that local connection in this tab's session storage. Restarting the harness creates a new token, so open the newly printed URL after a restart.

The launcher reads only the OnlineCompiler key/base URL from `python-backend/.env`. It does not use your application MongoDB URI or Aiven credentials. All database writes use a fresh `genhire_oa_preview_*` database on the Mongo process it starts. Background jobs in the real app are not started. Stop with Ctrl+C; the temporary database is discarded.

The existing local Mongo executable at `.tmp/oa-step1-mongo/mongod.exe` is detected automatically. Otherwise install MongoDB and pass `--mongod C:/path/to/mongod.exe`. Optional `--port 5012 --frontend-port 3000` changes the loopback harness port. The frontend must run in Vite development mode; the preview is absent from production web/kiosk builds, and `scripts/dev/` is excluded from the backend Docker image.

## Use the page

- The preview opens on the branded assessment instructions and section breakdown. Click **Enter developer workspace** to inspect the candidate experience. **Developer tools · localhost** stays collapsed above the page; expand it for fixture selectors, grading checks and provider usage.
- The workspace shows one question at a time, with a numbered Coding/SQL/MCQ sidebar, review bookmarks and **Save & next**. Coding and SQL use a resizable problem/editor split with Monaco open immediately. Use the theme toggle, font-size selector or editor focus button to adjust the workspace. SQL samples and results appear as tables; **Examples** and **Schema** tabs keep reference material accessible.
- **Load editable preview:** prefill correct answers for all 25 questions. Inspect the candidate layout, change languages, edit code/SQL and test autosave/reload.
- **Run public example / Run custom input:** actual provider execution through the normal public-run service and queue. SQL uses only its sample dataset. Code supports the displayed languages and custom stdin/typed input.
- **Test final submission:** submit your saved edits through the real immutable submission and grading pipeline. The top panel shows actual score, section results, case verdicts, queue states and provider usage.
- **Check correct submission:** one click creates, saves and submits the known correct fixture. Expected score: **100%**.
- **Check wrong submission:** expected score: **0%**.
- **Check compiler failure:** the first coding answer is invalid C++; the other answers are correct. Expected score: **80%**, with a compile-error case.
- Select **SQLite/DuckDB** or **standard input/output/typed function** before loading or checking a new fixture. After completion, load another editable preview to continue.

Each final fixture submission grades **seven cases**, hence seven provider runs: three hidden coding cases plus two datasets for each SQL question. The twenty MCQs use no compiler runs. Public Run consumes additional runs. These small fixtures keep developer verification cheap; they do not replace the normal 15–20-case authored coding suites or validation of actual recruiter questions. The account's rate/concurrency limits still apply. Wait for pending work before resetting. Unknown execution is retained for review and never automatically replayed; restart this disposable harness to abandon that local session after investigating it.

## Headless checks

These commands exercise real saved answers, submission snapshots, queue dispatch, provider execution and final scoring without opening a browser. They consume seven provider runs each:

```powershell
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/oa_preview.py --self-check
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/oa_preview.py --self-check --scenario wrong
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/oa_preview.py --self-check --engine duckdb --contract function
python-backend/venv/Scripts/python.exe python-backend/scripts/dev/oa_preview.py --self-check --engine duckdb --scenario compile_error
```

Verified live on 22 October 2026: these four checks completed with scores **100%, 0%, 100%, 80%**, respectively. Each completed seven execution tasks using the saved local key. The first sandbox-restricted attempt could not reach the provider and timed out without fabricating a result; the network-enabled runs above passed.

The redesigned workspace was also checked in a real Chromium browser at desktop and mobile sizes, in light and dark themes, with Monaco loaded. Real public runs from the page returned `2` for the saved C++ echo solution and the expected SQLite revenue table (`East: 30`, `West: 7`). Navigating to another question did not display the previous question's output. These checks left the editable assessment unsubmitted.

Offline automated checks cover loopback/database/token/origin restrictions, prefilled candidate serialization, both SQL dialects/contracts, actual immutable submission, public-run admission, React controls and exclusion from production bundles. `npm run check:oa` includes the new preview smoke and artifact-exclusion checks.

This confirms the tested execution/submission paths. Real job content, invitation admission, device/proctoring, production workers, release permissions, billing and full cohort capacity still need their existing staging acceptance. No production attestation is created by this developer tool.

## Cloud Build warning and pushing changes

The warning on Cloud Run describes the **container image**: a linked Cloud Build trigger deploys its own image on its next run. An image-only update normally retains runtime env/secret configuration; a deployment that replaces env/secrets or the service YAML can change it. Check the external trigger's deployment arguments before pushing to its production branch. [Cloud Run deployment options](https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy).

Your backend private dotenv files are Git-ignored and excluded by `.dockerignore`, and the loader uses `override=False`. A build cannot obtain old private credentials from these files in the repository; Cloud Run variables take precedence. Frontend public env values are compiled at build time and are a separate concern. [Cloud Run environment configuration](https://docs.cloud.google.com/run/docs/configuring/services/environment-variables).

No Cloud Build deploy definition was found in this repository. Its external trigger was not inspected; a screenshot cannot establish its exact configuration. In Cloud Build → Triggers, inspect the deploy step for replacement flags such as `--set-env-vars`, `--env-vars-file`, `--set-secrets`, `--clear-*`, or `services replace`. Preserve the final runtime variables and CA secret mount. Do not share raw secret values when reviewing those settings.

Push reviewed source to a branch you have confirmed does not auto-deploy. Hold the production-trigger branch until the local checks, deployed env/mount configuration, current executor acceptance and intended worker rollout are reviewed. All-true flags or a healthy Cloud Run startup are not evidence of that acceptance. No commit, push or deployment was performed by this work.

## Compact workspace and local code formatting

See [OA UI refinement](OA_UI_REFINEMENT.md) for the current typography, compact MCQ/JD layouts and validation. In the editor use **Format code** or **Shift+Alt+F**, then undo/redo or find from the toolbar. Formatters are bundled locally in the website and kiosk. To see the real deployed candidate UI, install the current kiosk and complete the existing staging secure-launch checks; the developer preview deliberately omits those gates.

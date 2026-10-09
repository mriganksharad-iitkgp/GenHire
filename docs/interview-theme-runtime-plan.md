# Backend startup and remaining interface plan

Keep the current landing layout and lavender/purple theme. Preserve the existing
interview, identity, proctoring and payment contracts.

- [x] Diagnose the active Python environment and add an explicit local runtime check/launcher.
- [x] Verify backend boot and health with the selected environment.
- [x] Align interview preparation, active interview, reports, mobile companion and kiosk entry with the shared theme.
- [x] Refine create/edit/view job dialogs and replace decorative/promotional wording with clear labels.
- [x] Audit remaining account recovery, billing and admin surfaces for scoped theme consistency.
- [x] Run appropriate backend, frontend and kiosk checks; document the flow and limitations.

Audit: the root `.venv` is Python 3.14 with missing packages and conflicting Google
dependencies. `python-backend/venv` is Python 3.12 with the declared runtime packages
and a clean `pip check`. Activation scripts contain paths from a previous workspace
location, so interpreter selection should use an explicit executable.

The live interview UI and the kiosk bundle share `Chat` and its CSS module. Styling
that shared component updates both without duplicating the interview workflow.
The old Electron HTML/renderer files are not the active UI bundle.

## Backend findings and resolution

The Bash activation scripts still refer to the old `D:\GenHire` folder, so an
activated prompt can select the wrong Python. The root environment also uses
Python 3.14 and lacks multiple runtime packages. Requirements already declare
Flask-SocketIO; this was an environment/setup failure, not a missing declaration.
The backend Python 3.12 environment now has the missing pinned OpenCV wheel and
passes `pip check`.

`core/runtime.py` checks package availability before heavy local startup imports.
`dev.py` and direct `python app.py` select a complete Python 3.11/3.12 backend
interpreter. Production imports through gunicorn keep their original behavior.
The check command does not load credentials or connect to the database.

Startup also failed because `uq_applications_job_student` already existed as a
sparse unique index, while the code requested a partial unique index with the
same name. `config/indexes.py` reuses compatible full, sparse or equivalent partial
unique indexes, including reversed compound key order. Restrictive partial filters
are not accepted. No application rows or indexes were deleted. Startup still
rejects noncanonical identity data and duplicate records.

A local verification backend returned HTTP 200 from `/health`; unauthenticated `/api/me`
returns 401. New startup/index tests (5) and existing request/concurrency protection
tests (35) pass.

## Starting the backend in Git Bash

```bash
cd /d/Projects/GenHire/python-backend
python dev.py --check
python dev.py --no-reload
```

The original `python app.py` command also checks/selects the environment and remains
in the foreground. The current local configuration disables the watcher; set
`GENHIRE_DEV_RELOAD=1` to enable it. Use the explicit executable if needed:

```bash
./venv/Scripts/python.exe app.py
```

To set up a fresh environment, use Python 3.12, then install the complete declared
requirements rather than individual packages in a different interpreter:

```bash
py -3.12 -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe -m pip check
```

## Remaining interface changes

- Interview preparation, face/phone steps, active questions, reconnect/error
  states, result cards and report dialogs share landing-derived tokens. Primary
  controls stay purple with white hover text. Camera previews and status colors
  retain their meaning. Questions are not truncated; smaller screens stack panels.
- The kiosk imports the same tokens and a local font/reset stylesheet, preventing
  default browser typography. It uses the shared Chat flow rather than a second UI.
- Create/edit/view job dialogs use matching gradient headers, rounded surfaces,
  restrained typography and visible focus states. Create/edit share monitoring
  labels and accessible toggles with unchanged API keys and billing settings.
- Recovery pages reuse AuthShell and the standard form sizing. Invitation text,
  admin navigation/headers and billing surfaces use the same palette.
- Payment return pages use role-aware dashboard/wallet links and no dead support
  route. They do not assert settled payment or absence of charges from a return
  URL alone; the confirmed status remains in wallet transaction history.
- The landing layout, credentials and provider configuration remain unchanged.

## Verification limits

No browser is connected. Component/CSS fixture checks cover rendering, navigation,
contrast and media rules; they do not verify actual browser geometry or camera,
biometric, microphone, provider response or native kiosk execution. No real
interview, payment or account mutation was used for these UI checks.

## Final checks

- Backend environment: `python dev.py --check` and backend `pip check` passed.
- Backend health: HTTP 200; unauthenticated account check: HTTP 401; Socket.IO
  polling handshake: HTTP 200 with the expected opening packet.
- `test_runtime_startup.py`: 5 tests passed, including compatible unique index
  reuse and continued duplicate rejection.
- `test_request_robustness.py`: 35 tests passed, including concurrency, durable
  scoring, rate limits, overload and invalid legacy identity/index data.
- Frontend contracts: 16 passed. Actual-component portal checks: 44 passed,
  including interview setup/result states, missing mobile token, installation
  confirmation, recovery controls, monitoring labels and role-aware payment links.
- Frontend lint, web production build and kiosk UI production build passed.
- Kiosk runtime-security tests: 2 passed.
- At that earlier checkpoint, `git diff --check` passed and landing source/CSS
  were unchanged. Environment organization is covered in the subsequent audit.

- Windows installer packaging passed: `secure-browser-kiosk/dist/Genhire.exe`
  (97,001,118 bytes). The packaged ASAR contains the shared theme, system font
  and current kiosk entry bundle. The installer was not installed or published;
  the configured cloud download is unchanged.

The latest foreground-startup verification used a separate port and was stopped
after checking health and port conflicts. No assistant-owned backend remains
running. See [the current startup/configuration audit](local-startup-launch-env-plan.md)
for the additional startup tests and environment organization.

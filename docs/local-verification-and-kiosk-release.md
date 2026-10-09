# Local verification and Windows kiosk release 1.2.1

Verified on 9 October 2026.

## Rebuilt installer

The Windows installer is available at:

```text
secure-browser-kiosk/dist/Genhire.exe
secure-browser-kiosk/dist/Genhire.exe.sha256
secure-browser-kiosk/dist/Genhire.exe.blockmap
```

- Application version: **1.2.1**.
- Installer size: **97,003,905 bytes**.
- SHA-256: `e75f4af5a7857db56095a834592aa3ed92d1a5e3ac1f9abea0feace0a490afc6`.
- The packaged application contains the latest shared interview JavaScript and
  CSS, verified byte-for-byte against the kiosk build output. The package includes
  the new answer format controls, device recovery dialog and phone pairing action.
- Windows executable metadata reports file version `1.2.1` and product version
  `1.2.1.0`. The packaged Electron binary's command-line runtime check exits
  successfully. The two kiosk runtime/security tests pass.

Run the installer to update an existing installation, then open the secure
browser from My Applications. Packaging an installer does not automatically
update installed copies.

The public download location was not updated in this task. To make this build
available to candidates, publish the tested installer through the existing
release workflow at the configured `REACT_APP_KIOSK_DOWNLOAD_URL`. Keep the
checksum with the release. This Windows build does not provide a Mac installer.

## Backend runtime repair

Both `python-backend/venv` and `.venv-tests` referenced a Python 3.12 executable
that no longer existed at their original installation path. Their installed
packages were present, but the Windows virtual-environment redirectors could
not start the base interpreter. The available `python` command was Python 3.14,
which is outside this backend's supported 3.11/3.12 range.

The repair adds a project-local Python 3.12.10 runtime from the
[official CPython NuGet package](https://www.nuget.org/packages/python/3.12.10)
under the ignored `python-backend/venv/.base-python312` directory. Its executable
has a valid Python Software Foundation signature. Both virtual environments
were refreshed with that interpreter while retaining their installed packages.
Their original `pyvenv.cfg` files were backed up beside the repaired files.
No system PATH, registry settings or dotenv credentials were changed.

The [Python Windows documentation](https://docs.python.org/3.12/using/windows.html#the-nuget-org-packages)
describes these application-local packages. Virtual environments remain local
machine artifacts: if moving or recreating this checkout, create a new environment
with a supported interpreter and reinstall the pinned requirements.

Verified:

```text
python dev.py --check                          Dependencies: ready
venv/Scripts/python.exe -m pip check           No broken requirements found
python app.py                                 Starts and stays in the foreground
GET http://127.0.0.1:5000/health                HTTP 200, healthy
```

The normal `python app.py` command now hands off from Python 3.14 to the repaired
backend Python 3.12.10 and retains the foreground process. The HTTP server uses
the existing local configuration and connects successfully to MongoDB. Mandatory
GCS configuration initializes successfully.

For verification only, the process used `GENHIRE_DEV_RELOAD=0` and
`GENHIRE_DISABLE_JOBS=1` to avoid a duplicate reloader and scheduled work against
the configured database. These were process overrides, not dotenv edits. Normal
startup restores the existing configured job behavior. The startup wallet
bootstrap reported zero new bonus grants.

## Local frontend and API checks

The frontend was started with:

```powershell
cd react-frontend
npm.cmd start -- --host 127.0.0.1 --port 3000 --strictPort
```

Landing, login, signup, applications, profile and recruiter route requests return
HTTP 200. The changed interview/application modules and route module compile
successfully through the running Vite server. Its `/@vite/env` shim uses
`http://127.0.0.1:5000` and `http://127.0.0.1:5000/api`, matching local configuration.

Read-only checks against the running backend confirmed:

| Request | Expected and observed result |
| --- | --- |
| `GET /` | 200 |
| `GET /health` | 200, MongoDB connected and request protection available |
| `GET /api/me` without a token | 401 |
| `GET /api/applications` without a token | 401 |
| `GET /api/jobs` without a token | 401 |
| Unknown route | 404 JSON error |
| `OPTIONS /api/login` from `http://localhost:3000` | 200 with matching CORS origin |

The tested GET responses include the expected CORS origin and request ID. No
authenticated account, payment, provider or candidate-data request was made.
Restricted sandbox networking blocked the first MongoDB DNS attempt; the same
configuration starts and passes readiness with normal network access.

## Regression checks

- Backend: **118 tests passed**, covering interview lifecycle, recovery, billing
  idempotency, provider fallback, monitoring, startup and request protection.
- Frontend: **16 contract tests, 50 portal checks and 10 interview usability
  checks passed**. The component checks use offline API/socket/media fixtures.
- Kiosk: **2 runtime/security tests passed**.
- Windows installer build: `npm.cmd run dist:win` passed. Its pre-build hook
  recompiles the shared kiosk UI.
- The frontend web build, kiosk web build and frontend lint passed during the
  preceding UI verification. No frontend source was changed after those checks.

## Remaining owner configuration and manual review

The local environment validator reports zero errors and three existing notices:

1. `DEEPSEEK_API_KEY` is empty. That provider cannot run without its key; the
   configured fallback providers can still be used. Supply the key if DeepSeek
   is intended to participate.
2. `RAZORPAY_WEBHOOK_SECRET` is empty. Supply the signing secret for the configured
   webhook before expecting verified payment webhook processing.
3. `MOBILE_RECORDING_ENABLED` is false. Jobs requiring a second camera cannot
   start until the owner enables and verifies the companion recording feature.

Follow [the service setup checklist](required-setup-and-rate-limits.md) and
[environment configuration](environment-configuration.md) for configuration
instructions. Credentials cannot be generated by the application.

No browser or native app surface is connected to the verification tools.
HTTP startup, compilation, component behavior, packaged contents and binary
execution were checked. Visual browser review, installation/reinstallation,
custom-protocol launch, real camera/microphone/phone capture, authenticated
interviews and real recording uploads still require the manual steps in
[the interview usability checklist](interview-usability-improvements.md#manual-review-before-release).

The verification frontend and backend processes are stopped after checking,
so ports 3000 and 5000 are free for normal local startup.

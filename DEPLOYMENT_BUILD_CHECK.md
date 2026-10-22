# Deployment build check — 22 October 2026

Local checks pass and the Windows kiosk installer has been rebuilt. No Git push, cloud deployment or download upload was performed. **Follow-up: Docker Desktop is now available; the Linux image build, production Gunicorn startup and Redis/cache/outage smoke tests passed.** See [Redis and Docker verification](REDIS_AND_DOCKER_READINESS.md) for the updated backend results and CI checks. External GCP/Vercel configuration was not inspected.

## Results

| Check | Result |
| --- | --- |
| Full backend suite, disposable Mongo replica set | Updated after Redis changes: 493 tests, 490 passed, 3 opt-in tests skipped |
| Local 100-client CI benchmark, run separately | Passed; zero phase errors and no billing/workflow reconciliation issues; no provider calls |
| Environment/schema regression tests | 24 passed |
| Python syntax | 337 source files passed |
| Installed Python dependency consistency | `pip check` passed |
| Linux Docker image and production startup | Passed, including installed dependency consistency, shared Redis caching and outage readiness; see the Redis/Docker report |
| Fresh production dependency resolution | `pip install --dry-run --ignore-installed -r python-backend/requirements.txt` passed on Windows/Python 3.12; no packages changed |
| Frontend full `npm run check:oa` | Passed, including regression suites, lint, production web build, kiosk UI build and developer-preview exclusion |
| Frontend and kiosk npm dependency trees | Passed |
| Kiosk native/security/built-asset tests | 10 passed |
| Hidden Electron formatter runtime | Six bundled languages, WASM and production CSP passed |
| Hidden Electron face runtime | Bundled model, WASM and kiosk CSP passed |
| Hidden Electron voice/interview runtime | WebGL, Web Audio, worklet, captions, responsive layout and cleanup passed |
| Windows x64 NSIS installer | `npm run dist:win` passed |
| Packaged contents | All 38 web files match the fresh kiosk build byte for byte; Monaco worker included; no dotenv or developer-preview files |
| Packaged executable | Exit 0; Electron 40.6.1, Node 24.13.1, x64 |
| Local backend object detector | ONNX loads and inference output is `(1, 84, 8400)` |
| Current backend credential literals in Git-visible text files | None found; this is a targeted check, not a complete secret-history audit |

The three default-suite skips were two paid AI/provider acceptance tests and the opt-in local load benchmark. The benchmark was then run separately and passed. Its local start p95 was about 24 seconds under shared-wallet contention; this does not establish production capacity. Its scope excludes HTTP, Redis, devices, GCS and provider latency.

Logs are in the ignored `.tmp/release-*.log` files. The synthetic benchmark result is `.tmp/oa-step10-load.json`.

## Fix made during these checks

The environment auditor incorrectly required a `REDIS_URL` line in the private production dotenv even with `--allow-runtime-secrets`. It now permits that one production omission when explicitly requested, while retaining other key/order checks and rejecting malformed supplied Redis URLs. A regression test covers the exception. No credentials or private env values were changed.

```powershell
python-backend/venv/Scripts/python.exe scripts/check_environment.py --profile production --allow-runtime-secrets
```

Result: **0 errors, 5 configuration/acceptance notices**. This does not inspect the deployed Redis secret reference.

The first native smoke attempt inherited `ELECTRON_RUN_AS_NODE=1` from the development shell. Rerunning with that variable removed passed; this was a test-process setting, not a source-code failure.

## Installer to upload

```text
secure-browser-kiosk/dist/Genhire.exe
secure-browser-kiosk/dist/Genhire.exe.sha256
secure-browser-kiosk/dist/Genhire.exe.blockmap
```

- Application version: **1.3.0**; executable product version: **1.3.0.0**. This matches the configured backend kiosk release ID. It is a rebuild of that version, not a version bump.
- Installer: **104,566,497 bytes**.
- SHA-256: `c7b134cf90ac72ffbd2b5b33cb550858ba4d388785ebeeacffba0a0fe2269d79`.
- Authenticode status: **NotSigned**. No Windows signing certificate was configured; Windows may display publisher/SmartScreen prompts. Signing requires your own certificate and would change the installer checksum.
- Windows x64 only; no macOS installer was produced on this Windows machine.

In GCP Cloud Storage, open bucket **`genhire-downloads`** and replace the **`Genhire.exe`** object with this new installer. Upload its checksum beside it. Preserve the intended existing download access and use suitable cache metadata so candidates receive the new file. The configured frontend URL is already:

```text
https://storage.googleapis.com/genhire-downloads/Genhire.exe
```

After upload, download that public URL, compare its SHA-256 with the value above, install it over an existing copy, then test a real secure launch, Monaco coding/SQL, permissions and return-to-dashboard on a Windows device. Rebuilding or uploading does not update installed copies automatically.

## Before pushing to a deployment-trigger branch

1. **Cloud Run runtime configuration:** preserve the saved credentials and secret references. `REDIS_URL` must be injected from the intended Redis secret. Omit `GOOGLE_APPLICATION_CREDENTIALS` entirely when using the Cloud Run service account/ADC; do not set an empty path variable.
2. **Aiven CA:** ensure the service account can access the CA secret and its mounted file is exactly `/etc/secrets/aiven/ca.pem`. For a directory-style volume, mount `/etc/secrets/aiven` and set the secret file path to `ca.pem`. Set `AIVEN_POSTGRES_SSL_ROOT_CERT` to that complete file path on the process doing trusted validation.
3. **Backend object model:** the validated local `python-backend/models/proctoring/yolov8n.onnx` is Git-ignored. A GitHub-triggered build needs an explicit provisioning/copy step or a readable deployment mount with `PROCTORING_OBJECT_MODEL_PATH` pointing to it. A push alone will not include the local model. Follow [the model deployment instructions](docs/proctoring-model-setup.md). Its validated SHA-256 is `be7980683b0c4d7c86529e37953b363cfef67f8ec44c32ccfcc62736c7de7404`.
4. **Cloud Build trigger:** inspect the external deploy arguments for env/secret replacement flags or service YAML replacement. Image-only deployment normally retains runtime configuration; the external trigger was not inspected. Complete its Linux image build and startup/health check before routing production traffic.
5. **Vercel:** use either root configuration supported by this repo: `react-frontend` root with output `build`, or repository root with output `react-frontend/build`. Confirm Production environment values point to your Cloud Run API and `https://genhire.in`; private backend dotenv files are not pushed. Check Vercel's build and a direct nested-route reload after deploying.
6. **OA availability:** verify active workers and real profile-bound executor/device/media acceptance. All-true flags, passing builds and a healthy API are not substitutes for that evidence. Local developer preview is excluded from deployed web/kiosk/API artifacts.

Source is ready for review and a GitHub push to a non-production branch. For a branch that deploys automatically, resolve the configuration and artifact steps above first. These checks reduce deployment risk; they cannot guarantee a deployment without access to the actual cloud build and runtime configuration.

Latest compact UI, local formatters and installer verification: [OA UI refinement](OA_UI_REFINEMENT.md). The current installer includes these changes.

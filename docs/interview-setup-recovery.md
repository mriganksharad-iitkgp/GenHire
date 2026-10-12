# Interview setup, automatic face capture and kiosk 1.2.5

Updated 12 October 2026. For interruption accounting without automatic termination, front camera,
session restoration and real-device acceptance checklist, follow
[Interview monitoring policy](interview-monitoring-policy.md). Backend/frontend changes require deployment; the
rebuilt kiosk includes its own bundled UI and must be installed separately.

Release 1.2.5 adds the real-audio dotted voice sphere, voice-only conversation
and incremental captions. It removes automatic interruption termination, adds
typed interruption counts to the final monitoring score, reduces duplicate-face
warnings and retains phone recording parts across camera recovery. See
[voice and captions](interview-voice-and-captions.md) for provider usage and latency.

## Automatic capture and retake

Camera permission and laptop checks warm the locally bundled MediaPipe Tasks
Vision 0.10.32 detector, WASM runtime and BlazeFace model. One centered face at
a useful distance, held steady for **1.2 seconds**, triggers one local snapshot.
Movement, no face or multiple faces reset the hold. Candidates review the image,
choose **Retake photo**, or approve **Use photo and continue**. No photo reaches
the backend before approval. A failed save retains the chosen photo for retry.
**Take photo manually** is available immediately, including if detection fails.

Images are bounded to 640×480 JPEG. The existing server quality gate still
requires one face. Identity-card comparison remains background/advisory work;
a delayed result for an earlier photo cannot overwrite a retake. Required
camera, microphone, speaker and signed phone-readiness checks remain enforced.

## Delay and connection fixes

The supplied logs show **WORKER TIMEOUT**, a worker killed/restarted, repeated
instance starts and **Invalid session** socket errors. Gunicorn's "Perhaps out
of memory?" line is a generic SIGKILL diagnostic, not confirmation of a Cloud
Run memory-limit termination. A 45-second polling GET can be normal long polling.

Read-only inspection found revision **hrtech-00152-sw4** (image **cb02e70…**),
service maximum **3**, revision maximum **10**, no affinity, concurrency **80**
and request timeout **300 seconds**. Interview/socket state is process-local,
so different instances can receive requests belonging to the same interview.

The pending source changes use one Gunicorn **gthread** worker with **32 threads**
and explicit Flask-SocketIO threading/simple-websocket. Native vision/gRPC work
therefore does not starve a cooperative socket hub. Google TTS has a **4-second
RPC deadline**, with retries disabled. Setup prefetches question speech once;
speech availability does not gate setup. The existing first question is
deterministic, and its timer begins only after activation. OpenCV uses one
internal CPU thread; recharge-pack initialization runs once per database.
Desktop/mobile/application connections prefer WebSocket with polling fallback.
[Flask-SocketIO deployment guidance](https://flask-socketio.readthedocs.io/en/latest/deployment.html).

## Deploy release 1.2.5

1. Review, commit and push the fixes; run **genhire-main-deploy** on the new
   commit. Confirm logs show **gthread**, rather than eventlet. Keep the attached
   GCS identity, Redis Secret Manager mapping and HTTP `/health` startup probe.
   No dotenv credentials changed in this release.
2. Apply the connection settings in Cloud Shell during the rollout:

   ```bash
   gcloud run services update hrtech \
     --project=hr-tech-2026 \
     --region=europe-west1 \
     --max=1 \
     --max-instances=1 \
     --session-affinity \
     --concurrency=16 \
     --timeout=3600
   ```

   Both maximum settings address the inspected service/revision limits.
   Concurrency 16 leaves spare native thread capacity; it is a conservative
   starting configuration, not a production capacity benchmark. Instance limits
   can briefly be exceeded, and affinity is best-effort; neither recovers lost
   process state. Avoid deployments during active interviews. See Google's
   [instance limits](https://docs.cloud.google.com/run/docs/configuring/max-instances)
   and [WebSocket guidance](https://docs.cloud.google.com/run/docs/triggering/websockets).
3. Deploy the frontend to Vercel. npm install/start/build prepares the local WASM
   files automatically; serve the resulting `/assets/` files with proper MIME types.
4. Close the old kiosk and install **secure-browser-kiosk/dist/Genhire.exe**,
   version **1.2.5**. Packaging does not update existing installations or the
   hosted installer URL. Publish the tested installer and `.sha256` file through
   the existing installer release workflow when ready to distribute it.

Scale-to-zero still has a cold-start cost. Optionally set minimum instances to
**1** for planned interview windows if ongoing idle charges are acceptable.
This paid setting was not enabled here; local tests do not establish production
startup timing or hardware readiness.

## Verify release 1.2.5

Windows installer: **102,580,181 bytes**, installer version **1.2.5** (packaged application product version **1.2.5.0**).
SHA-256: `d146c966dfbc4c70fb977726dbfb2129f796e323d83ce1b5f390783269c14f91`.
Its 24 bundled UI/assets files match the build output byte-for-byte, including
the AudioWorklet, detector loader, WASM and face model. The checksum file sits beside it.

- Center one face, review the automatic snapshot, retake, then approve. Only the
  approved image should reach `register-face`; a failed save keeps it for retry.
- Move outside the guide or show two faces: automatic capture must pause.
- Single-/dual-camera jobs must retain their configured checks.
- Check Socket.IO uses WebSocket when available and remains connected beyond
  five minutes. Check new logs for quick photo saves and no worker restarts.
- Local checks passed: **161 backend tests**, **20 interview UI scenarios**,
  **19 frontend helper tests**, **7 kiosk security tests**, lint and both builds.
  Native Electron verified all five GPU voice states, actual audio amplitude,
  the AudioWorklet, cleanup and responsive layouts at 1400, 900 and about 390 pixels.
  Fixtures do not establish real-device camera accuracy or provider caption latency.

The updated local backend also started with the existing private configuration:
health returned **200** with MongoDB connected and Redis protection available,
Google-auth CORS preflight returned **200**, and an unauthenticated session read
returned **401**. The temporary port-5053 server used disabled background jobs
and was stopped after verification. Native WebSocket transport is covered by the suite.
The local threaded server closes WebSocket handlers cleanly without treating
their closing frames as another HTTP request. Focused backend tests cover
capture ownership/quality, stale retake scores, speech deadlines and plan setup.

## Earlier fixes in kiosk 1.2.2

Updated 11 October 2026. These changes preserve the required camera, microphone,
speaker, face-capture and signed phone-readiness checks before activation.

## Why setup was blocked

- The laptop preview and microphone could pass while Continue remained disabled
  because the separate speaker confirmation had not been completed.
- Setup now requests camera and microphone access automatically. When both pass,
  Continue plays a test sound and opens an explicit speaker confirmation dialog.
  Confirming it advances to face capture or the next required setup step.
- Some browsers suspend audio until a click. Setup now releases its busy state
  and provides Check microphone to resume audio rather than waiting indefinitely.
- The private backend environment files explicitly disabled the mobile companion
  with `MOBILE_RECORDING_ENABLED=false`. Dual-camera jobs correctly refused to
  start, producing the mobile-service-unavailable message.
- All four backend environment files now set `MOBILE_RECORDING_ENABLED=true`.
  The phone companion requests its camera and microphone only after signed pairing
  succeeds. Camera frames and a fresh heartbeat are still required for readiness.
- The create-job form now uses the same styled inputs as edit-job, including its
  date field. Per-field Generate draft buttons have been removed; the optional
  existing job-description import/AI assistance remains available.

## Apply the changes

1. Restart your local backend after changing `.env`: run `python app.py` from
   `python-backend` with its supported Python 3.11/3.12 environment. Restart the
   frontend if it is already running, using `npm start` in `react-frontend`.
2. In GCP, open Cloud Run → **hrtech** → Edit and deploy new revision → Variables
   and secrets. Set **MOBILE_RECORDING_ENABLED** to **true**, then deploy the
   revision. Editing the repository's `.env.production` does not update an already
   running Cloud Run revision. Retain the existing Redis Secret Manager reference
   `genhire-redis-url:latest`; production `REDIS_URL=""` in the file is intentional.
3. Deploy the updated frontend to Vercel so the hosted phone companion and
   create-job form receive these changes. Keep its API URL pointed at the same
   backend used by the kiosk session.
4. Close the old kiosk and install `secure-browser-kiosk/dist/Genhire.exe`, version
   **1.2.2**. This installer contains the updated shared interview UI and the
   native camera/microphone consent dialog. Existing installations do not download
   updated bundled UI automatically.
5. To distribute the release, replace the hosted installer at the configured
   download URL with the tested 1.2.2 installer. Local packaging does not upload it.
   Its checksum is provided beside it as `Genhire.exe.sha256`.

## Check the candidate journey

- Single camera: open an eligible interview, allow camera/microphone access in
  the popup, speak a short sentence, press Continue, confirm the test sound,
  capture your face and accept the interview instructions before starting.
- Permission denied: use Retry device checks after allowing access. The app
  does not repeatedly reopen the permission dialog without an explicit retry.
  If Windows blocks devices, enable desktop-app camera and microphone access
  under Settings → Privacy & security before retrying.
- Second camera: scan the signed QR code, allow devices on the phone, keep its
  page visible and position it beside the workspace. Continue becomes available
  after the server confirms the live phone camera, microphone and heartbeat.
- Disconnect: background the phone and verify a warning/count while laptop answers
  continue. Stop the laptop microphone, recover it and send the retained spoken answer.

## Local phone testing needs a reachable HTTPS site

A phone cannot reach the laptop's backend through `127.0.0.1` or `localhost`;
those names point to the phone itself. A QR code containing a localhost frontend
URL also opens the wrong device. An ordinary HTTP LAN address does not provide
the secure context required for phone camera access.

For a full phone test, use the deployed HTTPS frontend and backend together, or
configure a test HTTPS frontend and API endpoint reachable from both devices.
Both devices must connect to the same backend session. Do not mix a local kiosk
session with the production phone frontend unless both target that same backend.

Local startup was verified with the supported backend environment: `/health`
returned HTTP 200 with Mongo connected and Redis request protection available;
the interview-start CORS preflight returned HTTP 200 for `http://localhost:3000`.
GCS configuration and mobile enablement were confirmed at startup. Verification
disabled background jobs and startup wallet updates, and its temporary server
was stopped afterward. The sandbox's restricted DNS initially prevented Mongo
resolution; the network-enabled verification passed.

Automated checks use real React components with isolated media/socket/API fixtures;
they cannot verify physical laptop/phone hardware or the deployed configuration.
Follow the [interview acceptance matrix](interview-flow-audit.md#deployment-acceptance-matrix)
after installing and deploying the release.

# Interview setup fixes and kiosk 1.2.2

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
- Disconnect: stop a camera or background the phone, verify the interview pauses,
  then reconnect and resume the same session without losing an answer draft.

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

# Secure Browser (Kiosk) — Detailed Wiring

Folder: `secure-browser-kiosk/`. An **Electron** desktop app
(product name **Genhire**, appId `com.genhire.securebrowser`) that runs AI
interviews in a locked-down fullscreen kiosk so candidates can't switch apps,
open DevTools, or leave the interview window.

```
secure-browser-kiosk/
├── main.js       # Electron main process (~450 lines) — window, kiosk lockdown,
│                 #   deep links, speech token broker + TTS proxy, local HTTP server
├── preload.js    # contextBridge — the ONLY bridge between UI and main process
├── renderer.js   # The interview UI logic (~2,070 lines) — talks to the backend
├── index.html    # UI markup loaded into the window (~740 lines, CDN scripts)
└── package.json  # electron-builder config (NSIS installer / dmg, protocol registration)
```

**No Google service-account key ships with the app.** A `credentials.json`
still sits in the working tree but is explicitly excluded from the build
(`build.files: ["!credentials.json", ...]`) and nothing reads it — speech
auth is brokered by the backend at runtime (see below).

## Launch flow — from website click to running interview

1. **Install** — candidates install the built app (Windows NSIS installer or
   macOS dmg). The installer registers the app as the OS handler for the
   custom protocol **`secure-interview://`** (declared in `package.json` →
   `build.protocols`).
2. **Deep link** — on the website, `Profile.jsx` (real) or `Practice.jsx`
   (practice) navigates to
   `secure-interview://start?initData=<encoded payload>`. The OS launches
   the kiosk (or focuses the already-running instance — a single-instance
   lock is enforced; a second launch forwards its URL to the first).
3. **Payload handoff** — `main.js` parses `initData` from the URL and sends it
   to the renderer over IPC (`init-from-deeplink`). The payload carries the
   auth token, the backend API URL, and the application/practice context.
   The main process **also keeps** `{apiUrl, token}` for itself
   (`captureBackendSession`) — that is what authorizes its speech calls.
   Deep links are handled on both cold start (scanning `process.argv`) and
   while running (`second-instance` on Windows, `open-url` on macOS).
4. **Local HTTP server** — on startup the main process spins up a tiny HTTP
   server on `127.0.0.1` with a **random free port** and loads
   `http://localhost:<port>/index.html` into the window instead of a `file://`
   URL. This is required because Google's speech APIs reject `file://`
   origins. (`webSecurity: false` additionally allows the renderer to call
   the backend API cross-origin.)
5. **Interview** — the renderer drives the whole interview against the
   backend directly (see below). When the interview starts it asks the main
   process to enable kiosk mode; when it ends, kiosk mode is lifted and the
   candidate can be sent back to the website via their default browser
   (`open-external`).

## Kiosk lockdown (`enable-kiosk` / `disable-kiosk`)

When the interview begins the renderer sends `enable-kiosk`, and `main.js`:

- switches the window to `setKiosk(true)` + fullscreen + always-on-top,
  non-closable, non-minimizable, and force-focuses it;
- blocks in-window shortcuts via `before-input-event`
  (F12 / Ctrl+Shift+I DevTools, F5 / Ctrl+R reload, Ctrl+W / Ctrl+F4 /
  Alt+F4 close);
- registers global shortcuts to swallow `Alt+Tab`, `Ctrl+Tab`, `Escape`,
  `Super+D`, `Super+Tab` and (via `electron-localshortcut`) virtual-desktop
  switches;
- **emergency exit**: `Ctrl+Q` always works and shows a confirmation dialog
  warning that the interview session will end;
- on window **blur** (the user somehow switched away), immediately re-focuses
  and sends `app-switched` to the renderer, which logs a proctoring
  violation to the backend;
- prevents leaving fullscreen while kiosk is active.

`disable-kiosk` reverses all of it. Outside kiosk mode the app behaves as a
normal maximized window. The application menu is removed entirely, and
media (camera/mic) permission prompts are auto-granted while all other
permissions are denied.

Extra check: `get-display-info` returns the number of connected displays, so
the renderer can **flag** (not block) multi-monitor setups at interview start.

## Google Cloud Speech — brokered by the backend

The kiosk uses the **same** `/api/speech/*` endpoints as the website, with the
interview JWT from the deep link as its credential. Shipping a service-account
key inside a user-installed desktop app would have handed every candidate a
usable GCP key; this design removes that entirely.

- **TTS** (`synthesize-speech` IPC, invoke/response): `main.js` POSTs to
  `{apiUrl}/api/speech/synthesize` with `Authorization: Bearer <session jwt>`,
  trying voices in order `en-US-Journey-F` → `en-US-Neural2-C` →
  `en-US-Standard-C`, and returns the base64 MP3 for the renderer to play.
- **Streaming STT** (`start-stt-stream` / `audio-chunk` / `stop-stt-stream`):
  `getSpeechAccessToken()` POSTs to `{apiUrl}/api/speech/token` for a
  short-lived Google OAuth access token (cached until 2 minutes before expiry,
  re-minted per session). That token is wrapped in gRPC channel credentials to
  build a `@google-cloud/speech` client, which opens a live
  `streamingRecognize` stream (WEBM_OPUS, 48 kHz, `latest_long` model,
  automatic punctuation, interim results). Transcripts flow back over
  `stt-on-transcript (text, isFinal)`; errors over `stt-error`.
- Both paths throw *"No backend session — launch the app from the GenHire
  dashboard"* if the app was opened directly instead of via a deep link.

## Preload bridge (`preload.js`)

`contextIsolation: true` + `nodeIntegration: false` — the renderer only gets
this explicit API surface via `contextBridge` as `window.electronAPI`:

| Method | IPC channel | Purpose |
|---|---|---|
| `quitApp()` | `quit-app` | Exit the app |
| `enableKiosk()` / `disableKiosk()` | `enable-kiosk` / `disable-kiosk` | Toggle lockdown |
| `onInitDeepLink(cb)` | `init-from-deeplink` | Receive the session payload |
| `synthesizeSpeech(text)` | `synthesize-speech` | Google TTS |
| `startSTTStream()` / `sendAudioChunk(buf)` / `stopSTTStream()` | `start-stt-stream` / `audio-chunk` / `stop-stt-stream` | Google streaming STT |
| `onTranscript(cb)` / `onSTTError(cb)` | `stt-on-transcript` / `stt-error` | STT results |
| `openExternal(url)` | `open-external` | Return to the GenHire site in the default browser |
| `onAppSwitched(cb)` | `app-switched` | Kiosk blur detection → proctoring violation |
| `getDisplayInfo()` | `get-display-info` | Multi-monitor count |

## What the renderer talks to (backend integration)

`renderer.js` receives `{token, apiUrl, ...}` from the deep link and then
calls the **same Flask API the website uses**:

- `POST {apiUrl}/api/interviews/start` — begins the session (real mode).
- `POST .../api/interviews/<session_id>/register-face` — captures the
  candidate's face. The backend stores it, activates the session, and scores
  it against the account's identity card in the background; only a *missing*
  identity card (`identity_card_required`) stops the interview. `renderer.js`
  still contains branches for the retired `face_mismatch` /
  `face_mismatch_blocked` codes — the backend no longer returns them (see
  [../backend/interview-engine.md](../backend/interview-engine.md)).
- `POST .../api/interviews/<session_id>/answer` or
  `.../api/practice/<session_id>/answer` — submits each answer (the same
  renderer handles both real and practice modes; pacing — 30 s no-answer
  countdown, 10 s post-speech silence — matches the browser interview UI).
- `POST .../api/interviews/<session_id>/gaze-recorder-results` — gaze data.
- `POST .../api/interviews/<session_id>/end` or `.../api/practice/<session_id>/end`.
- **Socket.IO** to `apiUrl`: on connect emits `start_proctoring`
  (joins the session room) and `control_mobile_recording {action: "start"}`;
  emits `proctoring_violation` events **with acknowledgements and a retry
  queue** — violations that fail to send (mid-reconnect) are retried on the
  next connect, so none are lost.

## Building & running

```bash
cd secure-browser-kiosk
npm install
npm start            # dev — Electron with local files
npm run dist         # Windows x64 NSIS installer (Genhire.exe)
npm run dist:mac     # macOS universal dmg/zip
```

No credentials setup is required at build time. The kiosk gets everything it
needs (backend URL + JWT) from the `secure-interview://` deep link at runtime,
so a build is reproducible from a clean checkout.

`npm start` launches Electron directly; to exercise the full website→kiosk
handoff you need the `secure-interview://` protocol registered with the OS,
which only happens when you install a built package.

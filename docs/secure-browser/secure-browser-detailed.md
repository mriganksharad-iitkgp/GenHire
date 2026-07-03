# Secure Browser (Kiosk) — Detailed Wiring

Folder: `secure-browser-kiosk/`. An **Electron** desktop app
(product name **Genhire**, appId `com.genhire.securebrowser`) that runs AI
interviews in a locked-down fullscreen kiosk so candidates can't switch apps,
open DevTools, or leave the interview window.

```
secure-browser-kiosk/
├── main.js       # Electron main process (405 lines) — window, kiosk lockdown,
│                 #   deep links, Google Cloud TTS/STT, local HTTP server
├── preload.js    # contextBridge — the ONLY bridge between UI and main process
├── renderer.js   # The interview UI logic (~1,600 lines) — talks to the backend
├── index.html    # UI markup loaded into the window
├── credentials.json  # Google Cloud service-account key (packaged as extraResource)
└── package.json  # electron-builder config (NSIS installer / dmg, protocol registration)
```

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

## Google Cloud Speech — local to the kiosk

Unlike the website (which uses the backend's `/api/speech/*`), the kiosk has
its **own** Google Cloud clients, initialized from `credentials.json`
(bundled by electron-builder as an extraResource; found at
`process.resourcesPath` when packaged, next to `main.js` in dev):

- **TTS** (`synthesize-speech` IPC, invoke/response): tries voices in order
  `en-US-Journey-F` → `en-US-Neural2-C` → `en-US-Standard-C`, returns MP3
  audio as base64 for the renderer to play.
- **Streaming STT** (`start-stt-stream` / `audio-chunk` / `stop-stt-stream`):
  a live `streamingRecognize` stream (WEBM_OPUS, 48 kHz, `latest_long` model,
  automatic punctuation, interim results). Transcripts flow back over
  `stt-on-transcript (text, isFinal)`; errors over `stt-error`.

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
- `POST .../api/interviews/<session_id>/answer` or
  `.../api/practice/<session_id>/answer` — submits each answer (the same
  renderer handles both real and practice modes).
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

`credentials.json` (Google service account with Speech APIs enabled) must be
present at build time — it ships inside the installer as an extraResource.

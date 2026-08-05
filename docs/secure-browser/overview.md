# Secure Browser — Simple Overview

**What it is:** a desktop app (folder `secure-browser-kiosk/`, built with
**Electron**) called **Genhire** that candidates install on their computer.
All real and practice AI interviews run inside it — not in a normal browser
tab.

**Why it exists:** a browser tab can't stop a candidate from googling
answers, switching to notes, or opening ChatGPT in another window. The
secure browser can: during the interview it locks the machine into a
fullscreen kiosk.

## What it does

- **Launches from the website** — clicking "Start Interview" on the GenHire
  site opens a `secure-interview://` link; the OS hands it to this app along
  with the session data (login token, backend address, which
  application/practice session).
- **Records who's sitting there** — before a real interview starts the
  candidate's face is captured and sent to the backend, which scores it
  against the identity card on their profile in the background. The score and
  photo go to the recruiter; nobody is blocked on a low score, but an
  interview cannot start at all without a card on file.
- **Locks down during the interview** — fullscreen kiosk, always on top,
  can't be closed or minimized; Alt+Tab, Escape, F12/DevTools, reload, and
  close shortcuts are all blocked. If focus is somehow lost, the window
  snaps back and the switch is reported as a proctoring violation.
  `Ctrl+Q` remains as a confirmed emergency exit. Multiple monitors are
  detected and flagged.
- **Talks like a human** — questions are spoken aloud with Google Cloud
  text-to-speech, and the candidate answers by voice, transcribed live with
  Google streaming speech-to-text. **No Google key ships with the app**: TTS
  is proxied through the backend (`/api/speech/synthesize`) and streaming STT
  uses a short-lived access token the backend mints
  (`/api/speech/token`), both authorized by the interview JWT from the deep
  link.
- **Runs the interview against the backend** — the same Flask API the
  website uses: start session, submit answers, end session. Unlike the
  website (which streams webcam frames to the backend for server-side
  analysis), the kiosk detects gaze/head-turn/multi-face and phone-in-frame
  locally (MediaPipe + a small object-detection model) and only relays the
  resulting violations to the backend over Socket.IO.
- **Returns you to the site** — when the interview ends, lockdown lifts and
  the app opens the GenHire dashboard in the default browser.

## Shape of the code

```
secure-browser-kiosk/
├── main.js       # Electron main process: window, kiosk lockdown, deep links,
│                 #   speech token broker + TTS proxy, tiny localhost web server
├── preload.js    # the safe bridge (window.electronAPI) between UI and system
├── renderer.js   # the interview UI logic (questions, voice, proctoring)
└── index.html    # the UI itself
```

There is a `credentials.json` in the working tree, but it is **excluded from
the build** (`"!credentials.json"` in `package.json` → `build.files`) and no
longer read by the app — it is a leftover from the pre-token-broker design.

One quirk worth knowing: the app serves its own files from
`http://localhost:<random port>` instead of opening them as `file://`,
because Google's speech services refuse `file://` pages.

## How to run / build it

```bash
cd secure-browser-kiosk
npm install
npm start          # development
npm run dist       # Windows x64 NSIS installer (Genhire.exe)
npm run dist:mac   # macOS universal dmg/zip
```

No credentials setup is needed — everything the kiosk needs arrives with the
deep link at runtime.

**Want the details?** → [secure-browser-detailed.md](secure-browser-detailed.md)

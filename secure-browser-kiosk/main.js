const { app, BrowserWindow, globalShortcut, Menu, ipcMain, shell, dialog, screen } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');

// Google Cloud Speech access — NO bundled service-account key.
// TTS goes through the GenHire backend proxy (/api/speech/synthesize) and
// streaming STT authenticates with a short-lived access token minted by the
// backend (/api/speech/token), both using the interview session's JWT that
// arrives via the secure-interview:// deep link.
const speech = require('@google-cloud/speech');
const grpc = require('@grpc/grpc-js');
const { OAuth2Client } = require('google-auth-library');

let recognizeStream = null;

// Captured from the deep link's initData (same payload the renderer parses).
let backendSession = { apiUrl: null, token: null };
// Cached short-lived Google access token for streaming STT.
let speechAccessToken = { token: null, expiresAt: 0 };

function captureBackendSession(initData) {
    try {
        const payload = JSON.parse(Buffer.from(initData, 'base64').toString('utf-8'));
        if (payload && payload.apiUrl && payload.token) {
            backendSession = { apiUrl: String(payload.apiUrl).replace(/\/$/, ''), token: payload.token };
            speechAccessToken = { token: null, expiresAt: 0 }; // new session, new token
        }
    } catch (e) {
        console.warn('Could not parse deep-link session payload:', e.message);
    }
}

async function getSpeechAccessToken() {
    if (!backendSession.apiUrl || !backendSession.token) {
        throw new Error('No backend session — launch the app from the GenHire dashboard.');
    }
    // Reuse the cached token until 2 minutes before expiry.
    if (speechAccessToken.token && Date.now() < speechAccessToken.expiresAt - 120000) {
        return speechAccessToken.token;
    }
    const response = await fetch(`${backendSession.apiUrl}/api/speech/token`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${backendSession.token}` },
    });
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || `Speech token request failed (${response.status})`);
    }
    const data = await response.json();
    const expiresAt = data.expires_at ? Date.parse(data.expires_at) : Date.now() + 45 * 60 * 1000;
    speechAccessToken = { token: data.access_token, expiresAt };
    return speechAccessToken.token;
}

async function createSttClient() {
    const accessToken = await getSpeechAccessToken();
    const authClient = new OAuth2Client();
    authClient.setCredentials({ access_token: accessToken });
    const sslCreds = grpc.credentials.combineChannelCredentials(
        grpc.credentials.createSsl(),
        grpc.credentials.createFromGoogleCredential(authClient),
    );
    return new speech.SpeechClient({ sslCreds });
}

let KIOSK_HTTP_PORT = 0; // Set to 0 to auto-assign a free port to prevent EADDRINUSE

// Disable Hardware Acceleration to prevent GPU crashes with WebGL/ML Models in Kiosk mode
// app.disableHardwareAcceleration();

// Enable speech recognition in Electron (needed for Google's speech servers)
app.commandLine.appendSwitch('enable-speech-dispatcher');
app.commandLine.appendSwitch('enable-features', 'SpeechRecognition');

let mainWindow;
let isKioskActive = false;

// ----------------------------------------------------
// DEEP LINK & SINGLE INSTANCE LOCK HANDLING
// ----------------------------------------------------
if (process.defaultApp) {
    if (process.argv.length >= 2) {
        app.setAsDefaultProtocolClient('secure-interview', process.execPath, [path.resolve(process.argv[1])]);
    }
} else {
    app.setAsDefaultProtocolClient('secure-interview');
}

function handleDeepLink(url) {
    try {
        const urlObj = new URL(url);
        const initData = urlObj.searchParams.get('initData');
        if (initData) {
            captureBackendSession(initData);
        }
        if (initData && mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('init-from-deeplink', initData);
        }
    } catch (e) {
        console.error("Failed to parse deep link URL:", url, e);
    }
}

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
    app.quit();
} else {
    app.on('second-instance', (event, commandLine, workingDirectory) => {
        if (mainWindow) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            mainWindow.focus();
        }
        const url = commandLine.find(arg => arg.startsWith('secure-interview://'));
        if (url) {
            handleDeepLink(url);
        }
    });
}

// macOS deep link handling
app.on('open-url', (event, url) => {
    event.preventDefault();
    if (app.isReady()) {
        handleDeepLink(url);
    } else {
        app.once('ready', () => handleDeepLink(url));
    }
});
// ----------------------------------------------------

// Listen for the quit signal from the frontend renderer
ipcMain.on('quit-app', () => {
    app.quit();
});

// Open URL in default browser (for returning to GenHire dashboard)
ipcMain.on('open-external', (event, url) => {
    if (url && typeof url === 'string') {
        shell.openExternal(url).catch(err => {
            console.error('Failed to open external URL:', err);
        });
    }
});

// Multi-monitor detection — used at interview start to flag (not block) a
// second connected display, a common way to keep notes/answers off-screen
// from the interview camera.
ipcMain.handle('get-display-info', () => {
    const displays = screen.getAllDisplays();
    return { count: displays.length };
});

// ==========================================
// GOOGLE CLOUD TEXT-TO-SPEECH (TTS) HANDLERS
// ==========================================
ipcMain.handle('synthesize-speech', async (event, text) => {
    if (!backendSession.apiUrl || !backendSession.token) {
        throw new Error('No backend session — launch the app from the GenHire dashboard.');
    }

    // Voice fallback chain: Journey (most natural) -> Neural2 -> Standard
    const voices = ['en-US-Journey-F', 'en-US-Neural2-C', 'en-US-Standard-C'];

    for (const voiceName of voices) {
        try {
            const response = await fetch(`${backendSession.apiUrl}/api/speech/synthesize`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${backendSession.token}`,
                },
                body: JSON.stringify({ text, voice_name: voiceName, language_code: 'en-US' }),
            });
            if (!response.ok) {
                const body = await response.json().catch(() => ({}));
                throw new Error(body.error || `HTTP ${response.status}`);
            }
            const data = await response.json();
            if (data.audio_base64) return data.audio_base64;
            throw new Error('Empty audio response');
        } catch (err) {
            console.warn(`TTS voice ${voiceName} failed: ${err.message}`);
        }
    }
    throw new Error('All TTS voices failed — check the backend speech service.');
});

// ==========================================
// GOOGLE CLOUD SPEECH-TO-TEXT (STT) HANDLERS
// ==========================================
ipcMain.on('start-stt-stream', async (event) => {
    let sttClient;
    try {
        sttClient = await createSttClient();
    } catch (err) {
        console.error('STT client init failed:', err.message);
        event.sender.send('stt-error', err.message);
        return;
    }

    // Cleanup previous stream if any
    if (recognizeStream) {
        recognizeStream.end();
        recognizeStream = null;
    }

    const request = {
        config: {
            encoding: 'WEBM_OPUS',
            sampleRateHertz: 48000,
            languageCode: 'en-US',
            enableAutomaticPunctuation: true,
            model: 'latest_long'
        },
        interimResults: true,
    };

    recognizeStream = sttClient
        .streamingRecognize(request)
        .on('error', (err) => {
            console.error('STT Stream Error:', err);
            event.sender.send('stt-error', err.message);
        })
        .on('data', (data) => {
            if (data.results[0] && data.results[0].alternatives[0]) {
                const text = data.results[0].alternatives[0].transcript;
                const isFinal = data.results[0].isFinal;
                event.sender.send('stt-on-transcript', text, isFinal);
            }
        });

    console.log("🎙️ Google STT recognizer stream opened");
});

ipcMain.on('audio-chunk', (event, buffer) => {
    if (recognizeStream && recognizeStream.writable) {
        recognizeStream.write(buffer);
    }
});

ipcMain.on('stop-stt-stream', (event) => {
    if (recognizeStream) {
        recognizeStream.end();
        recognizeStream = null;
        console.log("🛑 Google STT recognizer stream closed");
    }
});

// Enable kiosk mode (called when interview starts)
ipcMain.on('enable-kiosk', () => {
    if (!mainWindow || mainWindow.isDestroyed() || isKioskActive) return;
    isKioskActive = true;

    mainWindow.setKiosk(true);
    mainWindow.setFullScreen(true);
    mainWindow.setAlwaysOnTop(true);
    mainWindow.setClosable(false);
    mainWindow.setMinimizable(false);
    // Force window to foreground — prevents tab-switch right after calibration dot 5
    mainWindow.focus();

    // Block keyboard shortcuts
    mainWindow.webContents.on('before-input-event', blockInputHandler);

    // Register global shortcuts
    try {
        globalShortcut.register('CommandOrControl+Tab', () => { });
        globalShortcut.register('Alt+Tab', () => { });
        globalShortcut.register('Escape', () => { });
        globalShortcut.register('Super+D', () => { });
        globalShortcut.register('Super+Tab', () => { });

        // Emergency exit: Ctrl+Q shows a confirmation dialog (works even during kiosk)
        globalShortcut.register('Control+Q', () => {
            if (!mainWindow || mainWindow.isDestroyed()) return;
            const choice = dialog.showMessageBoxSync(mainWindow, {
                type: 'warning',
                title: 'Exit GenHire',
                message: 'Exit GenHire Secure Browser?',
                detail: 'This will end your current interview session.',
                buttons: ['Cancel', 'Exit GenHire'],
                defaultId: 0,
                cancelId: 0,
            });
            if (choice === 1) {
                isKioskActive = false;
                mainWindow.setKiosk(false);
                mainWindow.setAlwaysOnTop(false);
                mainWindow.setClosable(true);
                globalShortcut.unregisterAll();
                app.quit();
            }
        });

        const localShortcut = require('electron-localshortcut');
        localShortcut.register(mainWindow, 'Super+Tab', () => { });
        localShortcut.register(mainWindow, 'Super+Ctrl+Right', () => { });
        localShortcut.register(mainWindow, 'Super+Ctrl+Left', () => { });
    } catch (e) {
        console.log('Some shortcuts could not be registered:', e.message);
    }

    console.log('🔒 Kiosk mode ENABLED');
});

// Disable kiosk mode (called when interview ends)
ipcMain.on('disable-kiosk', () => {
    if (!mainWindow || mainWindow.isDestroyed() || !isKioskActive) return;
    isKioskActive = false;

    mainWindow.setKiosk(false);
    mainWindow.setFullScreen(false);
    mainWindow.setAlwaysOnTop(false);
    mainWindow.setClosable(true);
    mainWindow.setMinimizable(true);

    // Unblock keyboard shortcuts
    mainWindow.webContents.removeListener('before-input-event', blockInputHandler);

    // Unregister all global shortcuts
    globalShortcut.unregisterAll();
    try {
        const localShortcut = require('electron-localshortcut');
        localShortcut.unregisterAll(mainWindow);
    } catch (e) { }

    console.log('🔓 Kiosk mode DISABLED');
});

function blockInputHandler(event, input) {
    // Block dangerous shortcuts during kiosk
    if (input.key.toLowerCase() === 'f12' || (input.control && input.shift && input.key.toLowerCase() === 'i')) event.preventDefault();
    if (input.key.toLowerCase() === 'f5' || (input.control && input.key.toLowerCase() === 'r')) event.preventDefault();
    if (input.control && (input.key.toLowerCase() === 'w' || input.key.toLowerCase() === 'f4')) event.preventDefault();
    if (input.alt && input.key.toLowerCase() === 'f4') event.preventDefault();
}

function createWindow() {
    // Start as a normal maximized window (NOT kiosk)
    mainWindow = new BrowserWindow({
        title: 'Genhire',
        width: 1280,
        height: 800,
        icon: path.join(__dirname, 'build', 'genhire_logo.ico'),
        fullscreen: false,
        kiosk: false,
        alwaysOnTop: false,
        autoHideMenuBar: true,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
            webSecurity: false // Allow cross-origin requests from file:// to localhost API
        }
    });

    // Maximize on start for a nice look
    mainWindow.maximize();

    // Auto-grant media permissions
    mainWindow.webContents.session.setPermissionCheckHandler((webContents, permission, requestingOrigin, details) => {
        if (permission === 'media') return true;
        return false;
    });

    mainWindow.webContents.session.setPermissionRequestHandler((webContents, permission, callback, details) => {
        if (permission === 'media') callback(true);
        else callback(false);
    });

    mainWindow.loadURL(`http://localhost:${KIOSK_HTTP_PORT}/index.html`);

    // Removed DevTools for production

    // Remove the default menu entirely
    Menu.setApplicationMenu(null);

    // Aggressive re-focusing + proctoring notification ONLY when kiosk is active
    mainWindow.on('blur', () => {
        if (isKioskActive && mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.focus();
            // Notify renderer so it can log the proctoring violation
            mainWindow.webContents.send('app-switched', {});
        }
    });

    // Prevent leaving fullscreen ONLY when kiosk is active
    mainWindow.on('leave-full-screen', (event) => {
        if (isKioskActive && mainWindow && !mainWindow.isDestroyed()) {
            event.preventDefault();
            mainWindow.setFullScreen(true);
        }
    });
}

app.whenReady().then(() => {
    // Start a local HTTP server to serve kiosk files
    // This is REQUIRED because Google's Speech Recognition API 
    // rejects requests from file:// origins but accepts http://localhost
    const mimeTypes = {
        '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
        '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.wasm': 'application/wasm',
        '.mjs': 'application/javascript'
    };

    const server = http.createServer((req, res) => {
        let filePath = path.join(__dirname, req.url === '/' ? 'index.html' : req.url);
        // Remove query strings if any
        if (filePath.includes('?')) filePath = filePath.split('?')[0];

        const ext = path.extname(filePath).toLowerCase();
        const contentType = mimeTypes[ext] || 'application/octet-stream';

        fs.readFile(filePath, (err, data) => {
            if (err) {
                res.writeHead(404);
                res.end('Not Found');
                return;
            }
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(data);
        });
    });

    server.listen(0, '127.0.0.1', () => {
        KIOSK_HTTP_PORT = server.address().port;
        console.log(`✅ Kiosk HTTP server running on http://localhost:${KIOSK_HTTP_PORT}`);
        createWindow();

        // Handle deep link passed as arg on initial launch
        mainWindow.webContents.once('did-finish-load', () => {
            const url = process.argv.find(arg => arg.startsWith('secure-interview://'));
            if (url) {
                handleDeepLink(url);
            }
        });
    });

    app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', function () {
    if (process.platform !== 'darwin') app.quit();
});

// Cleanup global shortcuts when quitting
app.on('will-quit', () => {
    globalShortcut.unregisterAll();
});

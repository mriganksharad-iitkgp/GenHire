const { app, BrowserWindow, globalShortcut, Menu, ipcMain } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');

// Add Google Cloud Speech APIs
const textToSpeech = require('@google-cloud/text-to-speech');
const speech = require('@google-cloud/speech');

// Initialize Google Cloud Clients using local credentials.json
const credentialsPath = path.join(__dirname, 'credentials.json');
let ttsClient = null;
let sttClient = null;

try {
    if (fs.existsSync(credentialsPath)) {
        ttsClient = new textToSpeech.TextToSpeechClient({ keyFilename: credentialsPath });
        sttClient = new speech.SpeechClient({ keyFilename: credentialsPath });
        console.log("✅ Google Cloud API clients initialized");
    } else {
        console.warn("⚠️ credentials.json not found! Google Cloud Speech APIs will fail.");
    }
} catch (err) {
    console.error("❌ Failed to initialize Google Cloud APIs:", err.message);
}

let recognizeStream = null;

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

// ==========================================
// GOOGLE CLOUD TEXT-TO-SPEECH (TTS) HANDLERS
// ==========================================
ipcMain.handle('synthesize-speech', async (event, text) => {
    if (!ttsClient) throw new Error("Google Cloud TTS client not initialized.");

    const request = {
        input: { text: text },
        voice: { languageCode: 'en-US', name: 'en-US-Journey-F' }, // Using a more natural voice, fallback to standard if not available in project
        audioConfig: { audioEncoding: 'MP3' },
    };

    try {
        const [response] = await ttsClient.synthesizeSpeech(request);
        // We return the binary audio content encoded as base64 so renderer can play it via Data URI
        return response.audioContent.toString('base64');
    } catch (err) {
        console.error("TTS Error:", err);
        throw err;
    }
});

// ==========================================
// GOOGLE CLOUD SPEECH-TO-TEXT (STT) HANDLERS
// ==========================================
ipcMain.on('start-stt-stream', (event) => {
    if (!sttClient) {
        console.error("STT Client not initialized.");
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

    // Block keyboard shortcuts
    mainWindow.webContents.on('before-input-event', blockInputHandler);

    // Register global shortcuts
    try {
        globalShortcut.register('CommandOrControl+Tab', () => { });
        globalShortcut.register('Alt+Tab', () => { });
        globalShortcut.register('Escape', () => { });
        globalShortcut.register('Super+D', () => { });

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

    // Aggressive re-focusing ONLY when kiosk is active
    mainWindow.on('blur', () => {
        if (isKioskActive && mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.focus();
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

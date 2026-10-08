const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    quitApp: () => ipcRenderer.send('quit-app'),
    enableKiosk: () => ipcRenderer.send('enable-kiosk'),
    disableKiosk: () => ipcRenderer.send('disable-kiosk'),
    
    // Deep Link Intialization
    onInitDeepLink: (callback) => {
        ipcRenderer.removeAllListeners('init-from-deeplink');
        ipcRenderer.on('init-from-deeplink', callback);
    },
    rendererReady: () => ipcRenderer.invoke('renderer-ready'),
    
    // Backend speech APIs: Google Standard TTS and Groq STT
    synthesizeSpeech: (text) => ipcRenderer.invoke('synthesize-speech', text),
    transcribeAudio: (audioBase64, sessionId) => ipcRenderer.invoke('transcribe-audio', { audioBase64, sessionId }),
    onTranscript: (callback) => {
        ipcRenderer.removeAllListeners('stt-on-transcript');
        ipcRenderer.on('stt-on-transcript', callback);
    },
    onSTTError: (callback) => {
        ipcRenderer.removeAllListeners('stt-error');
        ipcRenderer.on('stt-error', callback);
    },

    // Open URL in default browser
    openExternal: (url) => ipcRenderer.send('open-external', url),

    // App-switch detection (fired by main process when window loses focus during kiosk)
    onAppSwitched: (callback) => {
        ipcRenderer.removeAllListeners('app-switched');
        ipcRenderer.on('app-switched', callback);
    },

    // Multi-monitor detection — returns { count: <number of connected displays> }
    getDisplayInfo: () => ipcRenderer.invoke('get-display-info'),
});

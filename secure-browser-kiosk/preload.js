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
    
    // Google Cloud Speech Additions
    synthesizeSpeech: (text) => ipcRenderer.invoke('synthesize-speech', text),
    startSTTStream: () => ipcRenderer.send('start-stt-stream'),
    sendAudioChunk: (buffer) => ipcRenderer.send('audio-chunk', buffer),
    stopSTTStream: () => ipcRenderer.send('stop-stt-stream'),
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
});

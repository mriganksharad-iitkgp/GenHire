const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    quitApp: () => ipcRenderer.send('quit-app'),
    enableKiosk: () => ipcRenderer.send('enable-kiosk'),
    disableKiosk: () => ipcRenderer.send('disable-kiosk'),
    
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
    }
});

// Hidden Electron runtime test of the real model/WASM under the kiosk CSP.
// No camera, account, API endpoint or production session is used.
const { app, BrowserWindow } = require('electron');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const { resolvePublicFile } = require('../runtime-security');
const root = path.resolve(__dirname, '..');
app.setPath('userData', path.join(root, '.face-smoke-user-data'));
let server, window;
app.whenReady().then(async () => {
  try {
    const main = await fs.readFile(path.join(root, 'main.js'), 'utf8');
    const csp = main.match(/'Content-Security-Policy': "([^"]+)"/)[1];
    server = http.createServer(async (request, response) => {
      try {
        response.setHeader('Content-Security-Policy', csp);
        if (request.url === '/') { response.setHeader('Content-Type', 'text/html'); response.end('<!doctype html><html><body>Local face runtime check</body></html>'); return; }
        const target = request.url === '/assets/vision-runtime.js'
          ? path.join(root, '../react-frontend/node_modules/@mediapipe/tasks-vision/vision_bundle.mjs')
          : resolvePublicFile(root, request.url);
        if (!target) { response.writeHead(404); response.end(); return; }
        response.setHeader('Content-Type', target.endsWith('.wasm') ? 'application/wasm' : /\.m?js$/.test(target) ? 'application/javascript' : 'application/octet-stream');
        response.end(await fs.readFile(target));
      } catch { response.writeHead(404); response.end(); }
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    window = new BrowserWindow({ show: false, webPreferences: { nodeIntegration: false, contextIsolation: true } });
    await window.loadURL(`http://127.0.0.1:${server.address().port}/`);
    const result = await window.webContents.executeJavaScript(`(async () => {
      const {FaceDetector,FilesetResolver} = await import('/assets/vision-runtime.js');
      const started = performance.now();
      const runtime = await FilesetResolver.forVisionTasks(location.origin + '/assets');
      const detector = await FaceDetector.createFromOptions(runtime, {baseOptions: {modelAssetPath: location.origin + '/assets/blaze_face_short_range.tflite',delegate:'CPU'},runningMode:'VIDEO',minDetectionConfidence:0.65});
      const canvas = document.createElement('canvas'); canvas.width=640; canvas.height=480;
      canvas.getContext('2d').fillRect(0,0,640,480);
      const detections = detector.detectForVideo(canvas, performance.now()).detections;
      detector.close(); return {faces: detections.length, initializationMs: Math.round(performance.now()-started)};
    })()`);
    if (result.faces !== 0) throw new Error('Blank frame must not be captured as a face');
    console.log('PASS real bundled face detector + WASM + kiosk CSP:', JSON.stringify(result));
    window.destroy(); server.close(); app.exit(0);
  } catch (error) {
    console.error('FAIL face runtime:', error.message);
    window?.destroy(); server?.close(); app.exit(1);
  }
});
setTimeout(() => { console.error('FAIL face runtime: deadline exceeded'); app.exit(1); }, 20000).unref();

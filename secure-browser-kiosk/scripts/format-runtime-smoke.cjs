// Real bundled formatter engines under the secure browser's production CSP.
const { app, BrowserWindow } = require('electron');
const fs = require('node:fs/promises'), path = require('node:path'), http = require('node:http');
const { resolvePublicFile } = require('../runtime-security');
const root = path.resolve(__dirname, '..');
app.setPath('userData', path.join(root, '..', '.tmp', 'kiosk-format-smoke'));
let server, window;
app.whenReady().then(async () => {
  try {
    const main = await fs.readFile(path.join(root, 'main.js'), 'utf8');
    const csp = main.match(/'Content-Security-Policy': "([^"]+)"/)[1];
    const files = await fs.readdir(path.join(root, 'web-app/assets'));
    const formatter = files.find(name => /^codeFormatting-.*\.js$/.test(name));
    if (!formatter) throw new Error('Build the kiosk UI before running the formatter smoke.');
    server = http.createServer(async (request, response) => {
      try {
        response.setHeader('Content-Security-Policy', csp);
        if (request.url === '/') { response.setHeader('Content-Type', 'text/html'); response.end('<!doctype html><title>Local formatter check</title><div id="root"></div>'); return; }
        const file = resolvePublicFile(root, request.url);
        if (!file) { response.writeHead(404); response.end(); return; }
        response.setHeader('Content-Type', file.endsWith('.wasm') ? 'application/wasm' : 'application/javascript');
        response.end(await fs.readFile(file));
      } catch { response.writeHead(404); response.end(); }
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    window = new BrowserWindow({ show: false, webPreferences: { nodeIntegration: false, contextIsolation: true } });
    await window.loadURL(`http://127.0.0.1:${server.address().port}/`);
    const result = await window.webContents.executeJavaScript(`(async () => {
      const module = await import('/assets/${formatter}');
      const format = module.formatCode || Object.values(module).find(value => typeof value === 'function');
      const sources = { cpp: 'int main(){const char* s="a;b{}";return 0;}', c: 'int main(){return 0;}', java: 'class Main{public static void main(String[] a){System.out.println(1);}}', javascript: 'function add(a,b){return a+b;}', python: 'def add(a,b): return a+b', sql: "select 'a;b{}' as literal from t where n>0" };
      const passed = [];
      for (const [language, source] of Object.entries(sources)) {
        const formatted = await format(source, language);
        if (formatted.split('\\n').length < 3) throw new Error(language + ' remains minified');
        if (source.includes('a;b{}') && !formatted.includes('a;b{}')) throw new Error('String literal modified');
        passed.push(language);
      }
      let invalidRejected = false;
      try { await format('def invalid(:', 'python'); } catch { invalidRejected = true; }
      if (!invalidRejected) throw new Error('Invalid Python was not rejected');
      return {languages: passed, invalidSyntaxRejected: invalidRejected, localAssetsOnly: true};
    })()`);
    console.log('PASS bundled code formatters + WASM + kiosk CSP:', JSON.stringify(result));
    window.destroy(); server.close(); app.exit(0);
  } catch (error) {
    console.error('FAIL formatter runtime:', error.message);
    window?.destroy(); server?.close(); app.exit(1);
  }
});
setTimeout(() => { console.error('FAIL formatter runtime deadline'); app.exit(1); }, 30000).unref();

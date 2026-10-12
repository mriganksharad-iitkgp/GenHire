const { app, BrowserWindow } = require('electron');
const fs = require('node:fs/promises'), http = require('node:http'), path = require('node:path');
const root = path.resolve(__dirname, '..'), files = path.join(root, '.voice-runtime-smoke');
app.setPath('userData', path.join(root, '.voice-smoke-user-data'));
let server, window;
app.whenReady().then(async () => {
  try {
    const main = await fs.readFile(path.join(root, 'main.js'), 'utf8');
    const csp = main.match(/'Content-Security-Policy': "([^"]+)"/)[1];
    server = http.createServer(async (request, response) => {
      const name = request.url === '/' ? 'index.html' : request.url === '/interview' ? 'interview.html' : request.url.replace('/assets/', '');
      if (!['index.html', 'voice.js', 'voice.css', 'theme.css', 'interview.html', 'interview.js', 'interview.css', 'interview-pcm-worklet.js'].includes(name)) { response.writeHead(404);response.end();return; }
      response.setHeader('Content-Security-Policy', csp);
      response.setHeader('Content-Type', name.endsWith('.js') ? 'application/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html');
      response.end(await fs.readFile(path.join(files, name)));
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    window = new BrowserWindow({ show: false, width: 1400, height: 660, webPreferences: { nodeIntegration: false, contextIsolation: true, offscreen: true, backgroundThrottling: false, autoplayPolicy: 'no-user-gesture-required' } });
    window.webContents.setAudioMuted(true);
    await window.loadURL(`http://127.0.0.1:${server.address().port}/`);
    let result;
    for (let i=0;i<40;i++) { result = await window.webContents.executeJavaScript('window.voiceResults'); if(result)break; await new Promise(resolve=>setTimeout(resolve,250)); }
    if (!result || result.canvases !== 5 || result.quiet > .01 || result.active < .2) throw new Error('WebGL or actual audio amplitude verification failed: ' + JSON.stringify(result));
    await fs.writeFile(path.join(files,'voice-states.png'), (await window.webContents.capturePage()).toPNG());
    const cleanup = await window.webContents.executeJavaScript('window.cleanupVoice()');
    if(cleanup.canvases || cleanup.context !== 'closed') throw new Error('Voice renderer/audio cleanup failed');
    console.log('PASS real WebGL + actual Web Audio signal + kiosk CSP:', JSON.stringify({ ...result, cleanup }));
    await window.setSize(1400, 960);
    await window.loadURL(`http://127.0.0.1:${server.address().port}/interview`);
    const press = label => window.webContents.executeJavaScript(`(()=>{const button=[...document.querySelectorAll('button')].find(node=>node.textContent.trim()===${JSON.stringify(label)});if(!button||button.disabled)return false;button.click();return true;})()`);
    for(let i=0;i<30;i++){if(await press('Continue'))break;await new Promise(resolve=>setTimeout(resolve,200));}
    await new Promise(resolve=>setTimeout(resolve,250));
    if(!await press('I heard the sound')) throw new Error('Speaker confirmation unavailable');
    await new Promise(resolve=>setTimeout(resolve,250));
    let accepted=false;
    for(let i=0;i<20;i++){
      accepted=await window.webContents.executeJavaScript("(()=>{const input=document.querySelector('input[type=checkbox]');if(!input)return false;input.click();return true;})()");
      if(accepted)break;
      await press('I heard the sound');await new Promise(resolve=>setTimeout(resolve,250));
    }
    if(!accepted)throw new Error('Setup did not reach interview consent');
    await new Promise(resolve=>setTimeout(resolve,200));
    if(!await press('Start interview')) throw new Error('Interview start unavailable');
    await new Promise(resolve=>setTimeout(resolve,1500));
    const layout=await window.webContents.executeJavaScript("({width:innerWidth,pageWidth:document.documentElement.scrollWidth,transcript:document.querySelector('[aria-label=\"Interview conversation\"]')?.textContent,canvas:!!document.querySelector('[aria-label=\"Interview voice activity\"] canvas'),typedAnswer:!!document.querySelector('textarea')})");
    if(!layout.canvas||layout.typedAnswer||layout.pageWidth>layout.width||!layout.transcript.includes('hiring platform')) throw new Error('Interview layout failed: '+JSON.stringify(layout));
    await fs.writeFile(path.join(files,'interview-layout.png'),(await window.webContents.capturePage()).toPNG());
    const responsive = [];
    for (const width of [900, 390]) {
      window.setSize(width, 900);
      await new Promise(resolve => setTimeout(resolve, 200));
      const measured = await window.webContents.executeJavaScript('({width:innerWidth,pageWidth:document.documentElement.scrollWidth})');
      if (measured.pageWidth > measured.width) throw new Error('Responsive layout overflow: '+JSON.stringify(measured));
      responsive.push(measured);
    }
    await fs.writeFile(path.join(files,'interview-mobile-layout.png'),(await window.webContents.capturePage()).toPNG());
    await window.webContents.executeJavaScript('window.interviewCleanup()');
    console.log('PASS real interview layout, captions, WebGL, worklet and cleanup:',JSON.stringify({...layout,responsive}));
    window.destroy(); server.close(); app.exit(0);
  } catch(error) { console.error('FAIL voice runtime:',error.message); if(window)console.error(await window.webContents.executeJavaScript('document.body.textContent').catch(()=>''));window?.destroy();server?.close();app.exit(1); }
});
setTimeout(()=>{console.error('FAIL voice runtime: deadline exceeded');app.exit(1);},30000).unref();

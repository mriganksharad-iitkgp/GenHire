// Render the real interview UI without accounts, devices or paid API requests.
import { build } from "esbuild";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
const target = path.resolve("../secure-browser-kiosk/.voice-runtime-smoke");
await mkdir(target, { recursive: true });
const source = `
import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter} from 'react-router-dom';
import Chat from './src/features/interview/pages/Chat.jsx';
sessionStorage.setItem('companyxyz-token','fixture-token');
window.electronAPI={enableKiosk(){},disableKiosk(){},onAppSwitched(){}};
const context=new AudioContext(),osc=context.createOscillator(),gain=context.createGain(),destination=context.createMediaStreamDestination();
osc.frequency.value=160;gain.gain.value=.08;osc.connect(gain);gain.connect(destination);osc.start();await context.resume();
const canvas=document.createElement('canvas');canvas.width=640;canvas.height=480;const graphics=canvas.getContext('2d');
function camera(){graphics.fillStyle='#e9edf7';graphics.fillRect(0,0,640,480);graphics.fillStyle='#bec9e4';graphics.beginPath();graphics.arc(320,170,68,0,Math.PI*2);graphics.fill();graphics.beginPath();graphics.ellipse(320,420,142,150,0,0,Math.PI*2);graphics.fill();graphics.fillStyle='#536584';graphics.font='18px Arial';graphics.fillText('Test camera stream',235,35);requestAnimationFrame(camera);}camera();
const stream=new MediaStream([...canvas.captureStream(15).getVideoTracks(),...destination.stream.getAudioTracks()]);
navigator.mediaDevices.getUserMedia=async()=>stream.clone();
window.fetch=async(url,options={})=>{let data={};const path=String(url);
if(path.endsWith('/session'))data={session_id:'preview-session',status:'setup',current_question:'Tell me about a product you built and the impact it had.',max_questions:10,question_count:1,identity_captured:true,engine_available:true,proctoring_config:{},dual_proctoring_required:false};
if(path.endsWith('/activate'))data={current_question:'Tell me about a product you built and the impact it had.',question_deadline:Date.now()/1000+300};
if(path.endsWith('/monitoring'))data={integrity:{count:2,counts_by_type:{tab_switch:1,mobile_unavailable:1},losses:{},auto_termination:false}};
return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});};
window.fixtureSocket=()=>{const listeners=new Map();const socket={connected:true,on(event,callback){listeners.set(event,[...(listeners.get(event)||[]),callback]);return this;},off(event,callback){listeners.set(event,(listeners.get(event)||[]).filter(item=>item!==callback));return this;},emit(event,data,ack){ack?.({ok:true});if(event==='speech_live_start')setTimeout(()=>socket.fire('speech_live_transcript',{stream_id:data.stream_id,transcript:'I built a hiring platform that helped our recruiting team assess candidates more consistently.'}),500);return this;},disconnect(){this.connected=false;},fire(event,data){(listeners.get(event)||[]).forEach(fn=>fn(data));}};setTimeout(()=>socket.fire('connect'),0);return socket;};
const root=createRoot(document.getElementById('app'));root.render(React.createElement(MemoryRouter,null,React.createElement(Chat,{interviewId:'preview-session',apiBase:'/api',webOrigin:location.origin})));
window.interviewCleanup=async()=>{root.unmount();stream.getTracks().forEach(track=>track.stop());osc.stop();await context.close();};
`;
await build({ stdin: { contents: source, resolveDir: process.cwd(), loader: "jsx" }, bundle: true,
  outfile: path.join(target, "interview.js"), format: "esm", platform: "browser", loader: { ".js": "jsx", ".png": "dataurl", ".svg": "dataurl" },
  alias: Object.fromEntries(["app", "features", "shared", "assets"].map(name => [name, path.resolve("src", name)])),
  define: { "process.env": JSON.stringify({ NODE_ENV: "production" }) },
  plugins: [{ name: "fixture-socket", setup(plugin) {
    plugin.onResolve({ filter: /^socket.io-client$/ }, () => ({ path: "socket", namespace: "fixture" }));
    plugin.onLoad({ filter: /.*/, namespace: "fixture" }, () => ({ contents: "export default (...args)=>window.fixtureSocket(...args);", loader: "js" }));
  } }] });
await writeFile(path.join(target, "interview.html"), '<!doctype html><html><head><link rel="stylesheet" href="/assets/theme.css"><link rel="stylesheet" href="/assets/interview.css"></head><body style="padding:0"><div id="app"></div><script type="module" src="/assets/interview.js"></script></body></html>');
await writeFile(path.join(target, "interview-pcm-worklet.js"), await readFile("public/assets/interview-pcm-worklet.js"));

// Test artifact only: real WebGL and Web Audio with a known silent-output signal.
import { build } from "esbuild";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import path from "node:path";
const target = path.resolve("../secure-browser-kiosk/.voice-runtime-smoke");
await mkdir(target, { recursive: true });
const source = `
import React from "react";
import {createRoot} from "react-dom/client";
import VoiceSphere,{analyserLevel} from "./src/features/interview/components/VoiceSphere.jsx";
const root=createRoot(document.getElementById('app'));
const context=new AudioContext(), analyser=context.createAnalyser(); analyser.fftSize=1024;
const oscillator=context.createOscillator(), gain=context.createGain(), silence=context.createGain();
oscillator.frequency.value=180; gain.gain.value=0; silence.gain.value=0;
oscillator.connect(gain);gain.connect(analyser);analyser.connect(silence);silence.connect(context.destination);oscillator.start();
await context.resume();
const audioRef={current:{microphone:analyser,speaker:analyser}};
const states=['idle','listening','processing','speaking','interrupted'];
root.render(React.createElement('main',null,React.createElement('h1',null,'GenHire voice activity'),React.createElement('p',null,'Dotted 3D particles · Web Audio driven · Five voice states'),React.createElement('div',{className:'gallery'},...states.map(state=>React.createElement('article',{key:state},React.createElement('h2',null,state),React.createElement(VoiceSphere,{state,audioRef}))))));
await new Promise(resolve=>setTimeout(resolve,500));
const samples=new Uint8Array(1024), quiet=analyserLevel(analyser,samples);gain.gain.value=.16;
await new Promise(resolve=>setTimeout(resolve,1200));
window.voiceResults={hidden:document.hidden,quiet,active:analyserLevel(analyser,samples),canvases:document.querySelectorAll('canvas').length,labels:[...document.querySelectorAll('[data-state]')].map(node=>node.textContent)};
window.cleanupVoice=async()=>{root.unmount();oscillator.stop();oscillator.disconnect();gain.disconnect();analyser.disconnect();silence.disconnect();await context.close();return {canvases:document.querySelectorAll('canvas').length,context:context.state};};
`;
await build({ stdin: { contents: source, resolveDir: process.cwd(), loader: "jsx" }, bundle: true,
  outfile: path.join(target, "voice.js"), format: "esm", platform: "browser", loader: { ".js": "jsx" },
  define: { "process.env.NODE_ENV": '"production"' } });
await writeFile(path.join(target, "theme.css"), (await readFile("src/shared/styles/portal-theme.css", "utf8")) +
  "body{margin:0;padding:30px;background:#f7f8fc;font-family:Arial;color:#253148}h1{font-size:24px;margin:0 0 10px}main>p{color:#74829a;font-size:13px}.gallery{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:18px;margin-top:32px}.gallery article{min-width:0}h2{font-size:13px;text-transform:capitalize;color:#7162b4;font-weight:500}");
await writeFile(path.join(target, "index.html"), '<!doctype html><html><head><link rel="stylesheet" href="/assets/theme.css"><link rel="stylesheet" href="/assets/voice.css"></head><body><div id="app"></div><script type="module" src="/assets/voice.js"></script></body></html>');

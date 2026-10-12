import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import styles from "./VoiceSphere.module.css";

export const VOICE_LABELS = { idle: "Ready when you are", listening: "Listening to you",
  processing: "Preparing your next response", speaking: "Alex is speaking", interrupted: "Voice paused" };

const vertex = `
  uniform float time; uniform float level; uniform float activity; uniform float pointScale;
  varying float light;
  void main() {
    vec3 direction = normalize(position);
    float wave = sin(direction.y * 9.0 + time * 1.8) * cos(direction.x * 7.0 - time);
    float breath = sin(time * 1.4) * 0.012;
    vec3 p = position * (1.0 + breath + wave * (0.016 * activity + 0.18 * level));
    vec4 view = modelViewMatrix * vec4(p, 1.0);
    light = 0.55 + 0.45 * (direction.z * 0.5 + 0.5);
    gl_PointSize = clamp(pointScale * (1.0 + level * 0.65) / -view.z, 1.0, 7.0);
    gl_Position = projectionMatrix * view;
  }`;
const fragment = `
  uniform vec3 tint; varying float light;
  void main() {
    float r = length(gl_PointCoord - vec2(0.5));
    if (r > 0.5) discard;
    float glow = exp(-r * r * 14.0);
    gl_FragColor = vec4(tint * (0.8 + glow * 0.7), glow * light);
  }`;

export function analyserLevel(analyser, samples) {
  if (!analyser) return 0;
  analyser.getByteTimeDomainData(samples);
  let total = 0;
  for (const sample of samples) total += ((sample - 128) / 128) ** 2;
  return Math.min(1, Math.sqrt(total / samples.length) * 5);
}

/** Reuses caller-owned analysers; never opens a microphone or closes its context. */
export default function VoiceSphere({ state = "idle", audioRef, caption }) {
  const host = useRef(null), latest = useRef({ state, audioRef }); latest.current = { state, audioRef };
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    const element = host.current;
    let renderer, geometry, material, timer = 0, resize, lost, disposed = false;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(35, 1, .1, 20);
    camera.position.z = 3.7;
    const tint = new THREE.Color("#7761ef"), target = new THREE.Color();
    let level = 0, activity = 0, last = performance.now();
    const samples = new Uint8Array(1024);
    if (!window.WebGL2RenderingContext) { setUnavailable(true); return undefined; }
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
      renderer.setClearColor(0x000000, 0); element.appendChild(renderer.domElement);
      renderer.domElement.setAttribute("aria-hidden", "true");
      const points = new Float32Array(2800 * 3), golden = Math.PI * (3 - Math.sqrt(5));
      for (let i = 0; i < 2800; i++) {
        const y = 1 - 2 * (i + .5) / 2800, radius = Math.sqrt(1 - y * y), angle = i * golden;
        points.set([Math.cos(angle) * radius, y, Math.sin(angle) * radius], i * 3);
      }
      geometry = new THREE.BufferGeometry(); geometry.setAttribute("position", new THREE.BufferAttribute(points, 3));
      material = new THREE.ShaderMaterial({ vertexShader: vertex, fragmentShader: fragment,
        uniforms: { time: { value: 0 }, level: { value: 0 }, activity: { value: 0 }, tint: { value: tint }, pointScale: { value: 10 } },
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
      const sphere = new THREE.Points(geometry, material); scene.add(sphere);
      const size = () => { const { width, height } = element.getBoundingClientRect();
        renderer.setSize(Math.max(1, width), Math.max(1, height)); camera.aspect = Math.max(1, width) / Math.max(1, height); camera.updateProjectionMatrix(); };
      size(); resize = new ResizeObserver(size); resize.observe(element);
      const draw = now => {
        if (disposed) return;
        if (!document.hidden) {
          const dt = Math.min(.1, (now - last) / 1000), current = latest.current;
          const analyser = current.state === "listening" ? current.audioRef?.current?.microphone
            : current.state === "speaking" ? current.audioRef?.current?.speaker : null;
          const measured = analyserLevel(analyser, samples);
          level += (measured - level) * (1 - Math.exp(-dt * (measured > level ? 15 : 6)));
          const motion = current.state === "processing" ? 1 : current.state === "interrupted" ? 0 : .3;
          activity += (motion - activity) * (1 - Math.exp(-dt * 4));
          target.set(current.state === "speaking" ? "#20bba5" : current.state === "listening" ? "#568ef5" : "#8760f2");
          tint.lerp(target, 1 - Math.exp(-dt * 4));
          if (!reduced?.matches) { material.uniforms.time.value += dt; sphere.rotation.y += dt * (.09 + activity * .12); sphere.rotation.x = .16; }
          material.uniforms.level.value = reduced?.matches ? level * .15 : level;
          material.uniforms.activity.value = reduced?.matches ? 0 : activity;
          material.uniforms.tint.value.copy(tint); material.uniformsNeedUpdate = true;
          renderer.render(scene, camera);
        }
        last = now; timer = requestAnimationFrame(draw);
      };
      timer = requestAnimationFrame(draw);
      lost = event => { event.preventDefault(); cancelAnimationFrame(timer); if (!disposed) setUnavailable(true); };
      renderer.domElement.addEventListener("webglcontextlost", lost);
    } catch { setUnavailable(true); }
    return () => { disposed = true; cancelAnimationFrame(timer); resize?.disconnect();
      if (lost) renderer?.domElement.removeEventListener("webglcontextlost", lost);
      geometry?.dispose(); material?.dispose(); renderer?.dispose(); renderer?.forceContextLoss(); renderer?.domElement.remove(); };
  }, []);
  return <section className={styles.panel} aria-label="Interview voice activity">
    <div ref={host} className={styles.canvas} />
    {unavailable && <div className={styles.fallback} aria-hidden="true" />}
    <span className={styles.label} data-state={state}>{VOICE_LABELS[state] || VOICE_LABELS.idle}</span>
    <p className={styles.caption}>{caption || "Voice activity responds to your microphone and the interviewer audio."}</p>
  </section>;
}

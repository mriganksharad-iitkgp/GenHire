// Copy the pinned runtime locally; candidate capture never depends on a CDN.
import { copyFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const destination = new URL("../public/assets/", import.meta.url);
await mkdir(destination, { recursive: true });
for (const name of ["vision_wasm_internal.js", "vision_wasm_internal.wasm", "vision_wasm_nosimd_internal.js", "vision_wasm_nosimd_internal.wasm"]) {
  await copyFile(fileURLToPath(new URL(`../node_modules/@mediapipe/tasks-vision/wasm/${name}`, import.meta.url)), fileURLToPath(new URL(name, destination)));
}

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.dirname(fileURLToPath(import.meta.url));
export default defineConfig({
  envPrefix: [],
  root: path.join(root, "kiosk"), plugins: [react()],
  publicDir: path.join(root, "public"),
  define: { "process.env": JSON.stringify({ NODE_ENV: "production" }) },
  resolve: { alias: { features: path.join(root, "src/features"), shared: path.join(root, "src/shared"), "/src": path.join(root, "src") } },
  build: { outDir: path.join(root, "../secure-browser-kiosk/web-app"), emptyOutDir: true, sourcemap: false },
});

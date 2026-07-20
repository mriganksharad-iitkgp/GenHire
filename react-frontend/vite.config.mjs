import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

// This app was migrated from Create React App. Two CRA behaviours are
// preserved here so no source files had to change:
//
// 1. Config is read through `process.env.REACT_APP_*` in ~30 files (see
//    .env / .env.production). Vite only exposes VITE_-prefixed vars on
//    import.meta.env, so we load every REACT_APP_* var for the active mode
//    and statically shim `process.env` with them (plus NODE_ENV). Referenced
//    vars that are unset read back as `undefined`, exactly like under CRA.
//
// 2. JSX lives inside some `.js` files (e.g. src/index.js, a few hooks).
//    esbuild must be told to parse `.js` as JSX or those files fail to build.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, rootDir, "REACT_APP_");

  return {
    plugins: [react()],
    define: {
      "process.env": JSON.stringify({ NODE_ENV: mode, ...env }),
    },
    resolve: {
      // Mirrors jsconfig.json baseUrl:"src" — bare imports like
      // "features/payment/api" or "shared/utils/session" resolve from src/.
      alias: {
        app: path.resolve(rootDir, "src/app"),
        assets: path.resolve(rootDir, "src/assets"),
        features: path.resolve(rootDir, "src/features"),
        shared: path.resolve(rootDir, "src/shared"),
      },
    },
    server: { port: 3000, open: false },
    preview: { port: 3000 },
    // Keep CRA's output directory so existing deploy configs that publish
    // `build/` keep working unchanged.
    build: { outDir: "build", sourcemap: false },
    esbuild: { loader: "jsx", include: /src\/.*\.jsx?$/, exclude: [] },
    optimizeDeps: { esbuildOptions: { loader: { ".js": "jsx" } } },
  };
});

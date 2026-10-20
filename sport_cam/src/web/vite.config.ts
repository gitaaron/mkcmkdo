import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// The app calls /api on its own origin. Deployed, Firebase Hosting rewrites
// that to the `api` function; in dev, Vite proxies it to the functions
// emulator (npm run dev starts the emulators alongside).
const FUNCTIONS = "http://127.0.0.1:5001";
const API_PATH = "/demo-sportcam/us-central1/api";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true, // reachable through Docker/sandbox port mapping, and from a phone
    port: 5173,
    proxy: {
      "/api": { target: FUNCTIONS, changeOrigin: true, rewrite: (p) => API_PATH + p },
    },
  },
});

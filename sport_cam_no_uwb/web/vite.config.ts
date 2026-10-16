import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// The app only ever talks to its own origin; in dev Vite proxies to the API.
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true, // reachable through Docker/sandbox port mapping
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8787", changeOrigin: true },
      "/ws": { target: "ws://localhost:8787", ws: true },
    },
  },
});

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies /api to the FastAPI backend so the SPA uses same-origin calls
// (mirrors the nginx proxy used in the Docker/compose build). Override target with
// VITE_API_TARGET if the backend runs on a non-default port.
export default defineConfig(() => ({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
}));

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { readFileSync } from "node:fs";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

// In development, /api calls go to the FastAPI backend on port 8000.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
  // start.bat serves the built app (fast) with the same /api proxy
  preview: {
    port: 5173,
    strictPort: true,
    headers: { "Cache-Control": "no-cache" },  // always check for a newer build (no stale screens after an update)
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
  build: {
    chunkSizeWarningLimit: 1500,
    rollupOptions: { output: { manualChunks: { react: ["react", "react-dom", "react-router-dom"] } } },
  },
});

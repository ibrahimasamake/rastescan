import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API runs on :8000 (see backend/README). Relative paths keep the build working inside the Android app.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { host: true, allowedHosts: true, proxy: { "/api": "http://localhost:8000" } },
});

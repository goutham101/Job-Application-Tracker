import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend serves at the root path, so proxy each API prefix.
// Overridable so the Docker Compose frontend container can reach the "api"
// service by name instead of the host-only 127.0.0.1 default.
const API = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/applications": API,
      "/companies": API,
      "/stats": API,
      "/matches": API,
      "/questions": API,
    },
  },
});

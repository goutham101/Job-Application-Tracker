import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend serves at the root path, so proxy each API prefix.
const API = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/applications": API,
      "/companies": API,
      "/stats": API,
    },
  },
});

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const apiBase = process.env.TRADING_API_BASE || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      "/api": apiBase,
      "/health": apiBase,
      "/readyz": apiBase
    }
  }
});

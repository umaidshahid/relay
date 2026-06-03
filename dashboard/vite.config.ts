import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: "/dashboard/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/stats": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/v1": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});

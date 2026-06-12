import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" → semua aset relatif, aman saat di-embed via iframe di domain mana pun.
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
  build: {
    outDir: "dist",
    chunkSizeWarningLimit: 1500,
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "static/frontend",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        dashboard: "frontend/src/dashboard.jsx",
        ordenes: "frontend/src/ordenes.jsx",
        ordenDetalle: "frontend/src/ordenDetalle.jsx",
        caja: "frontend/src/caja.jsx",
        clientes: "frontend/src/clientes.jsx",
        clienteDetalle: "frontend/src/clienteDetalle.jsx",
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "[name].js",
        assetFileNames: "[name][extname]",
      },
    },
  },
});

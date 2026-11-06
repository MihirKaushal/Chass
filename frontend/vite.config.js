import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Load the worker's WASM from our verified static runtime directory, not a second bundled copy.
  resolve: { conditions: ["onnxruntime-web-use-extern-wasm"] },
  server: {
    port: 5173,
  },
});

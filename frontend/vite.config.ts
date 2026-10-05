import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// strictPort: the backend's CORS allows http://localhost:5173, so never drift to another port.
export default defineConfig({
  plugins: [react()],
  server: { port: Number(process.env.PORT ?? 5173), strictPort: true },
});

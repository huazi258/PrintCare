import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      proxy: {
        "/api/core": {
          target: env.VITE_CORE_API_TARGET || "http://127.0.0.1:8001",
          changeOrigin: true,
          rewrite: (requestPath) => requestPath.replace(/^\/api\/core/, ""),
        },
        "/api/admin": {
          target: env.VITE_ADMIN_API_TARGET || "http://127.0.0.1:8000",
          changeOrigin: true,
          rewrite: (requestPath) => requestPath.replace(/^\/api\/admin/, ""),
        },
      },
    },
  };
});

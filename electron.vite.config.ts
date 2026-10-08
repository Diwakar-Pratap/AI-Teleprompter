import { defineConfig, externalizeDepsPlugin } from "electron-vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    resolve: {
      alias: {
        "@shared": resolve("shared"),
      },
    },
    build: {
      rollupOptions: {
        input: {
          index: resolve("desktop/electron/main.ts"),
        },
      },
    },
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: {
          index: resolve("desktop/electron/preload.ts"),
        },
      },
    },
  },
  renderer: {
    root: "desktop/renderer",
    resolve: {
      alias: {
        "@": resolve("desktop/renderer"),
        "@shared": resolve("shared"),
      },
    },
    plugins: [react()],
    build: {
      rollupOptions: {
        input: {
          index: resolve("desktop/renderer/index.html"),
        },
      },
    },
  },
});

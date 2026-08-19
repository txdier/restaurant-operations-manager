import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  root: path.resolve(__dirname),
  plugins: [react()],
  base: "/",
  build: {
    outDir: path.resolve(__dirname, "../desktop/restaurant_manager/web"),
    emptyOutDir: true,
    // PyQtWebEngine-Qt5 5.15.2 embeds an older Chromium build. Keep the
    // generated syntax below logical-assignment support (&&=, ||=, ??=).
    target: "chrome80",
  },
});

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 45000,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:14173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    reducedMotion: "reduce",
    launchOptions: { args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] },
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "narrow", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    { command: "../.venv/bin/python ../scripts/e2e_server.py", url: "http://127.0.0.1:18100/health", timeout: 30000, reuseExistingServer: false },
    { command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 14173 --strictPort", url: "http://127.0.0.1:14173", env: { VITE_API_URL: "http://127.0.0.1:18100", VITE_SCANNER_API_URL: "", VITE_SCANNER_WAKE_URL: "" }, reuseExistingServer: false },
  ],
});

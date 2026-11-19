import { defineConfig, devices } from "@playwright/test";

const PORT = 8765;

/**
 * E2E against the real stdlib server (backend) serving the built frontend/dist.
 * Run `npm run build` first so dist matches the sources.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
  webServer: {
    command: `python3 -m audit_env.server --port ${PORT}`,
    cwd: "../backend",
    env: { PYTHONPATH: "src" },
    url: `http://127.0.0.1:${PORT}/api/episodes`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});

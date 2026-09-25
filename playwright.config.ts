import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  // Journeys share the two synthetic OIDC accounts and their revision streams.
  workers: 1,
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
    },
    {
      command:
        process.platform === "win32"
          ? ".venv\\Scripts\\python.exe -m planner.cli serve"
          : ".venv/bin/python -m planner.cli serve",
      url: "http://127.0.0.1:8000/health/live",
      reuseExistingServer: !process.env.CI,
    },
  ],
});

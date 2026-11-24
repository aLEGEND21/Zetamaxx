import path from "node:path";
import { defineConfig } from "@playwright/test";

// The end-to-end test runs against its own API and web servers, on their own
// ports and with a throwaway database, so it never touches `make dev` or its data.
const ROOT = path.join(__dirname, "..");
try {
  process.loadEnvFile(path.join(ROOT, ".env"));
} catch {
  // No .env: global setup reports the missing Clerk keys.
}

const WEB_PORT = 3210;
const API_PORT = 8210;
const WEB_URL = `http://localhost:${WEB_PORT}`;
const DATABASE_PATH = path.join(__dirname, "test-results", "e2e.db");

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 6 * 60_000, // two real 120-second games are played
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: "list",
  use: {
    baseURL: WEB_URL,
    channel: process.env.E2E_BROWSER_CHANNEL, // e.g. "chrome" to use the installed browser
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `rm -f "${DATABASE_PATH}"* && uv run uvicorn app.main:app --port ${API_PORT}`,
      cwd: path.join(ROOT, "api"),
      url: `http://localhost:${API_PORT}/api/health`,
      env: { DATABASE_PATH, ALLOWED_ORIGINS: WEB_URL },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx next dev --port ${WEB_PORT}`,
      url: WEB_URL,
      env: { NEXT_PUBLIC_E2E: "1", API_URL: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});

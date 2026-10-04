import { defineConfig } from '@playwright/test'

// End-to-end tests run against the real stack (nginx -> Vite -> Django -> Postgres),
// using the Brave already installed on the machine (no browser download).
export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'https://re-re.test',
    ignoreHTTPSErrors: true,
    viewport: { width: 1280, height: 800 },
    launchOptions: {
      executablePath: process.env.BROWSER_PATH ?? '/usr/bin/brave-browser',
      // E2E_SLOWMO=700 slows every action so a human can follow it (use with --headed).
      slowMo: Number(process.env.E2E_SLOWMO ?? 0),
    },
  },
})

import { defineConfig, devices } from '@playwright/test';

/**
 * Headless Chromium harness for the DAY-1 SVG/geometry regression suite.
 *
 * The config is also imported by the repository-level config so the documented
 * `npx --prefix .../engine playwright test` invocation works from any cwd.
 */
export default defineConfig({
  testDir: './tests',
  testMatch: /.*\.spec\.ts$/,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: [['list']],
  outputDir: './test-results',
  use: {
    headless: true,
    viewport: { width: 1400, height: 1000 },
    screenshot: 'only-on-failure',
    trace: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        headless: true,
      },
    },
  ],
});

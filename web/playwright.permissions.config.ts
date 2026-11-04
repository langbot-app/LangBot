import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch:
    /(?:plugin-permissions|agent-workspace-tools|pipeline-platform-tools|plugin-upgrade-recovery)\.spec\.ts/,
  workers: 1,
  retries: 0,
  reporter: 'list',
  outputDir: './test-results/permissions',
  use: {
    baseURL: 'http://127.0.0.1:4178',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command:
      'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4178 --strictPort',
    url: 'http://127.0.0.1:4178',
    reuseExistingServer: false,
    timeout: 120_000,
  },
});

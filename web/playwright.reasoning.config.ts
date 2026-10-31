import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e',
  workers: 1,
  retries: 0,
  timeout: 30000,
  reporter: 'list',
  outputDir: '/tmp/411-reasoning-results',
  use: { baseURL: 'http://127.0.0.1:4196' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command:
      'taskset -c 0,1 node node_modules/vite/bin/vite.js --config vite.reasoning.config.ts --host 127.0.0.1 --port 4196',
    url: 'http://127.0.0.1:4196',
    reuseExistingServer: true,
  },
});

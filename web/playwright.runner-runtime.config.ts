import { defineConfig, devices } from '@playwright/test';

const port = process.env.LANGBOT_RUNNER_WEB_PORT;
if (!port || !process.env.LANGBOT_RUNNER_API_URL) {
  throw new Error(
    'Run through tests/e2e/test_runner_plugin_runtime.py with its isolated backend and SDK runtime',
  );
}

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'runner-real-runtime.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: 'list',
  outputDir: process.env.LANGBOT_RUNNER_BROWSER_OUTPUT,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: `node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: { VITE_API_PROXY_TARGET: process.env.LANGBOT_RUNNER_API_URL },
  },
});

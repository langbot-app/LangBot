import { defineConfig } from '@playwright/test';
import base from './playwright.config';
export default defineConfig({
  ...base,
  retries: 0,
  outputDir: 'test-results-structured',
  use: { ...base.use, baseURL: 'http://127.0.0.1:4197' },
  webServer: {
    command:
      'taskset -c 0,1 node node_modules/vite/bin/vite.js --config vite.structured.config.ts --host 127.0.0.1 --port 4197 --strictPort',
    url: 'http://127.0.0.1:4197',
    reuseExistingServer: false,
    timeout: 120000,
  },
});

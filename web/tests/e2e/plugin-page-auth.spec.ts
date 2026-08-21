import { expect, test } from '@playwright/test';
import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

function wrapped(data: unknown) {
  return JSON.stringify({
    code: 0,
    message: 'ok',
    data,
    timestamp: Date.now(),
  });
}

test('loads a Cloud plugin page through the authenticated asset route', async ({
  page,
}) => {
  const workspace = makeWorkspaceEntry(
    'workspace-cloud',
    'Cloud Workspace',
    'cloud_projection',
  );
  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [workspace],
  });

  await page.route('**/api/v1/plugins', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: wrapped({
        plugins: [
          {
            install_source: 'marketplace',
            install_info: {},
            debug: false,
            manifest: {
              manifest: {
                metadata: {
                  author: 'langbot-team',
                  name: 'LangRAG',
                  version: '0.1.9',
                  label: { en_US: 'LangRAG', zh_Hans: 'LangRAG' },
                },
                spec: {
                  pages: [
                    {
                      id: 'observability',
                      path: 'components/pages/observability.html',
                      label: { en_US: 'Observability', zh_Hans: '观测面板' },
                    },
                  ],
                },
              },
            },
          },
        ],
      }),
    });
  });

  let authenticatedAssetRequests = 0;
  await page.route(
    '**/api/v1/plugins/langbot-team/LangRAG/authenticated-assets/**',
    async (route) => {
      authenticatedAssetRequests += 1;
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: `<!doctype html>
          <html>
            <body>
              <h1>LangRAG Observability</h1>
              <button id="save">Save</button>
              <script src="/api/v1/plugins/_sdk/page-sdk.js"></script>
              <script>
                document.querySelector('#save').addEventListener('click', async () => {
                  await window.langbot.api('/settings', { enabled: true }, 'POST');
                  document.body.dataset.saved = 'true';
                });
              </script>
            </body>
          </html>`,
      });
    },
  );
  let pageSdkRequests = 0;
  await page.route('**/api/v1/plugins/_sdk/page-sdk.js', async (route) => {
    pageSdkRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/javascript',
      body: `window.langbot = {
        api(endpoint, body, method) {
          return new Promise((resolve) => {
            const requestId = 'request-' + Date.now();
            const handler = (event) => {
              if (event.data?.type === 'langbot:api:response' && event.data.requestId === requestId) {
                window.removeEventListener('message', handler);
                resolve(event.data.data);
              }
            };
            window.addEventListener('message', handler);
            window.parent.postMessage({ type: 'langbot:api', requestId, endpoint, body, method }, '*');
          });
        },
      };`,
    });
  });
  let pageApiRequests = 0;
  await page.route(
    '**/api/v1/plugins/langbot-team/LangRAG/page-api',
    async (route) => {
      pageApiRequests += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: wrapped({ saved: true }),
      });
    },
  );

  await page.goto(
    '/home/plugin-pages?id=langbot-team%2FLangRAG%2Fobservability',
  );

  const pluginFrame = page.frameLocator('iframe');
  await expect(
    pluginFrame.getByRole('heading', { name: 'LangRAG Observability' }),
  ).toBeVisible();
  await pluginFrame.getByRole('button', { name: 'Save' }).click();
  await expect(pluginFrame.locator('body')).toHaveAttribute(
    'data-saved',
    'true',
  );
  expect(authenticatedAssetRequests).toBeGreaterThan(0);
  expect(pageSdkRequests).toBe(1);
  expect(pageApiRequests).toBe(1);
  await expect(page.getByText('Loading...')).toHaveCount(0);
});

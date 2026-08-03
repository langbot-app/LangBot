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
        body: '<!doctype html><html><body><h1>LangRAG Observability</h1></body></html>',
      });
    },
  );

  await page.goto(
    '/home/plugin-pages?id=langbot-team%2FLangRAG%2Fobservability',
  );

  await expect(
    page
      .frameLocator('iframe')
      .getByRole('heading', { name: 'LangRAG Observability' }),
  ).toBeVisible();
  expect(authenticatedAssetRequests).toBeGreaterThan(0);
  await expect(page.getByText('Loading...')).toHaveCount(0);
});

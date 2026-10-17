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
  let pageSdkRequests = 0;
  let pageApiRequests = 0;
  await page.route('**/api/v1/plugins/_sdk/page-sdk.js', async (route) => {
    pageSdkRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/javascript',
      body: `window.langbot = {
        onReady(callback) { callback(); },
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
  await page.route(
    '**/api/v1/plugins/langbot-team/LangRAG/authenticated-assets/**',
    async (route) => {
      authenticatedAssetRequests += 1;
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: `<!doctype html><html><body><main></main><button id="save">Save</button>
          <script src="/api/v1/plugins/_sdk/page-sdk.js"></script>
          <script>
            langbot.onReady(() => {
              document.querySelector('main').innerHTML = '<h1>LangRAG Observability</h1>';
              document.querySelector('#save').addEventListener('click', async () => {
                await window.langbot.api('/settings', { enabled: true }, 'POST');
                document.body.dataset.saved = 'true';
              });
            });
          </script>
        </body></html>`,
      });
    },
  );
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

for (const pendingAsset of [false, true]) {
  test(`Workspace switch discards ${pendingAsset ? 'late' : 'loaded'} plugin assets`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      workspaces: [
        makeWorkspaceEntry('workspace-alpha', 'Alpha Workspace'),
        makeWorkspaceEntry('workspace-beta', 'Beta Workspace'),
      ],
    });
    await page.route('**/api/v1/plugins', async (route) => {
      const scope = route.request().headers()['x-workspace-id'];
      expect(['workspace-alpha', 'workspace-beta']).toContain(scope);
      const label = scope === 'workspace-alpha' ? 'Alpha page' : 'Beta page';
      await route.fulfill({
        json: {
          code: 0,
          data: {
            plugins: [
              {
                install_source: 'marketplace',
                install_info: {},
                debug: false,
                manifest: {
                  manifest: {
                    metadata: {
                      author: 'qa',
                      name: 'scoped-page',
                      version: '1.0.0',
                      label: { en_US: label },
                    },
                    spec: {
                      pages: [
                        {
                          id: 'overview',
                          path: 'overview.html',
                          label: { en_US: label },
                        },
                      ],
                    },
                  },
                },
              },
            ],
          },
        },
      });
    });
    const assetHeaders: Record<string, string>[] = [];
    let releaseAsset = () => {};
    const assetGate = new Promise<void>((resolve) => {
      releaseAsset = resolve;
    });
    let assetSettled = () => {};
    const assetFinished = new Promise<void>((resolve) => {
      assetSettled = resolve;
    });
    await page.route(
      '**/api/v1/plugins/qa/scoped-page/authenticated-assets/overview.html',
      async (route) => {
        const headers = route.request().headers();
        assetHeaders.push(headers);
        expect(['workspace-alpha', 'workspace-beta']).toContain(
          headers['x-workspace-id'],
        );
        if (pendingAsset && headers['x-workspace-id'] === 'workspace-alpha') {
          await assetGate;
        }
        const label =
          headers['x-workspace-id'] === 'workspace-alpha' ? 'Alpha' : 'Beta';
        await route.fulfill({
          contentType: 'text/html',
          body: `<!doctype html><html><body><h1>${label} private page</h1></body></html>`,
        });
        if (headers['x-workspace-id'] === 'workspace-alpha') assetSettled();
      },
    );

    try {
      await page.goto('/home/plugin-pages?id=qa%2Fscoped-page%2Foverview');
      await page.getByRole('button', { name: /Alpha Workspace/ }).click();
      await expect(
        page.getByRole('button', { name: 'Alpha page' }),
      ).toBeVisible();
      await expect.poll(() => assetHeaders.length).toBeGreaterThan(0);
      let previousAssetUrl: string | null = null;
      if (!pendingAsset) {
        await expect(
          page.frameLocator('iframe').getByRole('heading', {
            name: 'Alpha private page',
          }),
        ).toBeVisible();
        previousAssetUrl = await page.locator('iframe').getAttribute('src');
      }
      expect(assetHeaders[0]['x-workspace-id']).toBe('workspace-alpha');
      expect(assetHeaders[0].authorization).toBe('Bearer playwright-token');

      await page.getByRole('button', { name: 'Switch Workspace' }).click();
      await page.getByRole('menuitem', { name: /Beta Workspace/ }).click();
      const switcher = page.getByRole('button', { name: 'Switch Workspace' });
      await expect(page).toHaveURL('/home/monitoring');
      await expect(switcher).toContainText('Beta Workspace');
      await expect(
        page.getByRole('button', { name: 'Beta page' }),
      ).toBeVisible();
      await expect(
        page.getByRole('button', { name: 'Alpha page' }),
      ).toHaveCount(0);
      await expect(page.locator('iframe')).toHaveCount(0);
      if (previousAssetUrl) {
        expect(
          await page.evaluate(async (url) => {
            try {
              await fetch(url);
              return true;
            } catch {
              return false;
            }
          }, previousAssetUrl),
        ).toBe(false);
      }

      const assetsBeforeBeta = assetHeaders.length;
      await page.getByRole('button', { name: 'Beta page' }).click();
      await expect
        .poll(() => assetHeaders.length)
        .toBeGreaterThan(assetsBeforeBeta);
      expect(assetHeaders.at(-1)?.['x-workspace-id']).toBe('workspace-beta');
      expect(assetHeaders.at(-1)?.authorization).toBe(
        'Bearer playwright-token',
      );
      const pluginFrame = page.frameLocator('iframe');
      await expect(
        pluginFrame.getByRole('heading', { name: 'Beta private page' }),
      ).toBeVisible();
      releaseAsset();
      await assetFinished;
      await expect(
        pluginFrame.getByRole('heading', { name: 'Beta private page' }),
      ).toBeVisible();
      await expect(
        pluginFrame.getByRole('heading', { name: 'Alpha private page' }),
      ).toHaveCount(0);
    } finally {
      releaseAsset();
    }
  });
}

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
  const assetHeaders: Array<Record<string, string>> = [];
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
      assetHeaders.push(route.request().headers());
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
  expect(assetHeaders[0]).toMatchObject({
    authorization: 'Bearer playwright-token',
    'x-workspace-id': 'workspace-cloud',
  });
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
test('plugin asset hook replaces and revokes URLs on a same-document Workspace change', async ({
  page,
}) => {
  const first = makeWorkspaceEntry('asset-first', 'First', 'local');
  const second = makeWorkspaceEntry('asset-second', 'Second', 'local');
  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [first],
  });
  const headers: Array<Record<string, string>> = [];
  await page.route(
    '**/api/v1/plugins/test/asset/authenticated-assets/page.html',
    async (route) => {
      headers.push(route.request().headers());
      await route.fulfill({
        contentType: 'text/html',
        body: `<h1>${headers.at(-1)?.['x-workspace-id']}</h1>`,
      });
    },
  );
  await page.goto('/home/bots');
  await expect
    .poll(() =>
      page.evaluate(async () => {
        const path = '/src/app/infra/http/currentWorkspaceStore.ts';
        return (await import(path)).getCurrentWorkspaceSnapshot()?.workspace
          .uuid;
      }),
    )
    .toBe('asset-first');
  await page.evaluate(async () => {
    const resources = performance
      .getEntriesByType('resource')
      .map((entry) => entry.name);
    const reactPath = resources.find((url) =>
      new URL(url).pathname.endsWith('/react.js'),
    )!;
    const domPath = resources.find((url) =>
      new URL(url).pathname.endsWith('/react-dom_client.js'),
    )!;
    const React = (await import(reactPath)).default;
    const domModule = await import(domPath);
    const { createRoot } = domModule.default || domModule;
    const hookPath = '/src/hooks/useAuthenticatedPluginResource.ts';
    const { useAuthenticatedPluginAsset } = await import(hookPath);
    const host = document.createElement('main');
    host.id = 'asset-hook';
    document.getElementById('root')!.style.display = 'none';
    document.body.appendChild(host);
    const revoke = URL.revokeObjectURL.bind(URL);
    URL.revokeObjectURL = (url) => {
      host.dataset.revoked = JSON.stringify([
        ...JSON.parse(host.dataset.revoked || '[]'),
        url,
      ]);
      revoke(url);
    };
    function Resource() {
      const resource = useAuthenticatedPluginAsset(
        'test',
        'asset',
        'page.html',
      );
      return React.createElement(
        'output',
        { 'data-testid': 'asset-url' },
        resource.url,
      );
    }
    function Harness() {
      const [mounted, setMounted] = React.useState(true);
      return React.createElement(
        React.Fragment,
        null,
        mounted && React.createElement(Resource),
        React.createElement(
          'button',
          { onClick: () => setMounted(false) },
          'Unmount resource',
        ),
      );
    }
    createRoot(host).render(React.createElement(Harness));
  });
  const output = page.getByTestId('asset-url');
  await expect(output).toHaveText(/^blob:/);
  const oldURL = await output.textContent();
  await page.evaluate(async (workspace) => {
    const contextPath = '/src/app/infra/http/workspaceContext.ts';
    const storePath = '/src/app/infra/http/currentWorkspaceStore.ts';
    const context = await import(contextPath);
    const store = await import(storePath);
    context.setActiveWorkspaceUuid(workspace.workspace.uuid);
    store.setCurrentWorkspaceSnapshot(workspace);
  }, second);
  await expect(output).toHaveText(/^blob:/);
  await expect(output).not.toHaveText(oldURL!);
  await expect
    .poll(() => headers.map((item) => item['x-workspace-id']))
    .toEqual(['asset-first', 'asset-second']);
  expect(
    headers.every((item) => item.authorization === 'Bearer playwright-token'),
  ).toBe(true);
  const newURL = await output.textContent();
  await expect
    .poll(() => page.locator('#asset-hook').getAttribute('data-revoked'))
    .toBe(JSON.stringify([oldURL]));
  await page.getByRole('button', { name: 'Unmount resource' }).click();
  await expect(output).toHaveCount(0);
  await expect
    .poll(() => page.locator('#asset-hook').getAttribute('data-revoked'))
    .toBe(JSON.stringify([oldURL, newURL]));
});

import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

for (const cleanup of ['close', 'expiry'] as const) {
  test(`QR start, polling and ${cleanup} cleanup retain the session Workspace`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    const calls: Array<{
      method: string;
      origin: string;
      path: string;
      workspace?: string;
      authorization?: string;
    }> = [];
    const endpoint = '/api/v1/platform/adapters/weixin/login';
    await page.route(`**${endpoint}**`, async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      calls.push({
        method: request.method(),
        origin: new URL(request.url()).origin,
        path,
        workspace: request.headers()['x-workspace-id'],
        authorization: request.headers().authorization,
      });
      const data =
        request.method() === 'POST'
          ? {
              session_id: 'qr-session',
              qr_url: 'https://scan.example/qr',
              expire_at: Date.now() / 1000 + 8,
            }
          : { status: 'waiting' };
      await route.fulfill({ json: { code: 0, data } });
    });
    await page.goto('/home/bots');
    await expect(
      page.getByRole('button', { name: 'Models', exact: true }),
    ).toBeVisible();
    const modules = await page.evaluate(() => {
      const resources = performance
        .getEntriesByType('resource')
        .map((entry) => entry.name);
      return {
        reactPath: resources.find((url) =>
          new URL(url).pathname.endsWith('/react.js'),
        )!,
        domPath: resources.find((url) =>
          new URL(url).pathname.endsWith('/react-dom_client.js'),
        )!,
      };
    });
    await page.clock.install();
    await page.evaluate(async ({ reactPath, domPath }) => {
      const reactModule = await import(reactPath);
      const React = reactModule.default || reactModule;
      const domModule = await import(domPath);
      const { createRoot } = domModule.default || domModule;
      const componentPath =
        '/src/app/home/components/qrcode-login/QrCodeLoginDialog.tsx';
      const { default: Dialog } = await import(componentPath);
      const contextPath = '/src/app/infra/http/workspaceContext.ts';
      (await import(contextPath)).setActiveWorkspaceUuid('qr-original');
      const host = document.createElement('div');
      document.body.appendChild(host);
      function Harness() {
        const [open, setOpen] = React.useState(true);
        return React.createElement(Dialog, {
          open,
          onOpenChange: setOpen,
          platform: 'weixin',
          onSuccess: () => {},
        });
      }
      createRoot(host).render(React.createElement(Harness));
    }, modules);
    await expect(page.getByRole('dialog').locator('img')).toBeVisible();
    await page.evaluate(async () => {
      const path = '/src/app/infra/http/workspaceContext.ts';
      (await import(path)).setActiveWorkspaceUuid('qr-other');
    });
    await page.clock.runFor(3100);
    await expect
      .poll(() => calls.some((call) => call.method === 'GET'))
      .toBe(true);
    if (cleanup === 'close') await page.keyboard.press('Escape');
    else await page.clock.runFor(6000);
    await expect
      .poll(() => calls.filter((call) => call.method === 'DELETE').length)
      .toBe(1);
    expect(calls).toEqual([
      {
        method: 'POST',
        origin: new URL(page.url()).origin,
        path: endpoint,
        workspace: 'qr-original',
        authorization: 'Bearer playwright-token',
      },
      ...calls
        .filter((call) => call.method === 'GET')
        .map(() => ({
          method: 'GET',
          origin: new URL(page.url()).origin,
          path: `${endpoint}/status/qr-session`,
          workspace: 'qr-original',
          authorization: 'Bearer playwright-token',
        })),
      {
        method: 'DELETE',
        origin: new URL(page.url()).origin,
        path: `${endpoint}/qr-session`,
        workspace: 'qr-original',
        authorization: 'Bearer playwright-token',
      },
    ]);
  });
}

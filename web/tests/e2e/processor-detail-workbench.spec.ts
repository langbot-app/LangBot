import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

test.describe('processor detail workbench', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('agent keeps debugging left of its orchestration settings', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      withRunnerToolSelector: true,
    });

    await page.goto('/home/agents?id=agent-workbench');

    const debugPanel = page.getByRole('region', { name: 'Debug' });
    const configPanel = page.getByRole('region', { name: 'Configuration' });
    await expect(debugPanel).toBeVisible();
    await expect(configPanel).toBeVisible();
    const debugBox = await debugPanel.boundingBox();
    const configBox = await configPanel.boundingBox();
    expect(debugBox).not.toBeNull();
    expect(configBox).not.toBeNull();
    expect(debugBox!.x).toBeLessThan(configBox!.x);
    expect(configBox!.width).toBeGreaterThan(debugBox!.width);

    const appShell = page.locator('[class*="group/sidebar-wrapper"]');
    const sidebarInset = page.locator('[data-slot="sidebar-inset"]');
    await expect(appShell).toHaveCSS('overflow', 'clip');
    await expect(sidebarInset).toHaveCSS('overflow', 'clip');
    await appShell.evaluate((element) => {
      element.scrollTop = 300;
    });
    await sidebarInset.evaluate((element) => {
      element.scrollTop = 300;
    });
    await expect
      .poll(() => appShell.evaluate((element) => element.scrollTop))
      .toBe(0);
    await expect
      .poll(() => sidebarInset.evaluate((element) => element.scrollTop))
      .toBe(0);
    expect(debugBox!.y).toBeGreaterThanOrEqual(0);

    const flow = configPanel.getByRole('tablist');
    await expect(flow.getByRole('tab').nth(0)).toContainText(
      'Basic Information',
    );
    await expect(flow.getByRole('tab').nth(1)).toContainText(
      'Bindable Event Range',
    );
    await expect(flow.getByRole('tab').nth(2)).toContainText('Runner');
    await expect(flow.getByRole('tab').nth(3)).toContainText('Local Agent');

    await expect(configPanel.getByLabel('Name')).toBeVisible();
    await expect(configPanel.getByLabel('Icon')).toBeVisible();
    await expect(configPanel.getByLabel('Description')).toBeVisible();

    const runnerStatus = page.getByRole('status', { name: 'Runner ready' });
    await expect(runnerStatus).toBeVisible();
    await runnerStatus.hover();
    await expect(
      page.getByText(
        'Local Agent is registered and the plugin runtime is connected.',
      ),
    ).toBeVisible();

    await flow.getByRole('tab').nth(1).click();
    await expect(
      configPanel.getByText('Bindable Event Range', { exact: true }).last(),
    ).toBeVisible();
    await flow.getByRole('tab').nth(3).click();
    await expect(
      configPanel.getByText('Local Agent', { exact: true }).last(),
    ).toBeVisible();
  });

  test('agent saves edits before debugging and shows the real output', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    const requests: string[] = [];
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname;
      if (
        request.method() === 'PUT' &&
        path === '/api/v1/agents/agent-workbench'
      ) {
        requests.push('save');
      }
      if (
        request.method() === 'POST' &&
        path === '/api/v1/agents/agent-workbench/debug'
      ) {
        requests.push('debug');
      }
    });

    await page.goto('/home/agents?id=agent-workbench');
    await page.getByLabel('Description').fill('Updated before debugging');
    await page
      .getByRole('textbox', { name: 'Conversation input' })
      .fill('Hello');
    await page.getByRole('button', { name: 'Save and run' }).click();

    await expect(page.getByText('Mock Agent response')).toBeVisible();
    expect(requests).toEqual(['save', 'debug']);
  });

  test('agent turns runner failures into an actionable message', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    await page.route(
      '**/api/v1/agents/agent-workbench/debug',
      async (route) => {
        await route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 'dify.config_invalid',
            msg: 'api-key is required',
          }),
        });
      },
    );

    await page.goto('/home/agents?id=agent-workbench');
    await page
      .getByRole('textbox', { name: 'Conversation input' })
      .fill('Hello');
    await page.getByRole('button', { name: 'Run test' }).click();

    await expect(
      page.getByText(
        'The runner configuration is incomplete: API Key is missing',
      ),
    ).toBeVisible();
    await expect(page.getByText('Internal server error')).toHaveCount(0);
    await page
      .getByRole('button', { name: 'Review runner configuration' })
      .click();
    await expect(
      page.getByRole('tab', { name: 'Local Agent', exact: true }),
    ).toHaveAttribute('data-state', 'active');
  });

  test('pipeline keeps debug chat left and exposes its main flow first', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    await page.routeWebSocket('**/api/v1/pipelines/**/ws/connect**', (ws) => {
      ws.onMessage((raw) => {
        const message = JSON.parse(String(raw));
        if (message.type === 'authenticate') {
          ws.send(
            JSON.stringify({
              type: 'connected',
              connection_id: 'playwright-connection',
              pipeline_uuid: 'pipeline-workbench',
              session_type: 'person',
            }),
          );
        }
      });
    });

    await page.goto('/home/pipelines?id=pipeline-workbench');

    const debugPanel = page.getByRole('region', { name: 'Debug Chat' });
    const configPanel = page.getByRole('region', { name: 'Configuration' });
    await expect(debugPanel).toBeVisible();
    await expect(configPanel).toBeVisible();
    await expect(
      debugPanel.getByRole('button', { name: 'Private Chat' }),
    ).toBeVisible();
    await expect(
      debugPanel.getByRole('button', { name: 'Group Chat' }),
    ).toBeVisible();
    await debugPanel
      .getByRole('button', { name: 'Reset Conversation' })
      .click();
    await expect(
      page.getByText('Conversation reset successfully'),
    ).toBeVisible();

    const debugBox = await debugPanel.boundingBox();
    const configBox = await configPanel.boundingBox();
    expect(debugBox).not.toBeNull();
    expect(configBox).not.toBeNull();
    expect(debugBox!.x).toBeLessThan(configBox!.x);
    expect(configBox!.width).toBeGreaterThan(debugBox!.width);

    const appShell = page.locator('[class*="group/sidebar-wrapper"]');
    const sidebarInset = page.locator('[data-slot="sidebar-inset"]');
    await expect(appShell).toHaveCSS('overflow', 'clip');
    await expect(sidebarInset).toHaveCSS('overflow', 'clip');
    await expect
      .poll(() => appShell.evaluate((element) => element.scrollTop))
      .toBe(0);
    expect(debugBox!.y).toBeGreaterThanOrEqual(0);

    const flow = configPanel.getByRole('tablist');
    await expect(flow.getByRole('tab').nth(0)).toContainText('Trigger');
    await expect(flow.getByRole('tab').nth(1)).toContainText('AI');
    await expect(flow.getByRole('tab').nth(2)).toContainText('Output');

    await flow.getByRole('tab').nth(1).click();
    await expect(
      configPanel.getByText('Runtime', { exact: true }).last(),
    ).toBeVisible();
  });
});

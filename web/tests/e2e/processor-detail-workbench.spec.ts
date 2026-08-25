import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

test.describe('processor detail workbench', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('agent keeps debugging left of its orchestration settings', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      withAdapterEvents: true,
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
    await expect(flow.getByRole('tab').nth(0)).toContainText('Runner');
    await expect(flow.getByRole('tab').nth(1)).toContainText('Local Agent');
    await expect(flow.getByRole('tab').nth(2)).toContainText(
      'Bindable Event Range',
    );
    await expect(flow.getByRole('tab')).toHaveCount(3);
    await expect(flow.getByText('Management')).toHaveCount(0);

    await page.setViewportSize({ width: 1024, height: 900 });
    const tabListMetrics = await flow.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(tabListMetrics.scrollWidth).toBeLessThanOrEqual(
      tabListMetrics.clientWidth,
    );

    await expect(
      page.getByRole('heading', { name: /agent-workbench/ }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Edit basic information' }),
    ).toBeVisible();
    const saveButton = page.getByRole('button', { name: 'Save' });
    const deleteButton = page.getByRole('button', { name: 'Delete' });
    await expect(saveButton).toBeVisible();
    await expect(deleteButton).toBeVisible();
    const saveBox = await saveButton.boundingBox();
    const deleteBox = await deleteButton.boundingBox();
    expect(saveBox).not.toBeNull();
    expect(deleteBox).not.toBeNull();
    expect(deleteBox!.x).toBeGreaterThan(saveBox!.x);
    await expect(configPanel.getByLabel('Name')).toHaveCount(0);
    await expect(configPanel.getByLabel('Icon')).toHaveCount(0);
    await expect(configPanel.getByLabel('Description')).toHaveCount(0);

    const runnerStatus = page.getByRole('status', { name: 'Runner ready' });
    await expect(runnerStatus).toBeVisible();
    await runnerStatus.hover();
    await expect(
      page
        .getByText(
          'Local Agent is registered and the plugin runtime is connected.',
        )
        .last(),
    ).toBeVisible();

    await flow.getByRole('tab').nth(2).click();
    await expect(
      configPanel.getByText('Bindable Event Range', { exact: true }).last(),
    ).toBeVisible();
    const eventPicker = configPanel.getByRole('combobox', {
      name: 'Event Range',
    });
    await expect(eventPicker).toBeVisible();
    await expect(configPanel.getByRole('textbox')).toHaveCount(0);
    await eventPicker.click();
    await expect(
      page.getByRole('option').filter({ hasText: 'message.received' }),
    ).toBeVisible();
    await expect(page.getByRole('group', { name: 'Messages' })).toHaveCount(1);
    await expect(page.getByRole('group', { name: 'Groups' })).toHaveCount(1);
    await page.keyboard.press('Escape');

    await flow.getByRole('tab').nth(1).click();
    await expect(
      configPanel.getByText('Local Agent', { exact: true }).last(),
    ).toBeVisible();

    await deleteButton.click();
    const deleteDialog = page.getByRole('dialog');
    await expect(deleteDialog).toContainText(
      'Are you sure you want to delete this Agent?',
    );
    await deleteDialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(deleteDialog).toHaveCount(0);
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
    await page.getByRole('button', { name: 'Edit basic information' }).click();
    const basicInfoDialog = page.getByRole('dialog');
    await expect(basicInfoDialog.getByLabel('Icon')).toBeVisible();
    await basicInfoDialog
      .getByLabel('Description')
      .fill('Updated before debugging');
    await basicInfoDialog.getByRole('button', { name: 'Save' }).click();
    await expect(basicInfoDialog).toHaveCount(0);
    await page
      .getByRole('textbox', { name: 'Conversation input' })
      .fill('Hello');
    await page.getByRole('button', { name: 'Run test' }).click();

    await expect(page.getByText('Mock Agent response')).toBeVisible();
    expect(requests).toEqual(['save', 'debug']);
  });

  test('agent deletion is confirmed from the header and returns to the list', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    await page.goto('/home/agents?id=agent-workbench');

    const deleteRequest = page.waitForRequest(
      (request) =>
        request.method() === 'DELETE' &&
        new URL(request.url()).pathname === '/api/v1/agents/agent-workbench',
    );
    await page.getByRole('button', { name: 'Delete' }).click();
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Confirm Delete' })
      .click();

    await deleteRequest;
    await expect(page).toHaveURL(/\/home\/agents$/);
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
    const sessionToolbar = debugPanel.locator(
      '[data-debug-session-toolbar="true"]',
    );
    await expect(sessionToolbar.getByText('Session Type')).toBeVisible();
    const privateChatButton = sessionToolbar.getByRole('button', {
      name: 'Private Chat',
    });
    const groupChatButton = sessionToolbar.getByRole('button', {
      name: 'Group Chat',
    });
    await expect(privateChatButton).toHaveAttribute('aria-pressed', 'true');
    await expect(privateChatButton).toHaveClass(/bg-primary\/15/);
    await expect(privateChatButton).toHaveClass(/text-primary/);
    await expect(groupChatButton).not.toHaveClass(/bg-primary\/15/);
    await groupChatButton.click();
    await expect(groupChatButton).toHaveAttribute('aria-pressed', 'true');
    await expect(groupChatButton).toHaveClass(/bg-primary\/15/);
    await expect(groupChatButton).toHaveClass(/text-primary/);
    await expect(privateChatButton).not.toHaveClass(/bg-primary\/15/);
    await privateChatButton.click();

    const composer = debugPanel.locator('[data-debug-composer="true"]');
    const messageInput = composer.locator('textarea');
    const sendButton = composer.getByRole('button', { name: 'Send' });
    const resetButton = composer.getByRole('button', {
      name: 'Reset Conversation',
    });
    await expect(messageInput).toBeVisible();
    await expect(messageInput).toHaveAttribute('rows', '1');
    await expect(resetButton).toBeVisible();
    const inputBox = await messageInput.boundingBox();
    const sendBox = await sendButton.boundingBox();
    const toolbarBox = await sessionToolbar.boundingBox();
    const emptyStateBox = await debugPanel
      .getByText('No messages', { exact: true })
      .boundingBox();
    expect(inputBox).not.toBeNull();
    expect(sendBox).not.toBeNull();
    expect(toolbarBox).not.toBeNull();
    expect(emptyStateBox).not.toBeNull();
    expect(sendBox!.x).toBeGreaterThan(inputBox!.x + inputBox!.width);
    expect(Math.abs(sendBox!.height - inputBox!.height)).toBeLessThanOrEqual(1);
    expect(Math.abs(sendBox!.y - inputBox!.y)).toBeLessThanOrEqual(1);
    expect(toolbarBox!.y).toBeLessThan(emptyStateBox!.y);

    const streamSwitchBox = await composer.getByRole('switch').boundingBox();
    const resetBox = await resetButton.boundingBox();
    expect(streamSwitchBox).not.toBeNull();
    expect(resetBox).not.toBeNull();
    expect(resetBox!.x).toBeGreaterThan(
      streamSwitchBox!.x + streamSwitchBox!.width,
    );
    expect(
      Math.abs(
        resetBox!.y +
          resetBox!.height / 2 -
          (streamSwitchBox!.y + streamSwitchBox!.height / 2),
      ),
    ).toBeLessThanOrEqual(1);

    await resetButton.click();
    await expect(
      page.getByText('Conversation reset successfully'),
    ).toBeVisible();

    await expect(
      page.getByRole('heading', { name: /pipeline-workbench/ }),
    ).toBeVisible();
    await expect(configPanel.locator('input[name="basic.name"]')).toHaveCount(
      0,
    );
    await page.getByRole('button', { name: 'Edit basic information' }).click();
    const basicInfoDialog = page.getByRole('dialog');
    await expect(basicInfoDialog.getByLabel('Icon')).toBeVisible();
    await basicInfoDialog.getByLabel('Name').fill('Renamed Pipeline');
    await basicInfoDialog
      .getByLabel('Description')
      .fill('Updated from the title dialog.');
    await basicInfoDialog.getByRole('button', { name: 'Save' }).click();
    await expect(
      page.getByRole('heading', { name: /Renamed Pipeline/ }),
    ).toBeVisible();

    const secondaryNavigation = configPanel.locator('nav').getByRole('button');
    await expect(secondaryNavigation.last()).toHaveText('Management');

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

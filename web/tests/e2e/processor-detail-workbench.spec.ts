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
    await expect
      .poll(() => appShell.evaluate((element) => element.scrollTop))
      .toBe(0);
    expect(debugBox!.y).toBeGreaterThanOrEqual(0);

    const flow = configPanel.locator('ol');
    await expect(flow.getByRole('button').nth(0)).toContainText(
      'Basic Information',
    );
    await expect(flow.getByRole('button').nth(1)).toContainText(
      'Bindable Event Range',
    );
    await expect(flow.getByRole('button').nth(2)).toContainText('Runner');
    await expect(flow.getByRole('button').nth(3)).toContainText('Local Agent');

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

    await flow.getByRole('button').nth(1).click();
    await expect(
      configPanel.getByText('Bindable Event Range', { exact: true }).last(),
    ).toBeVisible();
    await flow.getByRole('button').nth(3).click();
    await expect(
      configPanel.getByText('Local Agent', { exact: true }).last(),
    ).toBeVisible();
  });

  test('pipeline keeps debug chat left and exposes its main flow first', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/pipelines?id=pipeline-workbench');

    const debugPanel = page.getByRole('region', { name: 'Debug Chat' });
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
    await expect
      .poll(() => appShell.evaluate((element) => element.scrollTop))
      .toBe(0);
    expect(debugBox!.y).toBeGreaterThanOrEqual(0);

    const flow = configPanel.locator('ol');
    await expect(flow.getByRole('button').nth(0)).toContainText(
      'Trigger Conditions',
    );
    await expect(flow.getByRole('button').nth(1)).toContainText(
      'AI Capabilities',
    );
    await expect(flow.getByRole('button').nth(2)).toContainText(
      'Output Processing',
    );

    await flow.getByRole('button').nth(1).click();
    await expect(
      configPanel.getByText('Runtime', { exact: true }).last(),
    ).toBeVisible();
  });
});

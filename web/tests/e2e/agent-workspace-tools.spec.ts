import { expect, test } from '@playwright/test';
import {
  installLangBotApiMocks,
  pipelineMetadata,
} from './fixtures/langbot-api';

test('workspace tools have a separate tab and retain selection across tabs', async ({
  page,
}, testInfo) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withRunnerToolSelector: true,
  });
  await page.route('**/api/v1/agents/_/metadata', async (route) => {
    await route.fulfill({
      json: {
        code: 0,
        data: {
          runner_config: pipelineMetadata(true).configs[0],
          platform_tools: [],
          host_tools: [],
          workspace_operations: [
            {
              id: 'stats.basic',
              domain: 'stats',
              label: { en_US: 'Workspace statistics' },
              summary: 'Read workspace statistics',
              risk: 'read',
              grantable: true,
            },
          ],
          domains: [{ domain: 'stats', label: { en_US: 'Statistics' } }],
        },
      },
    });
  });
  await page.goto('/home/agents?id=agent-tools');
  await page.getByRole('tab', { name: 'Events & tools', exact: true }).click();
  const workspaceTab = page.getByRole('button', {
    name: /Workspace Operations/,
  });
  const botTab = page.getByRole('button', { name: /Bot tools/ });
  await expect(workspaceTab).toBeVisible();
  await expect(
    page.getByText('Workspace statistics', { exact: true }),
  ).toHaveCount(0);
  await workspaceTab.click();
  await expect(workspaceTab).toHaveAttribute('aria-pressed', 'true');
  await page.getByPlaceholder(/Search operation name/).fill('stats.basic');
  const operation = page.getByText('Workspace statistics', { exact: true });
  await expect(operation).toBeVisible();
  await operation.click();
  await botTab.click();
  await expect(operation).toHaveCount(0);
  await workspaceTab.click();
  await page.getByPlaceholder(/Search operation name/).fill('stats.basic');
  await expect(page.getByRole('checkbox', { checked: true })).not.toHaveCount(
    0,
  );
  await page.screenshot({
    path: testInfo.outputPath('workspace-tools.png'),
    fullPage: true,
  });
});

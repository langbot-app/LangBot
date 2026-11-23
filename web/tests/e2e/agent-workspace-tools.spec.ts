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
          workspace_operation_grants: {
            'langbot-team/LocalAgent': ['stats.basic'],
          },
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

test('workspace selection uses installation grants, not the current member ceiling', async ({
  page,
}, testInfo) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withRunnerToolSelector: true,
  });
  await page.route('**/api/v1/agents/_/metadata', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          runner_config: pipelineMetadata(true).configs[0],
          platform_tools: [],
          host_tools: [],
          workspace_operation_grants: {
            'langbot-team/LocalAgent': ['stats.basic'],
          },
          workspace_operations: [
            {
              id: 'stats.basic',
              domain: 'stats',
              label: { en_US: 'Granted operation' },
              risk: 'read',
              grantable: false,
            },
            {
              id: 'stats.private',
              domain: 'stats',
              label: { en_US: 'Ungranted operation' },
              risk: 'read',
              grantable: true,
            },
          ],
          domains: [{ domain: 'stats', label: { en_US: 'Statistics' } }],
        },
      },
    }),
  );
  await page.goto('/home/agents?id=agent-tools');
  await page.getByRole('tab', { name: 'Events & tools', exact: true }).click();
  await page.getByRole('button', { name: /Workspace Operations/ }).click();
  await page.getByPlaceholder(/Search operation name/).fill('stats.');
  await expect(
    page.getByRole('checkbox', { name: /Granted operation/ }),
  ).toBeEnabled();
  await expect(
    page.getByRole('checkbox', { name: /Ungranted operation/ }),
  ).toBeDisabled();
  await page.getByRole('checkbox', { name: /Granted operation/ }).check();
  await page.getByText('Ungranted operation', { exact: true }).hover();
  await expect(
    page
      .getByRole('tooltip')
      .getByText('Grant this operation in plugin permissions first'),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath('installation-grants.png'),
    fullPage: true,
  });
});

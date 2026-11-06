import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('agent bot tools use collapsible groups with group select-all', async ({
  page,
}, testInfo) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const data = {
    enable_all_plugins: true,
    enable_all_mcp_servers: true,
    enable_all_skills: true,
    bound_plugins: [],
    available_plugins: [],
    bound_mcp_servers: [],
    available_mcp_servers: [],
    bound_skills: [],
    available_skills: [],
    workspace_operations: [],
    available_workspace_operations: [],
    allowed_platform_tools: [],
    available_platform_tools: ['send_message', 'recall_message'].map(
      (name) => ({
        name,
        api: `bot.message.${name}`,
        scope: 'platform',
        category: 'message',
        risk: 'write',
        label: { en_US: name },
        description: { en_US: `${name} description` },
        event_patterns: [],
        parameters: {},
      }),
    ),
  };
  await page.route(
    '**/api/v1/pipelines/pipeline-tools/extensions',
    async (route) => {
      await route.fulfill({ json: { code: 0, data } });
    },
  );
  await page.goto('/home/pipelines?id=pipeline-tools');
  await page.getByRole('button', { name: 'Extensions', exact: true }).click();
  await page.getByRole('button', { name: /Bot tools/ }).click();

  const groupHeader = page.getByRole('button', { name: /Messages.*0 \/ 2/ });
  await expect(groupHeader).toBeVisible();
  await page.getByRole('checkbox', { name: /Messages Select all/ }).check();
  await expect(
    page.getByRole('checkbox', { name: 'send_message' }),
  ).toBeChecked();
  await expect(
    page.getByRole('checkbox', { name: 'recall_message' }),
  ).toBeChecked();
  await expect(
    page.getByRole('button', { name: /Messages.*2 \/ 2/ }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath('bot-tools-grouped.png'),
    fullPage: true,
  });

  await page.getByRole('button', { name: /Messages.*2 \/ 2/ }).click();
  await expect(
    page.getByRole('checkbox', { name: 'send_message' }),
  ).toHaveCount(0);
  await page.screenshot({
    path: testInfo.outputPath('bot-tools-collapsed.png'),
    fullPage: true,
  });
});

test('runner tools dialog groups tools by provider with select-all and search', async ({
  page,
}, testInfo) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withRunnerToolSelector: true,
  });
  await page.goto('/home/agents?id=agent-scope');
  await page.getByRole('tab', { name: /^Runner$/ }).click();
  await page.getByRole('button', { name: 'Edit tools' }).click();

  const dialog = page.getByRole('dialog');
  const header = dialog.getByRole('button', {
    name: /qa\/plugin-smoke.*0 \/ 1/,
  });
  await expect(header).toBeVisible();
  await dialog
    .getByRole('checkbox', { name: /qa\/plugin-smoke Select all/ })
    .check();
  await expect(
    dialog.getByRole('checkbox', { name: 'Select available_plugin_tool' }),
  ).toBeChecked();
  await page.screenshot({
    path: testInfo.outputPath('runner-tools-dialog.png'),
  });

  await dialog
    .getByRole('button', { name: /qa\/plugin-smoke.*1 \/ 1/ })
    .click();
  await expect(dialog.getByText('available_plugin_tool')).toHaveCount(0);
  await dialog.getByPlaceholder('Search tools…').fill('available');
  await expect(dialog.getByText('available_plugin_tool')).toBeVisible();
  await dialog.getByPlaceholder('Search tools…').fill('nothing-matches');
  await expect(dialog.getByText('No matching API or tool')).toBeVisible();
});

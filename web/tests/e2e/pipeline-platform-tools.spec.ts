import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('pipeline saves bot tools together with existing bindings and workspace selection', async ({
  page,
}, testInfo) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const writes: Record<string, unknown>[] = [];
  const plugin = {
    manifest: {
      manifest: {
        metadata: {
          author: 'qa',
          name: 'bound',
          label: { en_US: 'Bound plugin' },
          version: '1.0.0',
        },
        spec: {},
      },
    },
    enabled: true,
    components: [],
  };
  const data = {
    enable_all_plugins: false,
    enable_all_mcp_servers: false,
    enable_all_skills: false,
    bound_plugins: [{ author: 'qa', name: 'bound' }],
    available_plugins: [plugin],
    bound_mcp_servers: ['mcp-kept'],
    available_mcp_servers: [
      { uuid: 'mcp-kept', name: 'Kept MCP', mode: 'http', enable: true },
    ],
    bound_skills: ['skill-kept'],
    available_skills: [{ name: 'skill-kept', display_name: 'Kept skill' }],
    workspace_operations: ['stats.basic'],
    available_workspace_operations: [
      {
        id: 'stats.basic',
        domain: 'stats',
        label: { en_US: 'Statistics' },
        risk: 'read',
        grantable: true,
      },
    ],
    allowed_platform_tools: [],
    available_platform_tools: [
      {
        name: 'send_message',
        api: 'bot.message.send',
        scope: 'platform',
        category: 'message',
        risk: 'write',
        label: { en_US: 'Send bot message' },
        description: { en_US: 'Send a message using a bot' },
        event_patterns: [],
        parameters: {},
      },
    ],
  };
  await page.route(
    '**/api/v1/pipelines/pipeline-tools/extensions',
    async (route) => {
      if (route.request().method() === 'PUT') {
        writes.push(route.request().postDataJSON());
        Object.assign(data, route.request().postDataJSON());
      }
      await route.fulfill({ json: { code: 0, data } });
    },
  );
  await page.goto('/home/pipelines?id=pipeline-tools');
  await page.getByRole('button', { name: 'Extensions', exact: true }).click();
  await page.getByRole('button', { name: /Bot tools/ }).click();
  await page.getByRole('checkbox', { name: /Send bot message/ }).check();
  await page.getByRole('button', { name: /Save Workspace Operations/ }).click();
  const dialog = page.getByRole('alertdialog');
  await expect(dialog).toBeVisible();
  expect(writes).toHaveLength(0);
  await dialog.getByRole('button', { name: /Confirm/ }).click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toMatchObject({
    allowed_platform_tools: ['send_message'],
    workspace_operations: ['stats.basic'],
    bound_plugins: [{ author: 'qa', name: 'bound' }],
    bound_mcp_servers: ['mcp-kept'],
    bound_skills: ['skill-kept'],
    enable_all_plugins: false,
  });
  await page.reload();
  await page.getByRole('button', { name: 'Extensions', exact: true }).click();
  await page.getByRole('button', { name: /Bot tools/ }).click();
  await expect(
    page.getByRole('checkbox', { name: /Send bot message/ }),
  ).toBeChecked();
  await page.screenshot({
    path: testInfo.outputPath('pipeline-bot-tools-saved.png'),
    fullPage: true,
  });
});

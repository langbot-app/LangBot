import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

function ok(data: unknown) {
  return {
    code: 0,
    message: 'ok',
    data,
    timestamp: Date.now(),
  };
}

test('shows an actionable OAuth-required state after a transient MCP test', async ({
  page,
}, testInfo) => {
  await installLangBotApiMocks(page, { authenticated: true });

  await page.route('**/api/v1/mcp/servers/_/test', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(ok({ task_id: 2363 })),
    });
  });
  await page.route('**/api/v1/system/tasks/2363', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        ok({
          runtime: {
            done: true,
            exception: 'Connection failed',
            state: 'error',
          },
          task_context: {
            current_action: 'Testing MCP server',
            log: '',
            metadata: {
              runtime_info: {
                status: 'error',
                error_phase: 'oauth_required',
                retry_count: 1,
                tool_count: 0,
                tools: [],
                resource_count: 0,
                resources: [],
              },
            },
          },
        }),
      ),
    });
  });

  await page.goto('/home/mcp?id=new');
  await page.locator('input[name="name"]').fill('oauth-protected-mcp');
  await page
    .locator('input[name="url"]')
    .fill('https://mcp.example.test/protected');
  await page.getByRole('button', { name: /^Test$/ }).click();

  await expect(page.getByText('OAuth authorization required')).toBeVisible();
  await expect(
    page.getByText(
      'This MCP server requires OAuth sign-in. OAuth sign-in is not available yet; add an Authorization header manually if the server supports it.',
    ),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath('oauth-required.png'),
    fullPage: true,
  });
});

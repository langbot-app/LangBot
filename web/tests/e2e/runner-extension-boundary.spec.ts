import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('independent Runner guidance remains visible with extensions disabled', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.route('**/api/v1/pipelines/*/extensions', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          enable_all_plugins: false,
          enable_all_mcp_servers: false,
          enable_all_skills: false,
          bound_plugins: [],
          available_plugins: [],
          bound_mcp_servers: [],
          available_mcp_servers: [],
          bound_skills: [],
          available_skills: [],
        },
      },
    }),
  );
  await page.goto('/home/pipelines?id=boundary');
  await page.getByRole('tab', { name: 'AI', exact: true }).click();
  await expect(
    page.getByText(
      'Select the Runner independently here, regardless of extension plugin switches. Its plugin must still be installed and available.',
    ),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Extensions', exact: true }).click();
  await expect(
    page.getByText(
      'Only controls event listeners, tools and commands for this pipeline; does not affect the Runner selected in AI settings.',
    ),
  ).toBeVisible();
});

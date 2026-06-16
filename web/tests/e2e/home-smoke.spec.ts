import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

const appRoutes = [
  {
    path: '/home/bots',
    heading: 'Bots',
    bodyText: 'Select a bot from the sidebar',
  },
  {
    path: '/home/pipelines',
    heading: 'Pipelines',
    bodyText: 'Select a pipeline from the sidebar',
  },
  {
    path: '/home/extensions',
    heading: 'Extensions',
    bodyText: 'No extensions installed',
  },
  {
    path: '/home/mcp',
    heading: 'MCP',
    bodyText: 'Select an MCP server from the sidebar',
  },
  {
    path: '/home/knowledge',
    heading: 'Knowledge',
    bodyText: 'Select a knowledge base from the sidebar',
  },
];

test.describe('authenticated app shell', () => {
  for (const route of appRoutes) {
    test(`${route.path} renders without a backend process`, async ({
      page,
    }) => {
      await installLangBotApiMocks(page, { authenticated: true });

      await page.goto(route.path);

      await expect(page).toHaveURL(new RegExp(`${route.path}$`));
      await expect(page.getByText('Home').first()).toBeVisible();
      await expect(
        page.getByRole('button', { name: 'Dashboard' }),
      ).toBeVisible();
      await expect(page.getByText('Extensions').first()).toBeVisible();
      await expect(page.getByText(route.heading).first()).toBeVisible();
      await expect(page.getByText(route.bodyText)).toBeVisible();
      await expect(page.getByText('Backend unavailable')).toHaveCount(0);
    });
  }

  test('/home/monitoring loads dashboard data from mocked APIs', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/monitoring');

    await expect(page).toHaveURL(/\/home\/monitoring$/);
    await expect(page.getByText('Total Messages').first()).toBeVisible();
    await expect(
      page.getByRole('tab', { name: 'Message Records' }),
    ).toBeVisible();
    await expect(
      page.getByRole('tab', { name: 'Token Monitoring' }),
    ).toBeVisible();

    await page.getByRole('tab', { name: 'Token Monitoring' }).click();
    await expect(
      page.getByText('No token usage in the selected time range'),
    ).toBeVisible();
    await expect(page.getByText('Unable to connect to server')).toHaveCount(0);
  });

  test('/home/extensions shows plugin debug information from the backend', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/extensions');

    await page.getByRole('button', { name: 'Debug Info' }).click();

    await expect(page.getByText('Plugin Debug Information')).toBeVisible();
    await expect(page.getByRole('textbox').nth(0)).toHaveValue(
      'ws://127.0.0.1:5300/plugin/debug',
    );
    await expect(page.getByRole('textbox').nth(1)).toHaveValue(
      'test-debug-key',
    );
  });

  test('/home/skills?action=create creates a manual skill', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    await page.goto('/home/skills?action=create');

    await expect(page).toHaveURL(/\/home\/skills\?action=create$/);
    await expect(page.getByText('Create Skill').first()).toBeVisible();
    await expect(page.getByText('Import Local Skill Directory')).toBeVisible();

    const saveButton = page.getByRole('button', { name: 'Save' });
    await expect(saveButton).toBeEnabled();
    await saveButton.click();
    await expect(page.getByText('Skill name cannot be empty')).toBeVisible();

    await page.locator('#display_name').fill('Daily Summary');
    await page.locator('#name').fill('daily_summary');
    await page
      .locator('#description')
      .fill('Summarizes the current conversation for handoff.');
    await page
      .locator('#instructions')
      .fill('Summarize the conversation in five concise bullet points.');
    await saveButton.click();

    await expect(page).toHaveURL(/\/home\/skills\?id=daily_summary$/);
    await expect(
      page.getByRole('heading', { name: 'Daily Summary' }),
    ).toBeVisible();
    await expect(page.locator('#name')).toHaveValue('daily_summary');
    await expect(page.locator('#description')).toHaveValue(
      'Summarizes the current conversation for handoff.',
    );
    await expect(page.locator('#instructions')).toHaveValue(
      'Summarize the conversation in five concise bullet points.',
    );
  });
});

import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('event data stays in sync across the compact form, JSON and the request', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAdapterEvents: true,
  });
  await page.route(
    '**/api/v1/agents/agent-workbench/debug/stream',
    async (route) => {
      await route.fulfill({
        contentType: 'application/x-ndjson',
        body:
          JSON.stringify({ kind: 'completed', data: { final_text: 'Done' } }) +
          '\n',
      });
    },
  );
  await page.goto('/home/agents?id=agent-workbench');
  const panel = page.getByRole('region', { name: 'Event Debug' });
  await panel
    .getByRole('textbox', { name: 'Message content', exact: true })
    .fill('Hello Alice');
  await panel.getByRole('button', { name: 'Full JSON' }).click();
  const json = panel.getByRole('textbox', { name: 'Full JSON' });
  expect(JSON.parse(await json.inputValue()).text).toBe('Hello Alice');
  await json.fill('{');
  await expect(panel.getByRole('button', { name: 'Run test' })).toBeDisabled();
  await expect(panel.getByRole('alert').last()).toContainText('valid JSON');
  await json.fill(
    JSON.stringify({
      text: 'Edited in JSON',
      user_name: 'Alice',
      extra: { keep: true },
    }),
  );
  await panel.getByRole('button', { name: 'Common fields' }).click();
  await expect(
    panel.getByRole('textbox', { name: 'Message content', exact: true }),
  ).toHaveValue('Edited in JSON');
  await panel.getByRole('textbox', { name: 'User name' }).fill('Bob');
  await panel.getByRole('button', { name: 'Full JSON' }).click();
  expect(JSON.parse(await json.inputValue())).toMatchObject({
    user_name: 'Bob',
    extra: { keep: true },
  });

  await panel.getByRole('combobox', { name: 'Event type' }).click();
  await page
    .getByRole('option')
    .filter({ hasText: 'group.member_joined' })
    .click();
  await expect(
    panel.getByRole('textbox', { name: 'Message content', exact: true }),
  ).toHaveCount(0);
  await expect(
    panel.getByRole('textbox', { name: 'Event summary' }),
  ).toHaveCount(0);
  await panel.getByRole('textbox', { name: 'Member name' }).fill('Carol');
  await panel.getByRole('textbox', { name: 'Member ID' }).fill('member-42');
  await panel.getByRole('textbox', { name: 'Group ID' }).fill('group-42');
  const request = page.waitForRequest(
    (req) => req.method() === 'POST' && req.url().endsWith('/debug/stream'),
  );
  await panel.getByRole('button', { name: 'Run test' }).click();
  expect((await request).postDataJSON()).toMatchObject({
    event_type: 'group.member_joined',
    text: '',
    data: {
      member_name: 'Carol',
      member_id: 'member-42',
      group_id: 'group-42',
    },
  });
  await expect(panel.getByText('Done', { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 650 });
  await panel.getByRole('button', { name: 'Full JSON' }).click();
  await panel.locator('summary').filter({ hasText: 'Mock scenario' }).click();
  await expect(
    panel.getByRole('button', { name: 'Run test' }),
  ).toBeInViewport();

  await panel.getByRole('combobox', { name: 'Event type' }).click();
  await page.getByRole('option').filter({ hasText: 'Custom event' }).click();
  await expect(panel.getByRole('textbox', { name: 'Full JSON' })).toBeVisible();
  await expect(
    panel.getByRole('button', { name: 'Common fields' }),
  ).toHaveCount(0);
});

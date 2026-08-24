import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

test('an OSS local-only owner is prompted to bind before using LangBot Models', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.route('**/api/v1/user/space-credits', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        data: {
          credits: null,
          owner_space_bound: false,
          is_workspace_owner: true,
        },
        msg: 'ok',
      }),
    }),
  );
  await page.route('**/api/v1/provider/providers', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        data: {
          providers: [
            {
              uuid: 'langbot-models-provider',
              name: 'LangBot Models',
              requester: 'space-chat-completions',
              base_url: '',
              api_keys: [],
            },
          ],
        },
        msg: 'ok',
      }),
    }),
  );
  await page.route('**/api/v1/provider/requesters**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ code: 0, data: { requesters: [] }, msg: 'ok' }),
    }),
  );
  await page.route('**/api/v1/provider/models/**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ code: 0, data: { models: [] }, msg: 'ok' }),
    }),
  );

  await page.goto('/home?action=showModelSettings');

  await expect(
    page.getByRole('button', {
      name: 'The Workspace owner must connect a LangBot Account for LangBot Models.',
    }),
  ).toBeVisible();
});

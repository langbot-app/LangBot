import { expect, test } from '@playwright/test';
import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

for (const role of ['owner', 'viewer'] as const) {
  for (const bound of [false, true]) {
    test(`LangBot Models uses Workspace billing for ${role}, owner bound=${bound}`, async ({
      page,
    }) => {
      const workspace = makeWorkspaceEntry(
        'billing-workspace',
        'Billing Workspace',
        'local',
      );
      workspace.membership.role = role;
      await installLangBotApiMocks(page, {
        authenticated: true,
        workspaces: [workspace],
      });
      const billingHeaders: Array<Record<string, string>> = [];
      await page.route('**/api/v1/user/space-credits', async (route) => {
        billingHeaders.push(route.request().headers());
        await route.fulfill({
          json: {
            code: 0,
            data: {
              credits: bound ? 12500 : null,
              owner_space_bound: bound,
              is_workspace_owner: role === 'owner',
            },
          },
        });
      });
      await page.route('**/api/v1/provider/providers', (route) =>
        route.fulfill({
          json: {
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
          },
        }),
      );
      await page.route('**/api/v1/provider/requesters**', (route) =>
        route.fulfill({ json: { code: 0, data: { requesters: [] } } }),
      );
      await page.route('**/api/v1/provider/models/**', (route) =>
        route.fulfill({ json: { code: 0, data: { models: [] } } }),
      );
      await page.goto('/home?action=showModelSettings');
      await expect.poll(() => billingHeaders.length).toBeGreaterThan(0);
      expect(billingHeaders[0]).toMatchObject({
        authorization: 'Bearer playwright-token',
        'x-workspace-id': 'billing-workspace',
      });
      const dialog = page.getByRole('dialog');
      await expect(
        dialog.getByText(
          'The Workspace owner must connect a LangBot Account for LangBot Models.',
          { exact: true },
        ),
      ).toHaveCount(bound ? 0 : 1);
      await expect(
        dialog.getByRole('button', {
          name: 'Login with LangBot Account',
          exact: true,
        }),
      ).toHaveCount(role === 'owner' && !bound ? 1 : 0);
      await expect(
        dialog.getByText('2.50 Credits', { exact: true }),
      ).toHaveCount(bound ? 1 : 0);
      if (bound) {
        await expect(
          dialog
            .getByText('2.50 Credits', { exact: true })
            .locator('..')
            .getByRole('button'),
        ).toHaveCount(role === 'owner' ? 1 : 0);
      }
      await expect(
        dialog.getByText(
          "Uses the Workspace owner's LangBot Account billing and credits.",
          { exact: true },
        ),
      ).toHaveCount(role === 'viewer' && bound ? 1 : 0);
    });
  }
}

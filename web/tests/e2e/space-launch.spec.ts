import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

for (const fragment of [true, false]) {
  test(`direct launch assertion is fragment-only and cleared before exchange, fragment=${fragment}`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page);
    await page.addInitScript(() => {
      const replace = history.replaceState.bind(history);
      history.replaceState = (...args) => {
        sessionStorage.setItem('last-replaced-url', String(args[2]));
        replace(...args);
      };
    });
    let body: unknown;
    let fragmentAtExchange: string | null = null;
    await page.route('**/api/v1/user/space/callback', async (route) => {
      body = route.request().postDataJSON();
      fragmentAtExchange = await page.evaluate(() => location.hash);
      await route.fulfill({
        status: 403,
        json: { code: 'launch_denied', msg: 'Denied for test' },
      });
    });
    const query = '/auth/space/callback?code=launch-code&state=launch-state';
    await page.goto(
      fragment
        ? `${query}#workspace_uuid=target-workspace&launch_assertion=fragment-secret`
        : `${query}&workspace_uuid=target-workspace&launch_assertion=query-must-not-be-used`,
    );
    await expect(
      page.getByRole('button', { name: 'Back to Login', exact: true }),
    ).toBeVisible();
    if (fragment) {
      expect(body).toEqual({
        code: 'launch-code',
        state: 'launch-state',
        redirect_uri: new URL('/auth/space/callback', page.url()).href,
        workspace_uuid: 'target-workspace',
        launch_assertion: 'fragment-secret',
      });
      expect(fragmentAtExchange).toBe('');
    } else {
      expect(body).toBeUndefined();
      expect(fragmentAtExchange).toBeNull();
    }
    if (fragment)
      expect(
        await page.evaluate(() => sessionStorage.getItem('last-replaced-url')),
      ).toBe(query);
  });
}

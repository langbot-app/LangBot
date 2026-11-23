import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

const requestUrl =
  'https://github.com/langbot-app/LangBot/issues/new?template=plugin-request.yml';

for (const populated of [false, true]) {
  test(`official plugin request uses Core repository (${populated ? 'populated' : 'empty'} catalog)`, async ({
    page,
  }, testInfo) => {
    await installLangBotApiMocks(page, { authenticated: true });
    await page.route('**/api/v1/marketplace/extensions/search', (route) =>
      route.fulfill({
        json: {
          code: 0,
          data: {
            total: populated ? 1 : 0,
            extensions: populated
              ? [
                  {
                    author: 'qa',
                    name: 'source-index',
                    label: { en_US: 'Official source index fixture' },
                    description: { en_US: 'Local test fixture' },
                    latest_version: '1.0.0',
                    type: 'plugin',
                    status: 'live',
                    tags: [],
                    components: {},
                    install_count: 0,
                    like_count: 0,
                    hot_score: 0,
                  },
                ]
              : [],
          },
        },
      }),
    );
    await page.route('**/api/v1/marketplace/extensions/likes/status', (route) =>
      route.fulfill({ json: { code: 0, data: { extensions: [] } } }),
    );
    await page.goto('/home/add-extension');
    const request = page.locator(`a[href="${requestUrl}"]`);
    await expect(request).toBeVisible();
    await expect(request).toHaveAttribute('target', '_blank');
    await expect(request).toHaveAttribute('rel', 'noopener noreferrer');
    await expect(page.locator('a[href*="langbot-plugin-demo"]')).toHaveCount(0);
    await page.screenshot({
      path: testInfo.outputPath('official-plugin-source.png'),
      fullPage: true,
    });
  });
}

import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

for (const width of [375, 430]) {
  test(`dashboard filters fit mobile ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 });
    await installLangBotApiMocks(page, { authenticated: true });
    await page.goto('/home/monitoring');
    const bot = page.getByRole('combobox', { name: 'Bot', exact: true });
    await expect(bot).toBeVisible();
    const grid = bot.locator('..').locator('..');
    expect(
      await grid.evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(' ').length,
      ),
    ).toBe(2);
    const box = await grid.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    await expect(
      page.getByRole('button', { name: /Reset Filters/i }),
    ).toBeVisible();
    await page.screenshot({
      path: `test-results/dashboard-${width}.png`,
      fullPage: true,
    });
  });
}

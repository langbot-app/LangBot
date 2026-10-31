import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

const guideSteps = [
  'Review activity',
  'Connect chat platforms',
  'Configure processors',
  'Manage knowledge bases',
  'Manage installed extensions',
  'Add extensions',
  'Configure models',
  'Configure API access',
];

test('sidebar guide blocks background navigation until completed', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    storage: { langbot_sidebar_guide_v1: '0' },
  });

  await page.goto('/home/monitoring');

  const guide = page.getByTestId('sidebar-guide');
  await expect(guide).toHaveCount(1);
  await expect(guide.getByRole('dialog')).toBeVisible();
  await expect(guide.getByText('Step 1 of 8')).toBeVisible();
  await expect(guide.getByRole('button', { name: 'Previous' })).toHaveCount(0);
  const highlight = await page
    .getByTestId('sidebar-guide-highlight')
    .elementHandle();
  await guide.getByRole('button', { name: 'Next' }).click();
  await expect(guide.getByText('Step 2 of 8')).toBeVisible();
  expect(await highlight!.evaluate((element) => element.isConnected)).toBe(
    true,
  );
  await expect
    .poll(async () => {
      const rect = await page
        .getByTestId('sidebar-guide-highlight')
        .boundingBox();
      const target = await page
        .locator('[data-sidebar-guide="bots"]')
        .boundingBox();
      return Math.abs(rect!.y - target!.y);
    })
    .toBeLessThan(1);

  await guide.getByRole('button', { name: 'Next' }).focus();
  await page.keyboard.press('Shift+Tab');
  await expect(guide.getByRole('button', { name: 'Previous' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(guide.getByText('Step 1 of 8')).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem('langbot_sidebar_guide_v1')),
    )
    .toBe('0');

  const dashboardTarget = page.locator('[data-sidebar-guide="monitoring"]');
  const targetBox = await dashboardTarget.boundingBox();
  expect(targetBox).not.toBeNull();
  const elementAtTargetCenter = await page.evaluate(
    ({ x, y }) => {
      const element = document.elementFromPoint(x, y);
      return element?.closest('[data-testid="sidebar-guide"]') !== null;
    },
    {
      x: targetBox!.x + targetBox!.width / 2,
      y: targetBox!.y + targetBox!.height / 2,
    },
  );
  expect(elementAtTargetCenter).toBe(true);

  for (const [index, title] of guideSteps.entries()) {
    await expect(
      guide.getByRole('heading', { name: title, exact: true }),
    ).toBeVisible();

    if (index === guideSteps.length - 1) {
      await guide.getByRole('button', { name: 'Previous' }).click();
      await expect(
        guide.getByRole('heading', {
          name: 'Configure models',
          exact: true,
        }),
      ).toBeVisible();
      await guide.getByRole('button', { name: 'Next' }).click();
      await expect(
        guide.getByRole('heading', { name: title, exact: true }),
      ).toBeVisible();
    }

    const buttonName = index === guideSteps.length - 1 ? 'Finish' : 'Next';
    await guide.getByRole('button', { name: buttonName }).click();
  }

  await expect(guide).toHaveCount(0);
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem('langbot_sidebar_guide_v1')),
    )
    .toBe('completed');

  await page.getByRole('button', { name: 'Add Extension' }).click();
  await expect(page).toHaveURL(/\/home\/add-extension$/);

  await page.reload();
  await expect(guide).toHaveCount(0);
});

test('sidebar guide popover stays inside a narrow viewport', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 760 });
  await installLangBotApiMocks(page, {
    authenticated: true,
    storage: { langbot_sidebar_guide_v1: '0' },
  });

  await page.goto('/home/monitoring');

  const dialog = page.getByRole('dialog', { name: 'Review activity' });
  await expect(dialog).toBeVisible();
  const dialogBox = await dialog.boundingBox();
  expect(dialogBox).not.toBeNull();
  expect(dialogBox!.x).toBeGreaterThanOrEqual(0);
  expect(dialogBox!.y).toBeGreaterThanOrEqual(0);
  expect(dialogBox!.x + dialogBox!.width).toBeLessThanOrEqual(390);
  expect(dialogBox!.y + dialogBox!.height).toBeLessThanOrEqual(760);
});

test('sidebar guide supports the shared skip and Escape controls', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    storage: { langbot_sidebar_guide_v1: '0' },
  });
  await page.goto('/home/monitoring');
  const guide = page.getByTestId('sidebar-guide');
  await expect(guide.getByRole('button', { name: 'Skip' })).toBeVisible();
  await expect(guide.getByRole('button', { name: 'Next' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(guide).toHaveCount(0);
  await expect
    .poll(() => page.evaluate(() => document.body.style.overflow))
    .not.toBe('hidden');
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem('langbot_sidebar_guide_v1')),
    )
    .toBe('completed');
});

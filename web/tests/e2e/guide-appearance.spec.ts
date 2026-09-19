import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('sidebar introduction takes priority without losing the page guide step', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    storage: {
      langbot_sidebar_guide_v1: '0',
      langbot_pipeline_setup_guide_v1: 'trigger',
    },
  });
  await page.goto('/home/agents?id=pipeline-guide');
  const sidebar = page.getByTestId('sidebar-guide');
  const contextual = page.getByTestId('pipeline-setup-guide');
  await expect(sidebar.getByRole('dialog')).toBeVisible();
  await expect(contextual).toHaveCount(1);
  await expect(contextual).toBeHidden();
  await sidebar.getByRole('button', { name: 'Skip' }).click();
  await expect(sidebar).toHaveCount(0);
  await expect(contextual.getByRole('dialog')).toBeVisible();
  await expect(contextual).toHaveAttribute('data-active-step', 'trigger');
  await contextual.getByRole('button', { name: 'Next' }).click();
  await expect(contextual).not.toHaveAttribute('data-active-step', 'trigger');
});

for (const theme of ['light', 'dark']) {
  for (const sidebar of [false, true]) {
    test(`${sidebar ? 'sidebar' : 'contextual'} guide keeps its highlight ring and backdrop in ${theme} mode`, async ({
      page,
    }, testInfo) => {
      await installLangBotApiMocks(page, {
        authenticated: true,
        storage: {
          'langbot-theme': theme,
          ...(sidebar
            ? { langbot_sidebar_guide_v1: '0' }
            : { langbot_pipeline_setup_guide_v1: 'trigger' }),
        },
      });
      await page.goto(
        sidebar ? '/home/monitoring' : '/home/agents?id=pipeline-guide',
      );
      const id = sidebar ? 'sidebar-guide' : 'pipeline-setup-guide';
      const guide = page.getByTestId(id);
      await expect(guide.getByRole('dialog')).toBeVisible();
      await expect(page.locator('html')).toHaveClass(theme);
      const highlight = page.getByTestId(`${id}-highlight`);
      const appearance = await highlight.evaluate((element) => {
        const style = getComputedStyle(element);
        const probe = document.createElement('span');
        probe.style.color = style.getPropertyValue('--tw-ring-color');
        element.append(probe);
        const ring = getComputedStyle(probe).color;
        probe.remove();
        return { shadow: style.boxShadow, ring };
      });
      // A standalone backdrop shadow used to override Tailwind's ring shadows.
      expect(appearance.ring).not.toBe('');
      expect(appearance.shadow).toContain(appearance.ring);
      expect(appearance.shadow).toContain('9999px');
      if (theme === 'dark') {
        expect(appearance.shadow).toContain('rgba(0, 0, 0, 0.72)');
      }
      await guide.getByRole('dialog').evaluate(async (element) => {
        await Promise.all(
          element.getAnimations().map((animation) => animation.finished),
        );
      });
      await page.screenshot({ path: testInfo.outputPath('guide.png') });
    });
  }
}

for (const [language, label] of [
  ['en-US', 'User guide'],
  ['zh-Hans', '使用指引'],
  ['zh-Hant', '使用指引'],
  ['ja-JP', '使い方ガイド'],
  ['es-ES', 'Guía de uso'],
  ['ru-RU', 'Руководство'],
  ['th-TH', 'คำแนะนำการใช้งาน'],
  ['vi-VN', 'Hướng dẫn sử dụng'],
]) {
  test(`shared guide controls fit a narrow viewport in ${language}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 600 });
    await installLangBotApiMocks(page, {
      authenticated: true,
      language,
      storage: { langbot_sidebar_guide_v1: '1', 'langbot-theme': 'dark' },
    });
    await page.goto('/home/monitoring');
    const guide = page.getByTestId('sidebar-guide');
    const dialog = guide.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(guide.getByText(label, { exact: true })).toBeVisible();
    await expect(
      guide.locator('[data-guided-tour-action="previous"]'),
    ).toBeVisible();
    await expect(
      guide.locator('[data-guided-tour-action="next"]'),
    ).toBeFocused();
    const box = await dialog.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
    expect(box!.y + box!.height).toBeLessThanOrEqual(600);
    expect(
      await dialog.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
    await guide.locator('[data-guided-tour-action="skip"]').click();
    await expect(guide).toHaveCount(0);
  });
}

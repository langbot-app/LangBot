import { mkdirSync, writeFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

// UI fixtures only: never authenticate or write a real provider.
test.use({ hasTouch: true });
for (const width of [1280, 390, 320]) {
  test(`provider dropdown bounded without dialog growth (${width}px)`, async ({
    page,
  }, testInfo) => {
    await installLangBotApiMocks(page, { authenticated: true });
    await page.route('**/api/v1/provider/**', async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/icon'))
        return route.fulfill({
          contentType: 'image/svg+xml',
          body: '<svg xmlns="http://www.w3.org/2000/svg"/>',
        });
      const data = path.endsWith('/requesters')
        ? {
            requesters: Array.from({ length: 30 }, (_, i) => ({
              name: i === 0 ? 'openai-codex' : `provider-${i}`,
              label: { en_US: i === 0 ? 'OpenAI Codex' : `Provider ${i}` },
              description: { en_US: '' },
              spec: {
                provider_category: 'manufacturer',
                config: [],
                support_type: ['llm'],
              },
            })),
          }
        : { providers: [], models: [] };
      await route.fulfill({ json: { code: 0, data } });
    });
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/home/bots');
    await page.getByRole('button', { name: 'Models', exact: true }).click();
    await page
      .getByRole('button', { name: 'Add Provider', exact: true })
      .click();
    await page.setViewportSize({ width, height: 720 });
    const trigger = page.getByRole('button', {
      name: 'Select Provider Type',
      exact: true,
    });
    const dialog = page
      .locator('[role="dialog"]')
      .filter({ has: page.locator('input[name="name"]') });
    await trigger.scrollIntoViewIfNeeded();
    const before = await dialog.evaluate((el) => ({
      height: el.clientHeight,
      scroll: el.scrollHeight,
    }));
    await trigger.click();
    const search = page.getByPlaceholder('Search providers...');
    await expect(search).toBeFocused();
    const menu = search.locator('../..');
    await expect(
      page.getByRole('button', { name: 'Provider 29', exact: false }),
    ).toBeAttached();
    await menu.evaluate(async (el) => {
      await Promise.all(el.getAnimations().map((a) => a.finished));
    });
    const options = menu.locator(':scope > div').last();
    await options.hover();
    await page.mouse.wheel(0, 1200);
    await expect
      .poll(() => options.evaluate((el) => el.scrollTop))
      .toBeGreaterThan(0);
    if (width < 1280) {
      await page.mouse.wheel(0, -1200);
      await expect.poll(() => options.evaluate((el) => el.scrollTop)).toBe(0);
      const box = (await options.boundingBox())!;
      const session = await page.context().newCDPSession(page);
      const x = box.x + box.width / 2;
      const y = box.y + box.height - 30;
      await session.send('Input.dispatchTouchEvent', {
        type: 'touchStart',
        touchPoints: [{ x, y }],
      });
      for (let step = 1; step <= 10; step++) {
        await session.send('Input.dispatchTouchEvent', {
          type: 'touchMove',
          touchPoints: [{ x, y: y - step * 18 }],
        });
      }
      await session.send('Input.dispatchTouchEvent', {
        type: 'touchEnd',
        touchPoints: [],
      });
      await session.detach();
      await expect
        .poll(() => options.evaluate((el) => el.scrollTop))
        .toBeGreaterThan(0);
    }
    const geometry = await menu.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      const list = el.lastElementChild as HTMLElement;
      const clipped: string[] = [];
      for (
        let parent = el.parentElement;
        parent;
        parent = parent.parentElement
      ) {
        const bounds = parent.getBoundingClientRect();
        if (
          /(auto|scroll|hidden|clip)/.test(
            getComputedStyle(parent).overflowY,
          ) &&
          (rect.bottom > bounds.bottom + 1 || rect.top < bounds.top - 1)
        )
          clipped.push(parent.tagName);
      }
      return {
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
        clipped,
        listHeight: list.clientHeight,
        listScroll: list.scrollHeight,
        scrollTop: list.scrollTop,
        documentWidth: document.documentElement.scrollWidth,
      };
    });
    const after = await dialog.evaluate((el) => ({
      height: el.clientHeight,
      scroll: el.scrollHeight,
    }));
    const dir = process.env.DROPDOWN_EVIDENCE_DIR || testInfo.outputDir;
    mkdirSync(dir, { recursive: true });
    await page.screenshot({
      path: `${dir}/dropdown-${width}.png`,
      fullPage: true,
    });
    writeFileSync(
      `${dir}/dropdown-${width}.json`,
      JSON.stringify(
        { evidence: 'UI fixture only', width, before, after, geometry },
        null,
        2,
      ),
    );
    expect.soft(after).toEqual(before);
    expect.soft(geometry.clipped).toEqual([]);
    expect.soft(geometry.left).toBeGreaterThanOrEqual(0);
    expect.soft(geometry.right).toBeLessThanOrEqual(width);
    expect.soft(geometry.top).toBeGreaterThanOrEqual(0);
    expect.soft(geometry.bottom).toBeLessThanOrEqual(720);
    expect.soft(geometry.documentWidth).toBeLessThanOrEqual(width);
    expect(geometry.listScroll).toBeGreaterThan(geometry.listHeight);
    expect(geometry.scrollTop).toBeGreaterThan(0);
    await page.keyboard.press('Escape');
    await expect(search).toBeHidden();
    await expect(dialog).toBeVisible();
    await expect(trigger).toBeFocused();
    await trigger.click();
    await search.fill('Provider 29');
    await page.locator('input[name="name"]').click();
    await expect(search).toBeHidden();
    await expect(page.locator('input[name="name"]')).toBeFocused();
    await trigger.click();
    await expect(search).toHaveValue('');
    await search.fill('Codex');
    await page
      .getByRole('button', { name: 'OpenAI Codex', exact: false })
      .click();
    await expect(search).toBeHidden();
    await expect(page.locator('input[name="api_key"]')).toHaveCount(0);
    await expect(
      page.getByRole('button', { name: 'Save and sign in', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'OpenAI Codex', exact: false }),
    ).toBeFocused();
  });
}

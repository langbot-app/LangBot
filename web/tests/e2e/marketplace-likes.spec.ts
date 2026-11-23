import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('marketplace defaults to hot sorting and updates the same browser like on its card', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const searches: Record<string, unknown>[] = [],
    updates: unknown[] = [];
  let fingerprint = '';
  await page.route('**/api/v1/marketplace/extensions/search', async (route) => {
    searches.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        code: 0,
        data: {
          total: 1,
          extensions: [
            {
              author: 'qa',
              name: 'liked',
              label: { en_US: 'QA Likes' },
              description: { en_US: 'Like test plugin' },
              latest_version: '1.0.0',
              type: 'plugin',
              status: 'live',
              tags: [],
              components: {},
              install_count: 5,
              like_count: 12,
              hot_score: 17,
            },
          ],
        },
      },
    });
  });
  await page.route(
    '**/api/v1/marketplace/extensions/likes/status',
    async (route) => {
      fingerprint = route.request().postDataJSON().fingerprint;
      expect(fingerprint).toEqual(expect.any(String));
      expect(fingerprint.length).toBeGreaterThan(0);
      await route.fulfill({ json: { code: 0, data: { extensions: [] } } });
    },
  );
  await page.route(
    '**/api/v1/marketplace/extensions/plugin/qa/liked/like',
    async (route) => {
      const body = route.request().postDataJSON();
      updates.push(body);
      expect(route.request().method()).toBe('PUT');
      expect(body.fingerprint).toBe(fingerprint);
      await route.fulfill({
        json: {
          code: 0,
          data: {
            type: 'plugin',
            extension_id: 'qa/liked',
            liked: body.liked,
            like_count: body.liked ? 13 : 12,
          },
        },
      });
    },
  );
  await page.goto('/home/add-extension');
  await expect(page.getByText('QA Likes', { exact: true })).toBeVisible();
  await expect.poll(() => fingerprint).not.toBe('');
  const like = page.getByRole('button', { name: 'Like', exact: true });
  await expect(like).toHaveAttribute('aria-pressed', 'false');
  await expect(like).toHaveText('12');
  expect(searches.length).toBeGreaterThan(0);
  expect(searches[0]).toMatchObject({
    sort_by: 'hot_score',
    sort_order: 'DESC',
  });
  await like.click();
  const unlike = page.getByRole('button', { name: 'Unlike', exact: true });
  await expect(unlike).toHaveAttribute('aria-pressed', 'true');
  await expect(unlike).toHaveText('13');
  await unlike.click();
  await expect(like).toHaveAttribute('aria-pressed', 'false');
  await expect(like).toHaveText('12');
  expect(updates).toEqual([
    { fingerprint, liked: true },
    { fingerprint, liked: false },
  ]);
});

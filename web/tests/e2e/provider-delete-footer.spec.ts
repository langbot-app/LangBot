import { expect, test, type Page, type Route } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

// UI fixtures only: no real provider/model deletion or subscription authentication.
async function fixture(page: Page, requester = 'openai', empty = false) {
  await installLangBotApiMocks(page, { authenticated: true });
  const provider = {
    uuid: 'provider-delete-fixture',
    name: 'Delete fixture provider',
    requester,
    base_url: 'https://example.test/v1',
    api_keys: [],
    llm_count: empty ? 0 : 1,
    embedding_count: empty ? 0 : 1,
    rerank_count: empty ? 0 : 1,
  };
  const state = {
    deleted: false,
    fail: false,
    deletes: [] as string[],
    reads: [] as string[],
    release: undefined as (() => void) | undefined,
    hold: false,
  };
  const ok = (route: Route, data: unknown) =>
    route.fulfill({ json: { code: 0, data } });
  await page.route('**/api/v1/provider/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    if (method === 'DELETE') {
      state.deletes.push(path + url.search);
      if (state.hold)
        await new Promise<void>((resolve) => {
          state.release = resolve;
        });
      if (state.fail)
        return route.fulfill({
          status: 409,
          json: { code: 409, msg: 'Fixture deletion blocked; try again.' },
        });
      state.deleted = true;
      return ok(route, {});
    }
    if (path.endsWith('/icon'))
      return route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg"/>',
      });
    if (path.endsWith('/requesters'))
      return ok(route, {
        requesters: ['openai', 'openai-codex'].map((name) => ({
          name,
          label: { en_US: name },
          description: { en_US: '' },
          spec: {
            provider_category: 'manufacturer',
            support_type: ['llm', 'embedding', 'rerank'],
            config: [],
          },
        })),
      });
    if (method === 'GET') state.reads.push(path + url.search);
    if (path.endsWith('/providers'))
      return ok(route, { providers: state.deleted ? [] : [provider] });
    if (path.endsWith('/codex/status'))
      return ok(route, {
        status: 'connected',
        connected: true,
        expires_at: null,
      });
    if (path.includes('/models/')) {
      const type = path.split('/').pop();
      return ok(route, {
        models: state.deleted
          ? []
          : [
              {
                uuid: `fixture-${type}`,
                name: `Fixture ${type} model`,
                provider_uuid: provider.uuid,
                provider,
                abilities: [],
                extra_args: {},
              },
            ],
      });
    }
    if (path.endsWith(provider.uuid)) return ok(route, { provider });
    return ok(route, {});
  });
  await page.goto('/home/bots');
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  return state;
}
const editDialog = (page: Page) =>
  page.locator('[role="dialog"]').filter({
    has: page.locator('[data-slot="dialog-title"]', {
      hasText: /^Edit Provider$/,
    }),
  });
async function edit(page: Page) {
  const card = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'Delete fixture provider' });
  await card.getByRole('button', { name: 'Expand', exact: true }).click();
  await expect(
    card.getByText('Fixture llm model', { exact: true }),
  ).toBeVisible();
  await card
    .locator('button')
    .filter({ has: page.locator('svg.lucide-settings') })
    .click();
  await expect(editDialog(page).locator('input[name="name"]')).toHaveValue(
    'Delete fixture provider',
  );
}

for (const width of [1280, 320]) {
  test(`confirmation stays centered throughout entry (${width}px)`, async ({
    page,
  }) => {
    const state = await fixture(page);
    await edit(page);
    await page.setViewportSize({ width, height: 900 });
    // Trigger without Playwright's post-click wait so the browser animation is
    // still live. Sample its actual keyframes, not only the final screenshot.
    await editDialog(page)
      .getByRole('button', { name: 'Delete', exact: true })
      .evaluate((el) => (el as HTMLButtonElement).click());
    const confirmation = page.getByRole('alertdialog');
    for (const phase of ['entry']) {
      const samples = await confirmation.evaluate(async (el) => {
        const animations = el.getAnimations();
        if (!animations.length)
          throw new Error('Expected the real dialog animation');
        await Promise.all(animations.map((a) => a.ready));
        animations.forEach((a) => a.pause());
        const samples = [0, 0.25, 0.5, 0.75, 0.99].map((fraction) => {
          animations.forEach((a) => {
            a.currentTime = Number(a.effect!.getTiming().duration) * fraction;
          });
          const r = el.getBoundingClientRect();
          return {
            x: r.x + r.width / 2,
            y: r.y + r.height / 2,
            left: r.left,
            right: r.right,
          };
        });
        animations.forEach((a) => a.finish());
        return samples;
      });
      for (const sample of samples) {
        expect(
          Math.abs(sample.x - width / 2),
          `${phase} horizontal center`,
        ).toBeLessThan(1);
        expect(
          Math.abs(sample.y - 450),
          `${phase} vertical center`,
        ).toBeLessThan(1);
        expect(sample.left).toBeGreaterThanOrEqual(0);
        expect(sample.right).toBeLessThanOrEqual(width);
      }
    }
    await confirmation
      .getByRole('button', { name: 'Cancel', exact: true })
      .click();
    await expect(confirmation).toHaveCount(0);
    expect(state.deletes).toEqual([]);
  });
}

for (const requester of ['openai', 'openai-codex']) {
  for (const width of [1280, 320]) {
    test(`footer deletion confirmation cancellation and geometry (${requester}, ${width}px)`, async ({
      page,
    }) => {
      const state = await fixture(page, requester);
      await edit(page);
      await page.setViewportSize({ width, height: 900 });
      const dialog = editDialog(page);
      const footer = dialog.locator('[data-slot="dialog-footer"]');
      const remove = footer.getByRole('button', {
        name: 'Delete',
        exact: true,
      });
      await expect(remove).toBeVisible();
      for (const button of await footer.getByRole('button').all()) {
        await expect(button).toBeInViewport({ ratio: 1 });
        const box = await button.boundingBox();
        expect(box!.x).toBeGreaterThanOrEqual(0);
        expect(box!.x + box!.width).toBeLessThanOrEqual(width);
      }
      const left = await remove.boundingBox();
      const cancel = await footer
        .getByRole('button', { name: 'Cancel', exact: true })
        .boundingBox();
      expect(left!.x + left!.width).toBeLessThan(cancel!.x);
      await remove.click();
      const confirmation = page.getByRole('alertdialog');
      await expect(confirmation).toContainText('this provider and ALL models');
      await expect(confirmation).toContainText('cannot be undone');
      await expect(confirmation).toBeInViewport({ ratio: 1 });
      await confirmation.evaluate(async (element) => {
        await Promise.all(
          element.getAnimations().map((animation) => animation.finished),
        );
      });
      const box = await confirmation.boundingBox();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(width);
      await confirmation
        .getByRole('button', { name: 'Cancel', exact: true })
        .click();
      await expect(confirmation).toHaveCount(0);
      await expect(dialog).toBeVisible();
      expect(state.deletes).toEqual([]);
    });
  }
  test(`one awaited cascade request refreshes providers and clears models (${requester})`, async ({
    page,
  }) => {
    const state = await fixture(page, requester);
    await edit(page);
    state.hold = true;
    await editDialog(page)
      .getByRole('button', { name: 'Delete', exact: true })
      .click();
    const confirmation = page.getByRole('alertdialog');
    await confirmation
      .getByRole('button', { name: 'Delete', exact: true })
      .click();
    await expect.poll(() => state.deletes.length).toBe(1);
    await expect(
      confirmation.getByRole('button', { name: 'Delete', exact: true }),
    ).toBeDisabled();
    await expect(
      confirmation.getByRole('button', { name: 'Cancel', exact: true }),
    ).toBeDisabled();
    await expect(
      editDialog(page).getByRole('button', {
        name: requester === 'openai' ? 'Save' : 'Done',
        exact: true,
        includeHidden: true,
      }),
    ).toBeDisabled();
    await page.keyboard.press('Escape');
    await expect(confirmation).toBeVisible();
    state.reads = [];
    state.release!();
    await expect(editDialog(page)).toHaveCount(0);
    await expect(
      page.getByText('Delete fixture provider', { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText('Fixture llm model', { exact: true }),
    ).toHaveCount(0);
    expect(state.deletes).toEqual([
      '/api/v1/provider/providers/provider-delete-fixture?cascade=true',
    ]);
    expect(state.reads).toContain('/api/v1/provider/providers');
  });
}

test('failed cascade retains readable error and can retry', async ({
  page,
}) => {
  const state = await fixture(page);
  await edit(page);
  state.fail = true;
  await editDialog(page)
    .getByRole('button', { name: 'Delete', exact: true })
    .click();
  const confirmation = page.getByRole('alertdialog');
  await confirmation
    .getByRole('button', { name: 'Delete', exact: true })
    .click();
  await expect(confirmation.getByRole('alert')).toContainText(
    'Fixture deletion blocked; try again.',
  );
  await expect(
    confirmation.getByRole('button', { name: 'Delete', exact: true }),
  ).toBeEnabled();
  await expect(editDialog(page)).toBeVisible();
  state.fail = false;
  await confirmation
    .getByRole('button', { name: 'Delete', exact: true })
    .click();
  await expect(editDialog(page)).toHaveCount(0);
  expect(state.deletes).toHaveLength(2);
});

test('new providers do not expose footer deletion', async ({ page }) => {
  const state = await fixture(page);
  await page.getByRole('button', { name: 'Add Provider', exact: true }).click();
  await expect(
    page
      .getByRole('dialog', { name: 'Add Provider', exact: true })
      .getByRole('button', { name: 'Delete', exact: true }),
  ).toHaveCount(0);
  expect(state.deletes).toEqual([]);
});

test('system-managed provider has no edit or delete entry', async ({
  page,
}) => {
  const state = await fixture(page, 'space-chat-completions');
  const card = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'Delete fixture provider' });
  await expect(card).toBeVisible();
  await expect(card.locator('svg.lucide-settings')).toHaveCount(0);
  await expect(card.locator('svg.lucide-trash-2')).toHaveCount(0);
  expect(state.deletes).toEqual([]);
});

test('existing empty-provider card delete keeps its non-cascade request', async ({
  page,
}) => {
  const state = await fixture(page, 'openai', true);
  const card = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'Delete fixture provider' });
  await card
    .locator('button')
    .filter({ has: page.locator('svg.lucide-trash-2') })
    .click();
  await expect(
    page.getByText('Are you sure you want to delete this provider?', {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(card).toHaveCount(0);
  expect(state.deletes).toEqual([
    '/api/v1/provider/providers/provider-delete-fixture',
  ]);
});

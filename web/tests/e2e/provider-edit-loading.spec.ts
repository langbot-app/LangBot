import { expect, test, type Page, type Route } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

// All API traffic is intercepted; no real provider secrets or mutations.
async function fixture(page: Page, requester = 'openai') {
  await installLangBotApiMocks(page, { authenticated: true });
  const providers = ['alpha', 'beta'].map((id) => ({
    uuid: `loading-${id}`,
    name: `Loading fixture ${id}`,
    requester,
    base_url: `https://${id}.example.test/v1`,
    api_keys: [`fixture-key-${id}`],
    llm_count: 0,
    embedding_count: 0,
    rerank_count: 0,
  }));
  const state = {
    hold: '' as '' | 'detail' | 'requesters',
    fail: '' as '' | 'detail' | 'requesters',
    held: [] as { release: () => void; finished: Promise<void> }[],
    reads: [] as string[],
    mutations: [] as string[],
    errors: [] as string[],
  };
  page.on('pageerror', (error) => state.errors.push(error.message));
  const ok = (route: Route, data: unknown) =>
    route.fulfill({ json: { code: 0, data } });
  await page.route('**/api/v1/provider/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== 'GET') {
      state.mutations.push(route.request().method() + ' ' + path);
      return ok(route, {});
    }
    if (path.endsWith('/icon'))
      return route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg"/>',
      });
    state.reads.push(path);
    const provider = providers.find((p) => path.endsWith('/' + p.uuid));
    const dependency = path.endsWith('/requesters')
      ? 'requesters'
      : provider
        ? 'detail'
        : '';
    const fail = dependency && state.fail === dependency;
    let finish: (() => void) | undefined;
    if (dependency && state.hold === dependency) {
      const finished = new Promise<void>((resolve) => {
        finish = resolve;
      });
      await new Promise<void>((release) =>
        state.held.push({ release, finished }),
      );
    }
    try {
      if (fail)
        return await route.fulfill({
          status: 503,
          json: { code: 503, msg: `Fixture ${dependency} unavailable` },
        });
      if (dependency === 'requesters')
        return await ok(route, {
          requesters: [
            {
              name: requester,
              label: {
                en_US:
                  requester === 'openai' ? 'OpenAI fixture' : 'Codex fixture',
              },
              description: { en_US: '' },
              spec: {
                provider_category: 'manufacturer',
                support_type: ['llm'],
                config: [],
              },
            },
          ],
        });
      if (provider) return await ok(route, { provider });
      if (path.endsWith('/providers')) return await ok(route, { providers });
      if (path.endsWith('/codex/status'))
        return await ok(route, {
          status: 'connected',
          connected: true,
          expires_at: null,
        });
      return await ok(route, { models: [] });
    } finally {
      finish?.();
    }
  });
  await page.goto('/home/bots');
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await expect(
    page.getByText(providers[0].name, { exact: true }),
  ).toBeVisible();
  // Let the panel's independent requester-support read finish before gating the form.
  await expect
    .poll(() => state.reads.filter((p) => p.endsWith('/requesters')).length)
    .toBeGreaterThanOrEqual(1);
  return state;
}

const dialog = (page: Page) =>
  page.getByRole('dialog', { name: 'Edit Provider', exact: true });
const editButton = (page: Page, id = 'alpha') =>
  page
    .locator('[data-slot="card"]')
    .filter({ hasText: `Loading fixture ${id}` })
    .locator('button')
    .filter({ has: page.locator('svg.lucide-settings') });

async function expectLoading(page: Page) {
  const form = dialog(page);
  await expect(form.getByRole('status')).toContainText('Loading...');
  await expect(
    form.getByRole('status').locator('svg.animate-spin'),
  ).toBeVisible();
  await expect(form.locator('input')).toHaveCount(0);
  await expect(
    form.getByRole('button', { name: /^(Save|Done|Delete)$/ }),
  ).toHaveCount(0);
  await expect(
    form.getByRole('button', { name: 'Cancel', exact: true }),
  ).toBeEnabled();
}

async function expectReady(page: Page, id = 'alpha', requester = 'openai') {
  const form = dialog(page);
  await expect(form.locator('input[name="name"]')).toHaveValue(
    `Loading fixture ${id}`,
  );
  await expect(
    form.getByRole('status', { name: 'Loading...', exact: true }),
  ).toHaveCount(0);
  await expect(
    form.getByRole('button', { name: 'Delete', exact: true }),
  ).toBeEnabled();
  await expect(
    form.getByRole('button', {
      name: requester === 'openai' ? 'Save' : 'Done',
      exact: true,
    }),
  ).toBeEnabled();
  if (requester === 'openai') {
    await expect(form.locator('input[name="base_url"]')).toHaveValue(
      `https://${id}.example.test/v1`,
    );
    await expect(form.locator('input[name="api_key"]')).toHaveValue(
      `fixture-key-${id}`,
    );
    await expect(
      form.getByRole('button', { name: /OpenAI fixture/ }),
    ).toBeVisible();
  } else {
    await expect(form.locator('input[name="api_key"]')).toHaveCount(0);
    await expect(
      form.getByRole('button', { name: /Codex fixture/ }),
    ).toBeVisible();
  }
}

for (const requester of ['openai', 'openai-codex']) {
  for (const dependency of ['detail', 'requesters'] as const) {
    test(`edit waits for ${dependency} before showing populated ${requester} form`, async ({
      page,
    }) => {
      const state = await fixture(page, requester);
      state.hold = dependency;
      await editButton(page).click();
      await expect.poll(() => state.held.length).toBeGreaterThanOrEqual(1);
      await expectLoading(page);
      // Remain gated for the whole delay, not just the first render.
      await page.waitForTimeout(250);
      await expectLoading(page);
      state.hold = '';
      state.held.forEach((request) => request.release());
      await expectReady(page, 'alpha', requester);
      expect(state.mutations).toEqual([]);
      expect(state.errors).toEqual([]);
    });
  }
}

for (const dependency of ['detail', 'requesters'] as const) {
  test(`${dependency} load failure is recoverable with Retry or Cancel`, async ({
    page,
  }) => {
    const state = await fixture(page);
    state.fail = dependency;
    await editButton(page).click();
    const form = dialog(page);
    await expect(form.getByRole('alert')).toContainText('Failed to load data');
    await expect(form.locator('input')).toHaveCount(0);
    await expect(
      form.getByRole('button', { name: /^(Save|Done|Delete)$/ }),
    ).toHaveCount(0);
    await expect(
      form.getByRole('button', { name: 'Retry', exact: true }),
    ).toBeEnabled();
    await expect(
      form.getByRole('button', { name: 'Cancel', exact: true }),
    ).toBeEnabled();
    state.fail = '';
    state.hold = dependency;
    await form.getByRole('button', { name: 'Retry', exact: true }).click();
    await expect.poll(() => state.held.length).toBeGreaterThanOrEqual(1);
    await expectLoading(page);
    state.hold = '';
    state.held.forEach((request) => request.release());
    await expectReady(page);
    await form.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(form).toHaveCount(0);
    state.fail = dependency;
    await editButton(page).click();
    await expect(form.getByRole('alert')).toBeVisible();
    await form.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(form).toHaveCount(0);
    expect(state.mutations).toEqual([]);
    expect(state.errors).toEqual([]);
  });
}

for (const next of ['alpha', 'beta']) {
  for (const staleFailure of [false, true]) {
    test(`closed request ${staleFailure ? 'failure' : 'success'} cannot affect reopened ${next}`, async ({
      page,
    }) => {
      const state = await fixture(page);
      state.hold = 'detail';
      state.fail = staleFailure ? 'detail' : '';
      await editButton(page).click();
      await expect.poll(() => state.held.length).toBeGreaterThanOrEqual(1);
      await expectLoading(page);
      const staleRequests = state.held.splice(0);
      await dialog(page)
        .getByRole('button', { name: 'Cancel', exact: true })
        .click();
      state.fail = '';
      // Reopen during the closing animation, before Radix's retained content unmounts.
      await editButton(page, next).dispatchEvent('click');
      await expect.poll(() => state.held.length).toBeGreaterThanOrEqual(1);
      await expectLoading(page);
      state.hold = '';
      state.held.forEach((request) => request.release());
      await expectReady(page, next);
      await dialog(page)
        .locator('input[name="name"]')
        .fill('Unsaved fixture edit');
      staleRequests.forEach((request) => request.release());
      await Promise.all(staleRequests.map((request) => request.finished));
      await page.waitForTimeout(250);
      await expect(dialog(page).locator('input[name="name"]')).toHaveValue(
        'Unsaved fixture edit',
      );
      await expect(dialog(page).getByRole('alert')).toHaveCount(0);
      expect(state.mutations).toEqual([]);
      expect(state.errors).toEqual([]);
    });
  }
}

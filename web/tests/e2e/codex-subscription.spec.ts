import { writeFileSync } from 'node:fs';
import { expect, test, type Page, type Route } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

// All OAuth, provider and model responses here are explicit UI fixtures.
// These tests never authenticate with OpenAI or use a real subscription.
async function fixture(page: Page) {
  await installLangBotApiMocks(page, { authenticated: true });
  const state = {
    providers: [] as Record<string, unknown>[],
    creates: 0,
    starts: 0,
    polls: 0,
    cancels: 0,
    disconnects: 0,
    connected: false,
    failStart: false,
    pollStatus: 'pending',
    interval: 1,
    expiresIn: 600,
  };
  const ok = (route: Route, data: unknown) =>
    route.fulfill({ json: { code: 0, data } });
  await page.route('**/api/v1/provider/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    if (path.endsWith('/icon'))
      return route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><circle cx="12" cy="12" r="10" fill="#555"/></svg>',
      });
    if (path.endsWith('/requesters'))
      return ok(route, {
        requesters: ['openai-codex', 'openai'].map((name) => ({
          name,
          label: {
            en_US: name === 'openai-codex' ? 'OpenAI Codex' : 'OpenAI API',
          },
          description: { en_US: '' },
          spec: {
            provider_category: 'manufacturer',
            support_type: ['llm'],
            config: [
              { name: 'base_url', default: 'https://api.openai.com/v1' },
            ],
          },
        })),
      });
    if (path.endsWith('/providers')) {
      if (method === 'POST') {
        state.creates++;
        const provider = {
          ...route.request().postDataJSON(),
          uuid: `provider-${state.creates}`,
        };
        state.providers.push(provider);
        return ok(route, { uuid: provider.uuid });
      }
      return ok(route, { providers: state.providers });
    }
    if (path.endsWith('/codex/status'))
      return ok(route, {
        status: state.connected ? 'connected' : 'disconnected',
        connected: state.connected,
        expires_at: null,
      });
    if (path.endsWith('/codex/device') && method === 'POST') {
      state.starts++;
      if (state.failStart)
        return route.fulfill({
          status: 400,
          json: { code: 400, msg: 'Fixture start failure' },
        });
      return ok(route, {
        authorization_id: `attempt-${state.starts}`,
        user_code: 'TEST-1234',
        verification_uri: 'https://auth.openai.com/codex/device',
        interval: state.interval,
        expires_at: Date.now() / 1000 + state.expiresIn,
      });
    }
    if (path.endsWith('/codex/device/poll')) {
      state.polls++;
      expect(route.request().postDataJSON()).toEqual({
        authorization_id: `attempt-${state.starts}`,
      });
      if (state.pollStatus === 'connected') state.connected = true;
      return ok(route, { status: state.pollStatus, interval: state.interval });
    }
    if (path.includes('/codex/device/') && method === 'DELETE') {
      state.cancels++;
      return ok(route, {});
    }
    if (path.endsWith('/codex/auth') && method === 'DELETE') {
      state.disconnects++;
      state.connected = false;
      return ok(route, {});
    }
    if (/\/providers\/provider-\d+$/.test(path)) {
      const provider = state.providers.find((p) =>
        path.endsWith(String(p.uuid)),
      );
      if (method === 'PUT')
        Object.assign(provider!, route.request().postDataJSON());
      return ok(route, { provider });
    }
    if (path.includes('/models/')) return ok(route, { models: [] });
    return ok(route, {});
  });
  return state;
}

async function openModels(page: Page) {
  await page.goto('/home/bots');
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await page.getByRole('button', { name: 'Add Provider', exact: true }).click();
}
async function choose(page: Page, name: string) {
  await page
    .getByRole('button', { name: 'Select Provider Type', exact: true })
    .click();
  await page.getByRole('button', { name: new RegExp(name) }).click();
}

for (const width of [1280, 390, 320]) {
  test(`subscription sign-in in the existing provider dialog (${width}px, UI fixture)`, async ({
    page,
  }) => {
    const state = await fixture(page);
    await page.setViewportSize({ width: 1280, height: 900 });
    await openModels(page);
    await page.setViewportSize({ width, height: 900 });
    await page.locator('input[name="name"]').fill('My Codex');
    await choose(page, 'OpenAI Codex');
    await expect(page.locator('input[name="api_key"]')).toHaveCount(0);
    await expect(page.locator('input[name="base_url"]')).toHaveCount(0);
    await page
      .getByRole('button', { name: 'Save and sign in', exact: true })
      .click();
    await expect(page.getByText('TEST-1234')).toBeVisible();
    await page.getByRole('button', { name: 'Copy code', exact: true }).click();
    await expect(
      page.getByRole('button', { name: 'Copied', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText('Copy Successfully', { exact: true }),
    ).toBeInViewport({ ratio: 1 });
    expect(state.creates).toBe(1);
    expect(state.providers[0]).toMatchObject({
      requester: 'openai-codex',
      api_keys: [],
      base_url: 'https://chatgpt.com/backend-api/codex',
    });
    await expect(
      page.getByRole('link', { name: 'Continue at OpenAI' }),
    ).toHaveAttribute('href', 'https://auth.openai.com/codex/device');
    const geometry = await page.getByTestId('codex-account').evaluate((el) => {
      const box = el.getBoundingClientRect();
      return {
        left: box.left,
        right: box.right,
        width: innerWidth,
        documentWidth: document.documentElement.scrollWidth,
      };
    });
    expect(geometry.left).toBeGreaterThanOrEqual(0);
    expect(geometry.right).toBeLessThanOrEqual(width);
    expect(geometry.documentWidth).toBeLessThanOrEqual(width);
    if (process.env.CODEX_EVIDENCE_DIR) {
      await page.locator('[data-sonner-toast]').evaluate(async (el) => {
        await Promise.all(
          el
            .getAnimations({ subtree: true })
            .map((animation) => animation.finished.catch(() => undefined)),
        );
      });
      const screenshot = `${process.env.CODEX_EVIDENCE_DIR}/codex-${width}.png`;
      await page.screenshot({ path: screenshot, fullPage: true });
      writeFileSync(
        `${process.env.CODEX_EVIDENCE_DIR}/codex-${width}.json`,
        JSON.stringify(
          {
            evidence: 'UI fixture only; not live OpenAI sign-in',
            viewport: { width, height: 900 },
            geometry,
            screenshot,
          },
          null,
          2,
        ),
      );
    }
    state.pollStatus = 'connected';
    await expect(page.getByText('Connected', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await expect(page.getByText('My Codex', { exact: true })).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Add Model', exact: true }),
    ).toBeVisible();
    expect(state.creates).toBe(1);
    expect(
      await page.evaluate(() => JSON.stringify({ ...localStorage })),
    ).not.toContain('attempt-');
  });
}

test('failed start retries reuse saved provider; cancellation refreshes list', async ({
  page,
}) => {
  const state = await fixture(page);
  state.failStart = true;
  await openModels(page);
  await page.locator('input[name="name"]').fill('Retry Codex');
  await choose(page, 'OpenAI Codex');
  await page
    .getByRole('button', { name: 'Save and sign in', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText('Unable to sign in');
  state.failStart = false;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.getByText('TEST-1234')).toBeVisible();
  await page
    .getByRole('button', { name: 'Cancel sign-in', exact: true })
    .click();
  await expect.poll(() => state.cancels).toBe(1);
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByText('Retry Codex', { exact: true })).toBeVisible();
  expect(state.creates).toBe(1);
});

test('reconnect cancellation preserves connection and disconnect requires confirmation', async ({
  page,
}) => {
  const state = await fixture(page);
  state.pollStatus = 'connected';
  await openModels(page);
  await page.locator('input[name="name"]').fill('Managed Codex');
  await choose(page, 'OpenAI Codex');
  await page
    .getByRole('button', { name: 'Save and sign in', exact: true })
    .click();
  await expect(page.getByText('Connected', { exact: true })).toBeVisible();
  state.pollStatus = 'pending';
  await page.getByRole('button', { name: 'Reconnect', exact: true }).click();
  await expect(page.getByText('TEST-1234')).toBeVisible();
  await page
    .getByRole('button', { name: 'Cancel sign-in', exact: true })
    .click();
  await expect(page.getByText('Connected', { exact: true })).toBeVisible();
  expect(state.disconnects).toBe(0);
  await page.getByRole('button', { name: 'Disconnect', exact: true }).click();
  expect(state.disconnects).toBe(0);
  await page
    .getByRole('button', { name: 'Confirm disconnect', exact: true })
    .click();
  await expect(page.getByText('Not connected', { exact: true })).toBeVisible();
  expect(state.disconnects).toBe(1);
  expect(state.creates).toBe(1);
});

test('expiration permits retry without duplicate provider and closing cancels pending login', async ({
  page,
}) => {
  const state = await fixture(page);
  state.expiresIn = 1;
  await openModels(page);
  await page.locator('input[name="name"]').fill('Expired Codex');
  await choose(page, 'OpenAI Codex');
  await page
    .getByRole('button', { name: 'Save and sign in', exact: true })
    .click();
  await expect(
    page.getByText('Sign-in expired. Start again to get a new code.'),
  ).toBeVisible();
  await expect.poll(() => state.cancels).toBe(1);
  state.expiresIn = 600;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.getByText('TEST-1234')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect.poll(() => state.cancels).toBe(2);
  await expect(page.getByText('Expired Codex', { exact: true })).toBeVisible();
  expect(state.creates).toBe(1);
  await page.getByRole('button', { name: 'Add Provider', exact: true }).click();
  await page.locator('input[name="name"]').fill('Second Codex');
  await choose(page, 'OpenAI Codex');
  await page
    .getByRole('button', { name: 'Save and sign in', exact: true })
    .click();
  await expect(page.getByText('TEST-1234')).toBeVisible();
  expect(state.creates).toBe(2);
  expect(state.providers.map((provider) => provider.name)).toEqual([
    'Expired Codex',
    'Second Codex',
  ]);
  await page.keyboard.press('Escape');
  await expect.poll(() => state.cancels).toBe(3);
});

test('model test retains the connected provider identity', async ({ page }) => {
  const state = await fixture(page);
  state.connected = true;
  state.providers.push({
    uuid: 'provider-1',
    name: 'Connected Codex',
    requester: 'openai-codex',
    base_url: 'https://chatgpt.com/backend-api/codex',
    api_keys: [],
  });
  await page.goto('/home/bots');
  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await page.getByRole('button', { name: 'Add Model', exact: true }).click();
  await page
    .getByPlaceholder('Model Name', { exact: true })
    .fill('fixture-codex-model');
  const requestPromise = page.waitForRequest('**/models/llm/_/test');
  await page.getByRole('button', { name: 'Test', exact: true }).click();
  const payload = (await requestPromise).postDataJSON();
  expect(payload.provider_uuid).toBe('provider-1');
  expect(payload.provider.uuid).toBe('provider-1');
  expect(payload.provider.api_keys).toEqual([]);
});

test('ordinary API-key provider still saves and closes', async ({ page }) => {
  const state = await fixture(page);
  await openModels(page);
  await page.locator('input[name="name"]').fill('My API');
  await choose(page, 'OpenAI API');
  await page.locator('input[name="api_key"]').fill('fixture-api-key-not-real');
  await page
    .locator('input[name="base_url"]')
    .fill('https://api.example.test/v1');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByText('My API', { exact: true })).toBeVisible();
  expect(state.providers[0]).toMatchObject({
    requester: 'openai',
    api_keys: ['fixture-api-key-not-real'],
    base_url: 'https://api.example.test/v1',
  });
  expect(state.starts).toBe(0);
});

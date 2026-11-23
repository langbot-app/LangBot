import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

for (const width of [1440, 390]) {
  test(`bot setup and detail columns stay separated at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await installLangBotApiMocks(page, { authenticated: true });
    await page.goto('/home/bots?id=new');
    const layout = page.locator('#bot-form > fieldset');
    const basic = layout.locator('[data-guide="bot-basic"]');
    const adapter = page.getByTestId('adapter-gallery');
    await expect(basic).toBeVisible();
    await expect(adapter).toBeVisible();
    const basicBox = (await basic.boundingBox())!;
    const adapterBox = (await adapter.boundingBox())!;
    if (width >= 1024)
      expect(adapterBox.x).toBeGreaterThan(basicBox.x + basicBox.width);
    else expect(adapterBox.y).toBeGreaterThan(basicBox.y + basicBox.height);
    await adapter.getByRole('button', { name: /Playwright Adapter/ }).click();
    await page.locator('input[name="name"]').fill('Layout bot');
    await page.getByRole('button', { name: /^Submit$/ }).click();
    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);
    const routing = page.locator('[data-guide="bot-routing"]');
    await expect(routing).toBeVisible();
    const cards = await layout.locator(':scope > [data-slot="card"]').all();
    expect(cards).toHaveLength(2);
    const left = (await cards[0].boundingBox())!;
    const right = (await cards[1].boundingBox())!;
    if (width >= 1024) expect(right.x).toBeGreaterThan(left.x + left.width);
    else expect(right.y).toBeGreaterThan(left.y + left.height);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.goto('/home/knowledge?id=new');
    const form = page.locator('#kb-form');
    await expect(form).toBeVisible();
    const children = await form.locator(':scope > *').all();
    expect(children.length).toBeGreaterThan(1);
    for (let i = 1; i < children.length; i++) {
      const previous = await children[i - 1].boundingBox();
      const current = await children[i].boundingBox();
      if (previous && current)
        expect(current.y - previous.y - previous.height).toBeGreaterThanOrEqual(
          20,
        );
    }
  });
}

test('the dedicated connection selector hides its manifest controller and persists its value', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.route('**/api/v1/platform/adapters', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          adapters: [
            {
              name: 'connection-adapter',
              label: { en_US: 'Connection adapter' },
              description: { en_US: 'Both connection modes' },
              spec: {
                categories: ['testing'],
                config: [
                  {
                    name: 'transport',
                    label: { en_US: 'Raw transport controller' },
                    type: 'select',
                    required: true,
                    default: 'persistent',
                    options: [
                      { name: 'persistent', label: { en_US: 'Persistent' } },
                      {
                        name: 'webhook',
                        label: { en_US: 'Webhook transport' },
                      },
                    ],
                  },
                  {
                    name: 'webhook_url',
                    label: { en_US: 'Webhook address' },
                    type: 'webhook-url',
                    show_if: {
                      field: 'transport',
                      operator: 'eq',
                      value: 'webhook',
                    },
                  },
                  {
                    name: 'credential',
                    label: { en_US: 'Adapter credential' },
                    type: 'string',
                    required: true,
                    default: '',
                  },
                ],
              },
            },
          ],
        },
      },
    }),
  );
  await page.goto('/home/bots?id=new');
  await page
    .getByTestId('adapter-gallery')
    .getByRole('button', { name: /Connection adapter/ })
    .click();
  await page.getByRole('button', { name: /^Submit$/ }).click();
  await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);
  await page.getByRole('radio', { name: /^Webhook/ }).click();
  await expect(page.getByText(/^Raw transport controller/)).toHaveCount(0);
  await expect(
    page.getByText('Webhook address', { exact: true }),
  ).toBeVisible();
  await page.locator('input[name="credential"]').fill('persist-me');
  const save = page.waitForRequest(
    (request) =>
      request.method() === 'PUT' &&
      request.url().endsWith('/api/v1/platform/bots/bot-1'),
  );
  await page.getByRole('button', { name: /^Save and enable$/ }).click();
  expect((await save).postDataJSON().adapter_config).toEqual({
    transport: 'webhook',
    credential: 'persist-me',
  });
});

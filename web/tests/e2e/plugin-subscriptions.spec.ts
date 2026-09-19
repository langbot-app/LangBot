import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('creates a configured processor, persists subscriptions separately and reuses an instance', async ({
  page,
}) => {
  test.setTimeout(60_000);
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAdapterEvents: true,
  });
  const ref = 'plugin:test/welcome/default';
  const processors: Record<string, unknown>[] = [];
  await page.route('**/api/v1/agents/_/metadata', async (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          event_processors: [
            {
              id: ref,
              plugin_author: 'test',
              plugin_name: 'welcome',
              usages: ['event'],
              label: { en_US: 'Welcome members', zh_Hans: '欢迎新成员' },
              supported_event_patterns: ['group.member_joined'],
              config_schema: [
                {
                  name: 'greeting',
                  type: 'string',
                  label: { en_US: 'Greeting', zh_Hans: '欢迎语' },
                  required: true,
                  default: 'Hello',
                },
              ],
            },
          ],
        },
      },
    }),
  );
  await page.route('**/api/v1/agents', async (route) => {
    if (route.request().method() === 'POST') {
      processors.push({
        ...route.request().postDataJSON(),
        uuid: 'processor-new',
        supported_event_patterns: ['group.member_joined'],
      });
      return route.fulfill({
        json: {
          code: 0,
          data: { uuid: 'processor-new', kind: 'event_processor' },
        },
      });
    }
    return route.fulfill({ json: { code: 0, data: { agents: processors } } });
  });
  await page.goto('/home/bots?id=new');
  await page
    .getByTestId('adapter-gallery')
    .getByRole('button', { name: /Playwright Adapter/ })
    .click();
  await page.locator('input[name="name"]').fill('Subscription Bot');
  await page.getByRole('button', { name: /^Submit$/ }).click();
  await expect(page).toHaveURL(/id=bot-1$/);
  const section = page.getByRole('region', {
    name: 'Plugin processor',
    exact: true,
  });
  await section.getByRole('button', { name: 'Add plugin processor' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: /Welcome members/ }).click();
  await dialog.getByLabel('Name', { exact: true }).fill('Customer welcome');
  await dialog.locator('input[name="greeting"]').fill('Welcome aboard');
  await dialog.getByRole('button', { name: 'Create and bind' }).click();
  await expect(dialog).toBeHidden();
  expect(processors[0]).toMatchObject({
    kind: 'event_processor',
    component_ref: ref,
    config: { runner_config: { [ref]: { greeting: 'Welcome aboard' } } },
  });
  await expect(section).toContainText('Customer welcome');
  const save = async () => {
    const request = page.waitForRequest(
      (r) => r.method() === 'PUT' && r.url().endsWith('/platform/bots/bot-1'),
    );
    await page.getByRole('button', { name: /^Save$/ }).click();
    const body = (await request).postDataJSON();
    await expect(page.getByRole('button', { name: /^Save$/ })).toBeDisabled();
    // Move away so hovering the next control does not pause an overlapping toast.
    await page.mouse.move(0, 0);
    await expect(
      page.locator('[data-sonner-toast][data-visible="true"]'),
    ).toHaveCount(0);
    return body;
  };
  const body = await save();
  expect(body.plugin_processors).toEqual([
    { processor_uuid: 'processor-new', enabled: true },
  ]);
  expect(body.event_bindings).toEqual([]);
  await page.reload();
  await expect(section).toContainText('Customer welcome');
  await expect(
    section.getByRole('link', { name: 'View logs' }),
  ).toHaveAttribute('href', '/home/agents?id=processor-new&tab=logs');
  await section
    .getByRole('switch', { name: 'Enable Customer welcome' })
    .click();
  expect((await save()).plugin_processors).toEqual([
    { processor_uuid: 'processor-new', enabled: false },
  ]);
  await section
    .getByRole('button', { name: 'Unbind Customer welcome' })
    .click();
  await section.getByRole('button', { name: 'Add plugin processor' }).click();
  await dialog.getByRole('checkbox', { name: /Customer welcome/ }).check();
  await dialog
    .getByRole('button', { name: 'Add plugin processor', exact: true })
    .click();
  await expect(section).toContainText('Customer welcome');
  expect(processors).toHaveLength(1);

  processors.push({
    ...processors[0],
    uuid: 'processor-observer',
    name: 'Event observer',
  });
  await page.reload();
  await section
    .getByRole('button', { name: 'Unbind Customer welcome' })
    .click();
  await section.getByRole('button', { name: 'Add plugin processor' }).click();
  await dialog.getByRole('checkbox', { name: /Customer welcome/ }).check();
  await dialog.getByRole('checkbox', { name: /Event observer/ }).check();
  await dialog
    .getByRole('button', { name: 'Add plugin processor', exact: true })
    .click();
  expect((await save()).plugin_processors).toEqual([
    { processor_uuid: 'processor-new', enabled: true },
    { processor_uuid: 'processor-observer', enabled: true },
  ]);
});

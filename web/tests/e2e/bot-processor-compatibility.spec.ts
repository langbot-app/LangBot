import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

const warning = /This bot only supports some of the subscribed events/;
const definitions = [
  { name: 'Messages only', patterns: ['message.received'] },
  {
    name: 'Community helper',
    patterns: [
      'group.member_joined',
      'message.received',
      'friend.request_received',
    ],
  },
  { name: 'Group observer', patterns: ['group.*'] },
  { name: 'All observer', patterns: ['*'] },
];

async function setup(page: Page, events?: string[]) {
  await installLangBotApiMocks(page, { authenticated: true });
  const components = definitions.map(({ name, patterns }, index) => ({
    id: `plugin:qa/events/component-${index}`,
    label: { en_US: name },
    supported_event_patterns: patterns,
    config_schema: [],
    plugin_author: 'qa',
    plugin_name: 'events',
  }));
  const agents = components.map((component, index) => ({
    uuid: `processor-${index}`,
    name: definitions[index].name,
    kind: 'event_processor',
    component_ref: component.id,
    supported_event_patterns: component.supported_event_patterns,
    config: {},
  }));
  await page.route('**/api/v1/agents**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown;
    if (path.endsWith('/_/metadata')) data = { event_processors: components };
    else if (path === '/api/v1/agents' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON();
      agents.push({
        ...payload,
        uuid: 'processor-new',
        supported_event_patterns: components.find(
          (item) => item.id === payload.component_ref,
        )!.supported_event_patterns,
      });
      data = { uuid: 'processor-new', kind: 'event_processor' };
    } else if (path === '/api/v1/agents') data = { agents };
    else return route.fallback();
    await route.fulfill({ json: { code: 0, data } });
  });
  await page.route('**/api/v1/platform/adapters', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          adapters: [
            {
              name: 'playwright-adapter',
              label: { en_US: 'Message adapter' },
              description: { en_US: 'Messages' },
              spec: {
                config: [],
                ...(events ? { supported_events: events } : {}),
              },
            },
            {
              name: 'full-adapter',
              label: { en_US: 'Community adapter' },
              description: { en_US: 'Community events' },
              spec: {
                config: [],
                supported_events: [
                  'message.received',
                  'group.member_joined',
                  'friend.request_received',
                ],
              },
            },
          ],
        },
      },
    }),
  );
  await page.goto('/home/bots?id=compatibility-bot');
  await expect(
    page.getByRole('button', { name: 'Add plugin processor', exact: true }),
  ).toBeVisible();
}

test('partial support warns in existing choices and saved bindings, and changes with adapter', async ({
  page,
}) => {
  await setup(page, ['message.received']);
  await page
    .getByRole('button', { name: 'Add plugin processor', exact: true })
    .click();
  const dialog = page.getByRole('dialog');
  const community = dialog
    .locator('label')
    .filter({ hasText: 'Community helper' });
  await expect(community.getByRole('status')).toContainText(
    '(Message received)',
  );
  await expect(community.getByRole('status')).not.toContainText(
    'Member joined',
  );
  await expect(community.getByRole('listitem')).toHaveText([
    'Message received',
    'Member joined group',
    'Friend request received',
  ]);
  for (const pattern of ['group.member_joined', 'friend.request_received']) {
    const event = community.getByTitle(pattern, { exact: true });
    await expect(event).toHaveClass(/text-amber-/);
    await expect(event.locator('svg')).toHaveCount(1);
  }
  await expect(
    community.getByTitle('message.received', { exact: true }),
  ).not.toHaveClass(/text-amber-/);
  await expect(
    community.getByTitle('message.received', { exact: true }).locator('svg'),
  ).toHaveCount(0);
  await expect(
    dialog
      .locator('label')
      .filter({ hasText: 'Messages only' })
      .getByRole('status'),
  ).toHaveCount(0);
  await community.getByRole('checkbox').check();
  await dialog
    .getByRole('button', { name: 'Add plugin processor', exact: true })
    .click();
  await expect(
    page.getByRole('status').filter({ hasText: warning }),
  ).toHaveCount(1);
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.reload();
  await expect(
    page
      .getByRole('region', { name: 'Plugin processor', exact: true })
      .getByRole('listitem'),
  ).toHaveText([
    'Message received',
    'Member joined group',
    'Friend request received',
  ]);
  await expect(
    page.getByRole('status').filter({ hasText: warning }),
  ).toHaveCount(1);
  await page.getByRole('combobox').first().click();
  await page
    .getByRole('option', { name: 'Community adapter', exact: true })
    .click();
  await expect(
    page.getByRole('status').filter({ hasText: warning }),
  ).toHaveCount(0);
  await page.getByRole('combobox').first().click();
  await page
    .getByRole('option', { name: 'Message adapter', exact: true })
    .click();
  await expect(
    page.getByRole('status').filter({ hasText: warning }),
  ).toHaveCount(1);
});

test('new component choices warn for missing and wildcard events but allow creation and binding', async ({
  page,
}, testInfo) => {
  await setup(page);
  await page
    .getByRole('button', { name: 'Add plugin processor', exact: true })
    .click();
  const dialog = page.getByRole('dialog');
  await dialog
    .getByRole('tab', { name: 'New configuration', exact: true })
    .click();
  for (const name of ['Community helper', 'Group observer', 'All observer']) {
    await expect(
      dialog
        .getByRole('button', { name: new RegExp(name) })
        .getByRole('status'),
    ).toContainText(warning);
  }
  await expect(
    dialog.getByRole('button', { name: /Group observer/ }).getByRole('status'),
  ).toContainText('(None)');
  await expect(
    dialog.getByRole('button', { name: /All observer/ }).getByRole('status'),
  ).toContainText('(Message received)');
  const community = dialog.getByRole('button', { name: /Community helper/ });
  await expect(community.getByRole('listitem')).toHaveText([
    'Message received',
    'Member joined group',
    'Friend request received',
  ]);
  await expect(
    community.getByTitle('group.member_joined', { exact: true }).locator('svg'),
  ).toHaveCount(1);
  await expect(
    dialog.getByRole('button', { name: /Messages only/ }).getByRole('status'),
  ).toHaveCount(0);
  await dialog.getByRole('button', { name: /Community helper/ }).click();
  await dialog.screenshot({
    path: testInfo.outputPath('compatibility-dialog.png'),
  });
  await dialog
    .getByRole('button', { name: 'Create and bind', exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole('status').filter({ hasText: warning }),
  ).toHaveCount(1);
  await page
    .locator('section[aria-labelledby="plugin-subscriptions-title"]')
    .screenshot({ path: testInfo.outputPath('compatibility-bindings.png') });
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.reload();
  await expect(
    page.getByRole('status').filter({ hasText: warning }),
  ).toHaveCount(1);
});

test('fully supported processor choices have no compatibility warning', async ({
  page,
}) => {
  await setup(page, [
    'message.received',
    'group.member_joined',
    'friend.request_received',
  ]);
  await page
    .getByRole('button', { name: 'Add plugin processor', exact: true })
    .click();
  const dialog = page.getByRole('dialog');
  await expect(
    dialog
      .locator('label')
      .filter({ hasText: 'Community helper' })
      .getByRole('status'),
  ).toHaveCount(0);
  await dialog
    .getByRole('tab', { name: 'New configuration', exact: true })
    .click();
  await expect(
    dialog.getByRole('button', { name: /Community helper/ }),
  ).toBeVisible();
  await expect(
    dialog
      .getByRole('button', { name: /Community helper/ })
      .getByRole('status'),
  ).toHaveCount(0);
});

for (const events of [
  undefined,
  ['message.received'],
  ['message.received', 'message.edited'],
]) {
  test(`other events entry follows adapter events: ${events?.join(',') ?? 'legacy'}`, async ({
    page,
  }) => {
    await setup(page, events);
    await page
      .getByRole('button', { name: 'Add behavior', exact: true })
      .click();
    const entry = page.getByRole('menuitem', {
      name: /Configure another event/,
    });
    if (events?.includes('message.edited')) {
      await expect(entry).toBeVisible();
      await entry.hover();
      await expect(
        page.getByRole('menuitem', { name: /Message edited/ }),
      ).toBeVisible();
    } else {
      await expect(entry).toHaveCount(0);
      await expect(
        page.getByRole('menuitem', { name: /Reply to messages/ }),
      ).toBeVisible();
    }
  });
}

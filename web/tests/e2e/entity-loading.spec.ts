import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

async function setup(page: Page) {
  await page.routeWebSocket('**/api/v1/pipelines/**/ws/connect**', (ws) => {
    ws.onMessage((raw) => {
      if (JSON.parse(String(raw)).type === 'authenticate')
        ws.send(
          JSON.stringify({
            type: 'connected',
            connection_id: 'loading-test',
            session_type: 'person',
          }),
        );
    });
  });
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAdapterEvents: true,
    withRunnerToolSelector: true,
  });
  await page.route('**/api/v1/plugins/qa/loading**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = path.endsWith('/config')
      ? { config: {} }
      : path.endsWith('/readme')
        ? { readme: '# Loaded documentation' }
        : {
            plugin: {
              manifest: {
                manifest: {
                  metadata: {
                    author: 'qa',
                    name: 'loading',
                    label: { en_US: 'Loading test plugin' },
                    description: { en_US: 'Test' },
                  },
                  spec: { config: [] },
                },
              },
              components: [],
            },
          };
    await route.fulfill({ json: { code: 0, data } });
  });
  await page.route('**/api/v1/agents/processor-loading', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          agent: {
            uuid: 'processor-loading',
            kind: 'event_processor',
            name: 'Loading test processor',
            config: {},
            supported_event_patterns: [],
          },
        },
      },
    }),
  );
  await page.route('**/api/v1/agents/processor-loading/runs**', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: { items: [], has_more: false, next_cursor: null },
      },
    }),
  );
}

const cases = [
  {
    name: 'plugin documentation',
    url: '/home/extensions?id=qa/loading',
    endpoint: '/plugins/qa/loading/readme?**',
    form: '[data-slot="card-title"]',
    readyText: 'Loaded documentation',
  },
  {
    name: 'bot adapters',
    url: '/home/bots?id=bot-loading',
    endpoint: '/platform/adapters',
    form: '#bot-form',
  },
  {
    name: 'processor run history',
    url: '/home/agents?id=processor-loading',
    endpoint: '/agents/processor-loading/runs',
    form: '#event-processor-form',
  },
  {
    name: 'skill file list',
    url: '/home/skills?id=skill-loading',
    endpoint: '/skills/skill-loading/files?**',
    form: '#skill-form',
    readyText: 'SKILL.md',
  },

  {
    name: 'bot details',
    url: '/home/bots?id=bot-loading',
    endpoint: '/platform/bots/bot-loading',
    form: '#bot-form',
  },
  {
    name: 'agent details',
    url: '/home/agents?id=agent-loading',
    endpoint: '/agents/agent-loading',
    form: '#agent-form',
  },
  {
    name: 'pipeline details',
    url: '/home/agents?id=pipeline-loading',
    endpoint: '/pipelines/pipeline-loading',
    form: '#pipeline-form',
  },
  {
    name: 'legacy pipeline route',
    url: '/home/pipelines?id=pipeline-loading',
    endpoint: '/pipelines/pipeline-loading',
    form: '#pipeline-form',
  },
  {
    name: 'plugin processor details',
    url: '/home/agents?id=processor-loading',
    endpoint: '/agents/processor-loading',
    form: '#event-processor-form',
  },
  {
    name: 'knowledge base details',
    url: '/home/knowledge?id=kb-loading',
    endpoint: '/knowledge/bases/kb-loading',
    form: '#kb-form',
  },
  {
    name: 'MCP details',
    url: '/home/mcp?id=mcp-loading',
    endpoint: '/mcp/servers/mcp-loading',
    form: '#mcp-form',
  },
  {
    name: 'skill details',
    url: '/home/skills?id=skill-loading',
    endpoint: '/skills/skill-loading',
    form: '#skill-form',
  },
  {
    name: 'plugin details',
    url: '/home/extensions?id=qa/loading',
    endpoint: '/plugins/qa/loading',
    form: '[data-slot="card-title"]',
  },
  {
    name: 'agent metadata after runtime health',
    url: '/home/agents?id=agent-loading',
    endpoint: '/agents/_/metadata',
    form: '#agent-form',
  },
  {
    name: 'pipeline metadata',
    url: '/home/agents?id=pipeline-loading',
    endpoint: '/pipelines/_/metadata',
    form: '#pipeline-form',
  },
  {
    name: 'processor metadata',
    url: '/home/agents?id=processor-loading',
    endpoint: '/agents/_/metadata',
    form: '#event-processor-form',
  },
  {
    name: 'knowledge engines',
    url: '/home/knowledge?id=kb-loading',
    endpoint: '/knowledge/engines',
    form: '#kb-form',
  },
  {
    name: 'plugin configuration',
    url: '/home/extensions?id=qa/loading',
    endpoint: '/plugins/qa/loading/config',
    form: '[data-slot="card-title"]',
    readyText: 'Plugin Configuration',
  },
];

for (const scenario of cases) {
  test(`${scenario.name}: loading until response arrives`, async ({ page }) => {
    await setup(page);
    let release!: () => void;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    let requested = false;
    await page.route(`**/api/v1${scenario.endpoint}`, async (route) => {
      requested = true;
      await pending;
      await route.fallback();
    });
    try {
      await page.goto(scenario.url);
      await expect.poll(() => requested).toBe(true);
      await expect(
        page.getByRole('status').filter({ hasText: 'Loading...' }).first(),
      ).toBeVisible();
      await expect(
        page.getByText('No runners are available', { exact: true }),
      ).toHaveCount(0);
      if (scenario.name === 'agent metadata after runtime health') {
        await page.screenshot({
          path: '../../.codex-run/entity-loading-agent.png',
        });
      }
      if (!scenario.readyText)
        await expect(page.locator(scenario.form)).toHaveCount(0);
    } finally {
      release();
    }
    await expect(page.locator(scenario.form).first()).toBeAttached();
    await expect(
      page.getByRole('status').filter({ hasText: 'Loading...' }),
    ).toHaveCount(0);
  });

  test(`${scenario.name}: failed request can be retried`, async ({ page }) => {
    await setup(page);
    let fail = true;
    await page.route(`**/api/v1${scenario.endpoint}`, async (route) => {
      if (fail)
        await route.fulfill({
          status: 503,
          json: {
            code: -1,
            msg: 'Temporarily unavailable',
            message: 'Temporarily unavailable',
          },
        });
      else await route.fallback();
    });
    await page.goto(scenario.url);
    const error = page
      .getByRole('alert')
      .filter({ hasText: 'Failed to load. Please try again.' });
    await expect(error).toBeVisible();
    fail = false;
    await error.getByRole('button', { name: 'Retry', exact: true }).click();
    await expect(error).toHaveCount(0);
    await expect(page.locator(scenario.form).first()).toBeAttached();
    await expect(
      page.getByRole('status').filter({ hasText: 'Loading...' }),
    ).toHaveCount(0);
  });
}

test('completed empty metadata displays the genuine empty state', async ({
  page,
}) => {
  await setup(page);
  await page.route('**/api/v1/agents/_/metadata', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: { runner_config: null, platform_tools: [], host_tools: [] },
      },
    }),
  );
  await page.goto('/home/agents?id=agent-empty');
  await expect(
    page.getByText('No runners are available', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('status').filter({ hasText: 'Loading...' }),
  ).toHaveCount(0);
});

test('switching bots resets the form and ignores an old response', async ({
  page,
}) => {
  await setup(page);
  await page.route('**/api/v1/platform/bots', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          bots: ['bot-first', 'bot-second'].map((uuid) => ({
            uuid,
            name: uuid,
            adapter: 'aiocqhttp',
            enable: true,
          })),
        },
      },
    }),
  );
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  let requested = false;
  let responded = false;
  await page.route('**/api/v1/platform/bots/bot-second', async (route) => {
    requested = true;
    await pending;
    await route.fallback();
    responded = true;
  });
  await page.goto('/home/bots?id=bot-first');
  await expect(page.locator('#bot-form')).toBeVisible();
  try {
    await page.locator('a[href="/home/bots?id=bot-second"]').click();
    await expect.poll(() => requested).toBe(true);
    await expect(page.locator('#bot-form')).toHaveCount(0);
    await expect(
      page.getByRole('status').filter({ hasText: 'Loading...' }),
    ).toBeVisible();
    await page.locator('a[href="/home/bots?id=bot-first"]').click();
    await expect(page.locator('#bot-form')).toBeVisible();
  } finally {
    release();
  }
  await expect.poll(() => responded).toBe(true);
  await expect(
    page.getByRole('heading', { name: 'bot-first', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'bot-second', exact: true }),
  ).toHaveCount(0);
});

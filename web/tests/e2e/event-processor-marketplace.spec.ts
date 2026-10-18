import { test, expect } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

for (const scenario of ['install', 'retry', 'reload'] as const) {
  test(`event processor marketplace ${scenario}: filters usage and selects registered component`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    const ref = 'plugin:qa/events/default';
    let installed = false;
    let finish = scenario !== 'reload';
    let installs = 0;
    let registrations = 0;
    const requests: Record<string, unknown>[] = [];
    const descriptor = {
      id: ref,
      plugin_author: 'qa',
      plugin_name: 'events',
      label: { en_US: 'Event handler' },
      supported_event_patterns: ['group.member_joined'],
      config_schema: [
        {
          name: 'greeting',
          type: 'string',
          label: { en_US: 'Greeting' },
          default: 'Welcome',
          required: true,
        },
      ],
    };
    let processor = {
      uuid: 'event-market',
      kind: 'event_processor',
      name: 'Event marketplace',
      component_ref: '',
      config: {},
      supported_event_patterns: [],
    };
    await page.route('**/api/v1/agents**', async (route) => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown;
      if (path.endsWith('/_/metadata')) {
        if (installed) registrations++;
        data = {
          event_processors: installed && registrations > 1 ? [descriptor] : [],
          kinds: [],
          platform_tools: [],
        };
      } else if (path.endsWith('/runs')) data = { items: [], has_more: false };
      else if (path.endsWith('/event-market')) {
        if (route.request().method() === 'PUT')
          processor = { ...processor, ...route.request().postDataJSON() };
        data = { agent: processor };
      } else return route.fallback();
      await route.fulfill({ json: { code: 0, data } });
    });
    await page.route('**/api/v1/marketplace/**', async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (!path.endsWith('/search')) return route.fallback();
      requests.push(route.request().postDataJSON());
      const plugin = (
        name: string,
        usages?: string[],
        components = { Runner: 1 },
      ) => ({
        author: 'qa',
        name,
        label: { en_US: name },
        description: { en_US: name + ' description' },
        latest_version: '1.0.0',
        type: 'plugin',
        components,
        runner_usages: usages,
        install_count: 0,
      });
      await route.fulfill({
        json: {
          code: 0,
          data: {
            total: 5,
            [path.includes('/extensions/') ? 'extensions' : 'plugins']: [
              plugin('events', ['event']),
              plugin('agent-only', ['agent']),
              plugin('mixed', ['agent', 'event']),
              plugin('unknown'),
              plugin('knowledge-only', ['event'], {
                KnowledgeEngine: 1,
              } as any),
            ],
          },
        },
      });
    });
    await page.route('**/api/v1/plugins/install/marketplace', async (route) => {
      installs++;
      expect(route.request().postDataJSON()).toEqual({
        plugin_author: 'qa',
        plugin_name: 'events',
        plugin_version: '1.0.0',
      });
      await route.fulfill({ json: { code: 0, data: { task_id: installs } } });
    });
    await page.route('**/api/v1/system/tasks/*', async (route) => {
      const failed = scenario === 'retry' && installs === 1;
      installed = finish && !failed;
      await route.fulfill({
        json: {
          code: 0,
          data: {
            id: installs,
            name: 'plugin-install-marketplace',
            runtime: {
              done: finish,
              exception: failed ? 'Download failed' : null,
            },
            task_context: {
              current_action: 'Downloading',
              metadata: { progress_percent: 25 },
            },
          },
        },
      });
    });
    await page.goto('/home/agents?id=event-market');
    const select = page.getByRole('combobox', {
      name: 'Plugin processor',
      includeHidden: true,
    });
    await select.click();
    const install = page.getByRole('button', {
      name: 'Install events',
      exact: true,
    });
    await expect(install).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Install mixed', exact: true }),
    ).toBeVisible();
    for (const excluded of ['agent-only', 'unknown', 'knowledge-only'])
      await expect(
        page.getByRole('button', { name: `Install ${excluded}`, exact: true }),
      ).toHaveCount(0);
    expect(requests.length).toBeGreaterThan(0);
    for (const request of requests)
      expect(request).toMatchObject({
        component_filter: 'Runner',
        runner_usage: 'event',
        type_filter: 'plugin',
      });
    await install.click();
    if (scenario === 'retry') {
      await expect(
        page
          .getByRole('alert', { includeHidden: true })
          .filter({ hasText: 'Download failed' }),
      ).toBeVisible();
      await install.click();
    }
    if (scenario === 'reload') {
      await expect.poll(() => installs).toBe(1);
      await expect
        .poll(() =>
          page.evaluate(() =>
            Object.keys(sessionStorage).some((key) =>
              key.includes('event-processor:event-market'),
            ),
          ),
        )
        .toBe(true);
      finish = true;
      await page.reload();
    }
    await expect(select).toContainText('Event handler', { timeout: 20000 });
    await page.keyboard.press('Escape');
    await expect(page.locator('input[name="greeting"]')).toHaveValue('Welcome');
    expect(installs).toBe(scenario === 'retry' ? 2 : 1);
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect.poll(() => processor.component_ref).toBe(ref);
  });
}

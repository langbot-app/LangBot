import { expect, test } from '@playwright/test';
import {
  installLangBotApiMocks,
  pipelineMetadata,
} from './fixtures/langbot-api';

const runnerId = 'plugin:langbot-team/LocalAgent/default';
const ok = (data: unknown) => JSON.stringify({ code: 0, message: 'ok', data });

for (const failsFirst of [false, true]) {
  test(`prepares Local Agent before enabling the bot${failsFirst ? ' after an installation retry' : ''}`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      withAdapterEvents: true,
    });
    let installed = false;
    let completeInstall = false;
    let installCount = 0;
    let modelCount = 0;
    let messageReceived = false;
    const order: string[] = [];
    const configs: Record<string, any>[] = [];
    await page.route('**/api/v1/pipelines/_/metadata', async (route) => {
      const metadata = pipelineMetadata();
      if (!installed) metadata.configs[0].stages = [];
      else {
        const model = metadata.configs[0].stages.find(
          (stage) => stage.name === runnerId,
        )!.config[0];
        model.default = { primary: '', fallbacks: [] } as never;
      }
      await route.fulfill({
        contentType: 'application/json',
        body: ok(metadata),
      });
    });
    await page.route(
      '**/api/v1/marketplace/plugins/langbot-team/LocalAgent',
      async (route) => {
        await route.fulfill({
          contentType: 'application/json',
          body: ok({
            plugin: {
              author: 'langbot-team',
              name: 'LocalAgent',
              label: { en_US: 'Local Agent' },
              latest_version: '0.1.7',
            },
          }),
        });
      },
    );
    await page.route('**/api/v1/plugins/install/marketplace', async (route) => {
      installCount += 1;
      expect(route.request().postDataJSON()).toEqual({
        plugin_author: 'langbot-team',
        plugin_name: 'LocalAgent',
        plugin_version: '0.1.7',
      });
      order.push('install');
      await route.fulfill({
        contentType: 'application/json',
        body: ok({ task_id: installCount }),
      });
    });
    await page.route('**/api/v1/system/tasks/*', async (route) => {
      const failed = failsFirst && installCount === 1;
      installed = !failed && completeInstall;
      await route.fulfill({
        contentType: 'application/json',
        body: ok({
          id: installCount,
          name: 'plugin-install-marketplace',
          label: 'LocalAgent',
          runtime: {
            done: failed || completeInstall,
            exception: failed ? 'Download failed: connection reset' : null,
          },
          task_context: {
            current_action: 'Downloading package',
            metadata: { progress_percent: 25 },
          },
        }),
      });
    });
    await page.route(
      '**/api/v1/system/wizard/recommended-model',
      async (route) => {
        modelCount += 1;
        order.push('model');
        await route.fulfill({
          contentType: 'application/json',
          body: ok({ uuid: 'recommended-model', name: 'Recommended' }),
        });
      },
    );
    await page.route('**/api/v1/platform/bots/*/logs', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: ok({
          logs: messageReceived
            ? [
                {
                  seq_id: 1,
                  timestamp: Date.now() / 1000,
                  level: 'info',
                  text: 'Received message',
                  images: [],
                  message_session_id: 'person_123',
                },
              ]
            : [],
          total_count: messageReceived ? 1 : 0,
        }),
      });
    });
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname;
      if (
        request.method() === 'PUT' &&
        path === '/api/v1/pipelines/pipeline-1'
      ) {
        configs.push(request.postDataJSON().config);
        order.push('configure');
      }
      if (
        request.method() === 'PUT' &&
        path === '/api/v1/platform/bots/bot-1' &&
        request.postDataJSON().enable
      )
        order.push('enable');
    });
    await page.goto('/wizard');
    await page.getByText('Playwright Adapter', { exact: true }).click();
    await page.getByRole('button', { name: 'Confirm, Create Bot' }).click();
    await page.getByRole('button', { name: 'Save & Enable Bot' }).click();
    if (failsFirst) {
      await expect(
        page.getByText(/Download failed: connection reset/),
      ).toBeVisible();
      expect(order).toEqual(['install']);
      await expect(page.getByRole('button', { name: 'Next' })).toBeDisabled();
      await page.getByRole('button', { name: 'Save & Enable Bot' }).click();
    }
    const preparing = page.getByRole('button', {
      name: /Preparing default AI.*23%/,
    });
    await expect(preparing).toBeDisabled();
    await expect(preparing.locator('span[aria-hidden="true"]')).toHaveAttribute(
      'style',
      'width: 23%;',
    );
    await expect(page.getByRole('progressbar')).toHaveCount(0);
    completeInstall = true;
    await expect(
      page.getByRole('button', { name: 'Re-save Configuration' }),
    ).toBeVisible();
    expect(order.slice(-4)).toEqual([
      'install',
      'model',
      'configure',
      'enable',
    ]);
    expect(configs[0].ai.runner.id).toBe(runnerId);
    expect(configs[0].ai.runner_config[runnerId].model.primary).toBe(
      'recommended-model',
    );
    await page.getByRole('button', { name: 'Re-save Configuration' }).click();
    await expect.poll(() => configs.length).toBe(2);
    expect(installCount).toBe(failsFirst ? 2 : 1);
    expect(modelCount).toBe(1);
    messageReceived = true;
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(
      page.getByText('Use the default setup', { exact: true }),
    ).toBeVisible();
    await expect(page.getByText('Local Agent', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await expect(
      page.getByRole('button', { name: 'Back to Workbench' }),
    ).toBeVisible();
    expect(configs.length).toBe(2);
  });
}

test('uses a custom model in the existing Local Agent pipeline', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAdapterEvents: true,
  });
  await page.route('**/api/v1/platform/bots/*/logs', async (route) => {
    await route.fulfill({
      json: {
        code: 0,
        data: {
          logs: [
            {
              seq_id: 1,
              timestamp: Date.now() / 1000,
              level: 'info',
              text: 'Received message',
              images: [],
              message_session_id: 'person_123',
            },
          ],
          total_count: 1,
        },
      },
    });
  });
  await page.route('**/api/v1/provider/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/requesters'))
      return route.fulfill({
        json: {
          code: 0,
          data: {
            requesters: [
              {
                name: 'openai',
                label: { en_US: 'OpenAI API' },
                description: { en_US: '' },
                spec: {
                  provider_category: 'manufacturer',
                  support_type: ['llm'],
                  config: [
                    { name: 'base_url', default: 'https://api.openai.com/v1' },
                  ],
                },
              },
            ],
          },
        },
      });
    if (path.endsWith('/providers') && route.request().method() === 'POST')
      return route.fulfill({
        json: { code: 0, data: { uuid: 'own-provider' } },
      });
    if (path.endsWith('/scan-models'))
      return route.fulfill({ json: { code: 0, data: { models: [] } } });
    if (path.endsWith('/models/llm') && route.request().method() === 'POST')
      return route.fulfill({ json: { code: 0, data: { uuid: 'own-model' } } });
    await route.fallback();
  });
  await page.goto('/wizard');
  await page.getByText('Playwright Adapter', { exact: true }).click();
  await page.getByRole('button', { name: 'Confirm, Create Bot' }).click();
  await page.getByRole('button', { name: 'Save & Enable Bot' }).click();
  await page.getByRole('button', { name: 'Next' }).click();
  await page.getByText('Use My Own Model', { exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Use Selected Model & Finish' }),
  ).toBeDisabled();
  await page.locator('input[name="name"]').fill('Wizard custom provider');
  await page
    .getByRole('button', { name: 'Select Provider Type', exact: true })
    .click();
  await page.getByRole('button', { name: /OpenAI API/ }).click();
  await page.locator('input[name="api_key"]').fill('fixture-key');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByLabel('Model ID', { exact: false }).fill('test-model');
  const update = page.waitForRequest(
    (request) =>
      request.method() === 'PUT' &&
      new URL(request.url()).pathname === '/api/v1/pipelines/pipeline-1',
  );
  await page
    .getByRole('button', { name: 'Use Selected Model & Finish' })
    .click();
  const config = (await update).postDataJSON().config;
  expect(config.ai.runner.id).toBe(runnerId);
  expect(config.ai.runner_config[runnerId].model.primary).toBe('own-model');
  await expect(
    page.getByRole('button', { name: 'Back to Workbench' }),
  ).toBeVisible();
});

test('only labels debugging Runners even when the marketplace is offline', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.route('**/api/v1/system/info', async (route) => {
    await route.fulfill({
      json: {
        code: 0,
        data: {
          version: 'fixture',
          edition: 'community',
          cloud_service_url: 'https://space.langbot.app',
          enable_marketplace: true,
          wizard_status: 'none',
          wizard_progress: {
            step: 2,
            created_bot_uuid: 'bot-1',
            created_pipeline_uuid: 'pipeline-1',
            selected_adapter: 'test',
            bot_saved: true,
            message_received: true,
          },
        },
      },
    });
  });
  const plugins = [
    { name: 'local', label: 'Local Runner', debug: false },
    { name: 'debug', label: 'Debug Runner', debug: true },
  ];
  await page.route('**/api/v1/plugins', async (route) => {
    await route.fulfill({
      json: {
        code: 0,
        data: {
          plugins: plugins.map((plugin) => ({
            manifest: {
              manifest: {
                metadata: {
                  author: 'qa',
                  name: plugin.name,
                  description: { en_US: `${plugin.label} description` },
                },
              },
            },
            debug: plugin.debug,
          })),
        },
      },
    });
  });
  await page.route('**/api/v1/pipelines/_/metadata', async (route) => {
    const metadata = pipelineMetadata();
    const selector = metadata.configs[0].stages[0].config[0];
    if (!('options' in selector))
      throw new Error('Missing Runner options in fixture');
    const options = selector.options;
    for (const plugin of plugins) {
      options.push({
        name: `plugin:qa/${plugin.name}/default`,
        label: { en_US: plugin.label, zh_Hans: plugin.label },
      });
    }
    await route.fulfill({ json: { code: 0, data: metadata } });
  });
  await page.route('**/api/v1/marketplace/**', async (route) => {
    await route.fulfill({
      status: 503,
      json: { code: 503, msg: 'Marketplace offline' },
    });
  });
  await page.goto('/wizard');
  await page
    .getByRole('radio', { name: 'Connect an External Agent', exact: true })
    .click();
  const local = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'Local Runner' });
  const debug = page
    .locator('[data-slot="card"]')
    .filter({ hasText: 'Debug Runner' });
  await expect(local.getByText('Installed', { exact: true })).toHaveCount(0);
  await expect(debug.getByText('Debugging', { exact: true })).toBeVisible();
  await expect(debug.getByText('Installed', { exact: true })).toHaveCount(0);
  await debug.getByRole('button', { name: 'Use This Runner' }).click();
  await expect(
    page
      .locator('[data-slot="card"]')
      .filter({ hasText: 'Debug Runner' })
      .getByText('Debugging', { exact: true }),
  ).toBeVisible();
});

test('shows installation progress inside the matching card button and recovers after failure', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await installLangBotApiMocks(page, { authenticated: true });
  await page.route('**/api/v1/system/info', async (route) => {
    await route.fulfill({
      json: {
        code: 0,
        data: {
          version: 'fixture',
          edition: 'community',
          cloud_service_url: 'https://space.langbot.app',
          enable_marketplace: true,
          wizard_status: 'none',
          wizard_progress: {
            step: 2,
            created_bot_uuid: 'bot-1',
            created_pipeline_uuid: 'pipeline-1',
            selected_adapter: 'test',
            bot_saved: true,
            message_received: true,
          },
        },
      },
    });
  });
  const plugin = (name: string) => ({
    name,
    author: 'qa',
    label: { en_US: name },
    description: { en_US: 'Test Runner' },
    components: { Runner: 1 },
    runner_usages: ['agent'],
    latest_version: '1.0.0',
    install_count: 0,
    type: 'plugin',
  });
  await page.route(
    '**/api/v1/marketplace/extensions/search**',
    async (route) => {
      await route.fulfill({
        json: {
          code: 0,
          data: {
            extensions: [plugin('ProgressRunner'), plugin('OtherRunner')],
            total: 2,
          },
        },
      });
    },
  );
  let attempt = 0;
  let phase: 'download' | 'deps' | 'failed' | 'done' = 'download';
  let registered = false;
  await page.route('**/api/v1/plugins/install/marketplace', async (route) => {
    attempt += 1;
    phase = 'download';
    await route.fulfill({ json: { code: 0, data: { task_id: attempt } } });
  });
  await page.route('**/api/v1/system/tasks/*', async (route) => {
    await route.fulfill({
      json: {
        code: 0,
        data: {
          id: attempt,
          name: 'plugin-install-marketplace',
          label: 'ProgressRunner',
          runtime: {
            done: phase === 'done' || phase === 'failed',
            exception:
              phase === 'failed' ? 'Dependency installation failed' : null,
          },
          task_context: {
            current_action:
              phase === 'download'
                ? 'Downloading package'
                : 'Installing dependencies',
            metadata: { progress_percent: phase === 'download' ? 24 : 64 },
          },
        },
      },
    });
  });
  await page.route('**/api/v1/pipelines/_/metadata', async (route) => {
    const metadata = pipelineMetadata();
    const selector = metadata.configs[0].stages[0].config[0];
    if ('options' in selector)
      selector.options.push({
        name: 'plugin:qa/ExistingRunner/default',
        label: { en_US: 'ExistingRunner', zh_Hans: 'ExistingRunner' },
      });
    metadata.configs[0].stages.push({
      name: 'plugin:qa/ExistingRunner/default',
      label: { en_US: 'ExistingRunner', zh_Hans: 'ExistingRunner' },
      config: [
        {
          name: 'api-key',
          label: { en_US: 'API Key', zh_Hans: 'API Key' },
          type: 'string',
          required: true,
          default: '',
        },
      ],
    } as (typeof metadata.configs)[0]['stages'][number]);
    if (registered && 'options' in selector)
      selector.options.push({
        name: 'plugin:qa/ProgressRunner/default',
        label: { en_US: 'ProgressRunner', zh_Hans: 'ProgressRunner' },
      });
    await route.fulfill({ json: { code: 0, data: metadata } });
  });
  await page.goto('/wizard');
  await page
    .getByRole('radio', { name: 'Connect an External Agent', exact: true })
    .click();
  const card = page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByText('ProgressRunner', { exact: true }) });
  const other = page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByText('OtherRunner', { exact: true }) });
  const back = page.getByRole('button', {
    name: /Back to (options|list)/,
    exact: true,
  });
  await expect(back).toBeVisible();
  const pickerBounds = await back.boundingBox();
  await page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByText('ExistingRunner', { exact: true }) })
    .getByRole('button', { name: 'Use This Runner' })
    .click();
  await expect(page.getByText('ExistingRunner Configuration')).toBeVisible();
  await expect
    .poll(async () => (await back.boundingBox())?.x)
    .toBeCloseTo(pickerBounds!.x, 0);
  await expect
    .poll(async () => (await back.boundingBox())?.y)
    .toBeCloseTo(pickerBounds!.y, 0);
  await page.getByRole('textbox').fill('unsaved-test-key');
  await page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByText('ExistingRunner', { exact: true }) })
    .getByRole('button', { name: 'Use This Runner' })
    .click();
  await expect(page.getByRole('textbox')).toHaveValue('unsaved-test-key');
  await card
    .getByRole('button', { name: 'Install & Continue', exact: true })
    .click();
  await expect(
    card.getByRole('button', { name: /Downloading.*24%/ }),
  ).toBeDisabled();
  await expect(page.getByRole('progressbar')).toHaveCount(0);
  await expect(
    other.getByRole('button', { name: 'Install & Continue', exact: true }),
  ).toBeDisabled();
  phase = 'deps';
  await expect(
    card.getByRole('button', { name: /Installing Dependencies.*64%/ }),
  ).toBeDisabled();
  phase = 'failed';
  await card
    .getByRole('button', { name: 'Failed · Retry', exact: true })
    .click();
  await expect(
    card.getByRole('button', { name: /Downloading.*24%/ }),
  ).toBeDisabled();
  phase = 'done';
  await expect(
    card.getByRole('button', {
      name: /Starting and refreshing components.*95%/,
    }),
  ).toBeDisabled();
  registered = true;
  await expect(
    card.getByRole('button', { name: 'Use This Runner' }),
  ).toBeEnabled();
  await expect(
    card.getByRole('button', { name: 'Use This Runner' }),
  ).toHaveAttribute('aria-pressed', 'true');
  await expect(
    other.getByRole('button', { name: 'Install & Continue' }),
  ).toBeEnabled();
  expect(attempt).toBe(2);
});

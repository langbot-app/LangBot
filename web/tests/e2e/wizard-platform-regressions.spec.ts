import { expect, Page, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

import { installLangBotApiMocks } from './fixtures/langbot-api';

const qrPlatforms = [
  {
    platform: 'feishu',
    adapterName: 'qr-feishu',
    label: 'Feishu QR Adapter',
    apiBase: '/api/v1/platform/adapters/lark/create-app',
  },
  {
    platform: 'weixin',
    adapterName: 'qr-weixin',
    label: 'Weixin QR Adapter',
    apiBase: '/api/v1/platform/adapters/weixin/login',
  },
  {
    platform: 'dingtalk',
    adapterName: 'qr-dingtalk',
    label: 'DingTalk QR Adapter',
    apiBase: '/api/v1/platform/adapters/dingtalk/create-app',
  },
  {
    platform: 'wecombot',
    adapterName: 'qr-wecombot',
    label: 'WeCom QR Adapter',
    apiBase: '/api/v1/platform/adapters/wecombot/create-bot',
  },
  {
    platform: 'qqofficial',
    adapterName: 'qr-qqofficial',
    label: 'QQ Official QR Adapter',
    apiBase: '/api/v1/platform/adapters/qqofficial/bind',
  },
] as const;

function ok(data: unknown) {
  return JSON.stringify({
    code: 0,
    message: 'ok',
    data,
    timestamp: Date.now(),
  });
}

function adapterWithQrLogin(
  adapterName: string,
  label: string,
  platform: string,
) {
  return {
    name: adapterName,
    label: { en_US: label, zh_Hans: label },
    description: {
      en_US: 'Exercises the QR-assisted setup flow.',
      zh_Hans: '验证扫码辅助创建流程。',
    },
    spec: {
      categories: ['testing'],
      supported_events: ['message.received'],
      config: [
        {
          id: 'qr-login',
          name: 'qr-login',
          type: 'qr-code-login',
          label: { en_US: 'Create with QR code', zh_Hans: '扫码创建' },
          description: {
            en_US: 'Scan to finish creating this adapter.',
            zh_Hans: '扫码完成适配器创建。',
          },
          required: false,
          default: '',
          login_platform: platform,
        },
      ],
    },
  };
}

async function createDraftBot(page: Page, adapterLabel: string) {
  await page
    .getByTestId('adapter-gallery')
    .getByRole('button', { name: new RegExp(adapterLabel) })
    .click();
  await page.locator('input[name="name"]').fill(`${adapterLabel} Bot`);
  await page.getByRole('button', { name: /^Submit$/ }).click();
  await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);
}

test.describe('wizard and QR platform regressions', () => {
  test('starts with message platforms directly and keeps legacy adapters available', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    const adapter = adapterWithQrLogin(
      'message-adapter',
      'Message Adapter',
      'feishu',
    );
    await page.route('**/api/v1/platform/adapters', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: ok({
          adapters: [
            adapter,
            adapter,
            {
              ...adapter,
              name: 'events-only',
              label: { en_US: 'Events Only' },
              spec: {
                ...adapter.spec,
                supported_events: ['group.member_joined'],
              },
            },
            {
              ...adapter,
              name: 'legacy',
              label: { en_US: 'Legacy Message Adapter' },
              spec: {
                ...adapter.spec,
                legacy: true,
                supported_events: undefined,
              },
            },
          ],
        }),
      });
    });
    await page.goto('/wizard');
    await expect(
      page.getByRole('heading', { name: 'Select a Platform' }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', {
        name: /Reply to messages|Welcome new members/,
      }),
    ).toHaveCount(0);
    await expect(
      page.getByText('Message Adapter', { exact: true }),
    ).toHaveCount(1);
    await expect(page.getByText('Events Only', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: /Legacy Adapters/i }).click();
    await expect(
      page.getByText('Legacy Message Adapter', { exact: true }),
    ).toBeVisible();
    await page.getByText('Message Adapter', { exact: true }).click();
    await expect(
      page.getByRole('button', { name: 'Confirm, Create Bot' }),
    ).toBeEnabled();
  });

  test('old non-message drafts start fresh without modifying their Agent or bot', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    await page.route('**/api/v1/system/info', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: ok({
          version: 'frontend-smoke',
          edition: 'community',
          wizard_status: 'none',
          cloud_service_url: 'https://space.langbot.app',
          enable_marketplace: true,
          wizard_progress: {
            step: 2,
            selected_scenario: 'welcome_members',
            created_bot_uuid: 'old-bot',
            selected_adapter: 'test',
          },
        }),
      });
    });
    const resourceRequests: string[] = [];
    page.on('request', (request) => {
      if (
        /\/api\/v1\/(agents|pipelines|platform\/bots)(\/[^_]|$)/.test(
          new URL(request.url()).pathname,
        ) &&
        request.method() !== 'GET'
      ) {
        resourceRequests.push(request.url());
      }
    });
    await page.goto('/wizard');
    await expect(
      page.getByRole('heading', { name: 'Select a Platform' }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Confirm, Create Bot' }),
    ).toBeDisabled();
    expect(resourceRequests).toEqual([]);
  });

  test('loads the Page Bot from the API origin, retries failures, and reopens after every save', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    let pipelineCreateCount = 0;
    let boundPipelineUuid: string | null = null;
    let backendOrigin = '';
    page.on('request', (request) => {
      const url = new URL(request.url());
      if (url.pathname === '/api/v1/platform/adapters')
        backendOrigin = url.origin;
      if (request.method() === 'POST' && url.pathname === '/api/v1/pipelines') {
        pipelineCreateCount += 1;
      }
      if (
        request.method() === 'PUT' &&
        url.pathname === '/api/v1/platform/bots/bot-1'
      ) {
        const body = request.postDataJSON() as {
          event_bindings?: Array<{
            event_pattern?: string;
            target_type?: string;
            target_uuid?: string;
          }>;
        };
        const binding = body.event_bindings?.find(
          (item) =>
            item.event_pattern === 'message.received' &&
            item.target_type === 'pipeline',
        );
        boundPipelineUuid = binding?.target_uuid ?? null;
      }
    });

    await page.route('**/api/v1/platform/adapters', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({
          adapters: [
            {
              name: 'web_page_bot',
              label: { en_US: 'Page Bot', zh_Hans: '页面机器人' },
              description: {
                en_US: 'An embeddable page bot.',
                zh_Hans: '可嵌入网页的机器人。',
              },
              spec: {
                categories: ['web'],
                supported_events: ['message.received'],
                config: [
                  {
                    id: 'title',
                    name: 'title',
                    type: 'string',
                    label: { en_US: 'Title', zh_Hans: '标题' },
                    required: false,
                    default: 'Wizard Page Bot',
                  },
                ],
              },
            },
          ],
        }),
      });
    });

    const widgetTemplate = fs.readFileSync(
      path.resolve(process.cwd(), '../src/langbot/templates/embed/widget.js'),
      'utf8',
    );
    let widgetAvailable = false;
    await page.route('**/api/v1/embed/*/widget.js?*', async (route) => {
      expect(new URL(route.request().url()).origin).toBe(backendOrigin);
      if (!widgetAvailable || !boundPipelineUuid || pipelineCreateCount === 0) {
        await route.fulfill({
          status: 404,
          contentType: 'application/javascript',
          body: '// Bot not found or not available',
        });
        return;
      }
      const origin = new URL(route.request().url()).origin;
      const source = widgetTemplate
        .replaceAll('__LANGBOT_LOCALE__', 'en_US')
        .replaceAll('__LANGBOT_BOT_UUID__', 'bot-1')
        .replaceAll('__LANGBOT_BASE_URL__', origin)
        .replaceAll('__LANGBOT_TURNSTILE_SITE_KEY__', '')
        .replaceAll('__LANGBOT_BUBBLE_ICON__', 'chat');
      await route.fulfill({
        status: 200,
        contentType: 'application/javascript',
        body: source,
      });
    });

    await page.goto('/wizard');
    await page.getByText('Page Bot', { exact: true }).click();
    await page.getByRole('button', { name: 'Confirm, Create Bot' }).click();

    const saveButton = page.getByRole('button', {
      name: /^(Save & Enable Bot|Re-save Configuration)$/,
    });
    await saveButton.click();

    await expect.poll(() => pipelineCreateCount).toBe(1);
    await expect.poll(() => boundPipelineUuid).toBe('pipeline-1');

    await expect(
      page.getByText(
        'Failed to load the test chat. Please save the configuration again to retry.',
        { exact: true },
      ),
    ).toBeVisible();
    widgetAvailable = true;
    await saveButton.click();

    const widgetRoot = page.locator('#langbot-widget-root');
    await expect(widgetRoot).toBeAttached();
    await expect
      .poll(() =>
        widgetRoot.evaluate((root) =>
          root.shadowRoot
            ?.querySelector('.lb-panel')
            ?.classList.contains('lb-visible'),
        ),
      )
      .toBe(true);
    await expect
      .poll(() =>
        widgetRoot.evaluate(
          (root) =>
            root.shadowRoot?.querySelector('.lb-test-notice')?.textContent,
        ),
      )
      .toContain('For testing only');

    await widgetRoot.evaluate((root) => {
      const minimize = root.shadowRoot?.querySelector(
        '.lb-header-btn[aria-label="Minimize"]',
      ) as HTMLButtonElement | null;
      minimize?.click();
    });
    await expect
      .poll(() =>
        widgetRoot.evaluate((root) =>
          root.shadowRoot
            ?.querySelector('.lb-panel')
            ?.classList.contains('lb-visible'),
        ),
      )
      .toBe(false);

    await saveButton.click();
    await expect.poll(() => pipelineCreateCount).toBe(1);
    await expect.poll(() => boundPipelineUuid).toBe('pipeline-1');
    await expect
      .poll(() =>
        widgetRoot.evaluate((root) =>
          root.shadowRoot
            ?.querySelector('.lb-panel')
            ?.classList.contains('lb-visible'),
        ),
      )
      .toBe(true);
  });

  test('binds HTTP Bot before its signed inbound verification request', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });

    let pipelineCreateCount = 0;
    let inboundTestCount = 0;
    let boundPipelineUuid: string | null = null;
    let savedInboundSecret = '';

    page.on('request', (request) => {
      const url = new URL(request.url());
      if (request.method() === 'POST' && url.pathname === '/api/v1/pipelines') {
        pipelineCreateCount += 1;
      }
      if (
        request.method() === 'PUT' &&
        url.pathname === '/api/v1/platform/bots/bot-1'
      ) {
        const body = request.postDataJSON() as {
          adapter_config?: { inbound_secret?: string };
          event_bindings?: Array<{
            event_pattern?: string;
            target_type?: string;
            target_uuid?: string;
          }>;
        };
        savedInboundSecret = body.adapter_config?.inbound_secret ?? '';
        const binding = body.event_bindings?.find(
          (item) =>
            item.event_pattern === 'message.received' &&
            item.target_type === 'pipeline',
        );
        boundPipelineUuid = binding?.target_uuid ?? null;
      }
    });

    await page.route('**/api/v1/platform/adapters', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({
          adapters: [
            {
              name: 'http_bot',
              label: { en_US: 'HTTP Bot', zh_Hans: 'HTTP 机器人' },
              description: {
                en_US: 'Receives signed HTTP messages.',
                zh_Hans: '接收签名的 HTTP 消息。',
              },
              spec: {
                categories: ['web'],
                supported_events: ['message.received'],
                config: [
                  {
                    id: 'signature-required',
                    name: 'signature_required',
                    type: 'boolean',
                    label: { en_US: 'Require signature', zh_Hans: '要求签名' },
                    required: false,
                    default: true,
                  },
                  {
                    id: 'webhook-url',
                    name: 'webhook_url',
                    type: 'webhook-url',
                    label: { en_US: 'Webhook URL', zh_Hans: 'Webhook 地址' },
                    required: false,
                    default: '',
                  },
                ],
              },
            },
          ],
        }),
      });
    });
    await page.route(
      '**/api/v1/platform/bots/bot-1/test-inbound',
      async (route) => {
        inboundTestCount += 1;
        expect(route.request().method()).toBe('POST');
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: ok({ accepted: true }),
        });
      },
    );

    await page.goto('/wizard');
    await page.getByText('HTTP Bot', { exact: true }).click();
    await page.getByRole('button', { name: 'Confirm, Create Bot' }).click();
    await page
      .getByRole('button', {
        name: /^(Save & Enable Bot|Re-save Configuration)$/,
      })
      .click();

    await expect.poll(() => pipelineCreateCount).toBe(1);
    await expect.poll(() => boundPipelineUuid).toBe('pipeline-1');
    await expect.poll(() => savedInboundSecret).toMatch(/^[a-f0-9]{64}$/);

    await page.getByRole('button', { name: 'Send Test' }).click();
    await expect.poll(() => inboundTestCount).toBe(1);
  });

  test('creates only a message pipeline after message verification and valid Runner configuration', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      withAdapterEvents: true,
    });
    const processorRequests: string[] = [];
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname;
      if (
        request.method() === 'POST' &&
        ['/api/v1/pipelines', '/api/v1/agents'].includes(path)
      ) {
        processorRequests.push(path);
      }
    });
    let messageReceived = false;
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
    await page.route('**/api/v1/pipelines/_/metadata', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({
          configs: [
            {
              name: 'ai',
              label: { en_US: 'AI Feature', zh_Hans: 'AI 能力' },
              stages: [
                {
                  name: 'plugin:langbot-team/LocalAgent/default',
                  config: [
                    {
                      name: 'model',
                      type: 'model-fallback-selector',
                      required: true,
                      default: { primary: 'llm-valid', fallbacks: [] },
                    },
                  ],
                },
                {
                  name: 'runner',
                  label: { en_US: 'Runtime', zh_Hans: '运行方式' },
                  config: [
                    {
                      name: 'id',
                      label: { en_US: 'Runner', zh_Hans: '运行器' },
                      type: 'select',
                      required: true,
                      default: 'external-runner',
                      options: [
                        {
                          name: 'external-runner',
                          label: {
                            en_US: 'External Runner',
                            zh_Hans: '外部运行器',
                          },
                        },
                      ],
                    },
                  ],
                },
                {
                  name: 'external-runner',
                  label: {
                    en_US: 'External Runner',
                    zh_Hans: '外部运行器',
                  },
                  config: [
                    {
                      id: 'api-key',
                      name: 'api-key',
                      label: { en_US: 'API Key', zh_Hans: 'API 密钥' },
                      type: 'secret',
                      required: true,
                      default: 'your-api-key',
                    },
                  ],
                },
              ],
            },
          ],
        }),
      });
    });

    await page.goto('/wizard');
    await page.getByText('Playwright Adapter', { exact: true }).click();
    await page.getByRole('button', { name: 'Confirm, Create Bot' }).click();
    await page.getByRole('button', { name: 'Save & Enable Bot' }).click();
    await expect(page.getByRole('button', { name: 'Next' })).toBeDisabled();
    messageReceived = true;
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(
      page.getByText('Use the default setup', { exact: true }),
    ).toBeVisible();
    await page.getByText('Connect an External Agent', { exact: true }).click();
    await page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByText('External Runner', { exact: true }) })
      .getByRole('button', { name: 'Use This Runner' })
      .click();

    const deployButton = page.getByRole('button', { name: 'Create & Deploy' });
    await expect(deployButton).toBeDisabled();
    await page.getByRole('textbox').fill('app-real-api-key');
    await expect(deployButton).toBeEnabled();
    const bindingRequest = page.waitForRequest(
      (request) =>
        request.method() === 'PUT' &&
        new URL(request.url()).pathname === '/api/v1/pipelines/pipeline-1',
    );
    await deployButton.click();
    const body = (await bindingRequest).postDataJSON();
    expect(body.config.ai.runner.id).toBe('external-runner');
    expect(body.config.ai.runner_config['external-runner']['api-key']).toBe(
      'app-real-api-key',
    );
    await expect(
      page.getByRole('button', { name: 'Back to Workbench' }),
    ).toBeVisible();
    expect(processorRequests).toEqual(['/api/v1/pipelines']);
  });

  for (const qrPlatform of qrPlatforms) {
    test(`${qrPlatform.label} requests and displays its QR code`, async ({
      page,
    }) => {
      await installLangBotApiMocks(page, { authenticated: true });
      await page.route('**/api/v1/platform/adapters', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: ok({
            adapters: [
              adapterWithQrLogin(
                qrPlatform.adapterName,
                qrPlatform.label,
                qrPlatform.platform,
              ),
            ],
          }),
        });
      });

      let cleanupRequestSeen = false;
      await page.route(`**${qrPlatform.apiBase}`, async (route) => {
        expect(route.request().method()).toBe('POST');
        expect(new URL(route.request().url()).origin).toBe(
          'http://127.0.0.1:4173',
        );
        expect(route.request().headers()['authorization']).toBe(
          'Bearer playwright-token',
        );
        expect(route.request().headers()['x-workspace-id']).toBe(
          'workspace-playwright',
        );
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: ok({
            session_id: `session-${qrPlatform.platform}`,
            qr_url: `https://example.test/qr/${qrPlatform.platform}`,
            expire_at: Math.floor(Date.now() / 1000) + 120,
          }),
        });
      });
      await page.route(`**${qrPlatform.apiBase}/**`, async (route) => {
        if (route.request().method() === 'DELETE') {
          cleanupRequestSeen = true;
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: ok({ status: 'pending' }),
        });
      });

      await page.goto('/home/bots?id=new');
      await createDraftBot(page, qrPlatform.label);
      await page.getByRole('button', { name: /^Start$/ }).click();

      const qrImage = page.getByRole('img', { name: 'QR Code' });
      await expect(qrImage).toBeVisible();
      await expect(qrImage).toHaveAttribute('src', /^data:image\/png;base64,/);

      await page.keyboard.press('Escape');
      await expect(qrImage).toHaveCount(0);
      await expect.poll(() => cleanupRequestSeen).toBe(true);
    });
  }

  test('a failed QR request remains cancellable instead of trapping the form', async ({
    page,
  }) => {
    const qrPlatform = qrPlatforms[0];
    await installLangBotApiMocks(page, { authenticated: true });
    await page.route('**/api/v1/platform/adapters', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({
          adapters: [
            adapterWithQrLogin(
              qrPlatform.adapterName,
              qrPlatform.label,
              qrPlatform.platform,
            ),
          ],
        }),
      });
    });
    await page.route(`**${qrPlatform.apiBase}`, async (route) => {
      await route.fulfill({ status: 503, body: 'unavailable' });
    });

    await page.goto('/home/bots?id=new');
    await createDraftBot(page, qrPlatform.label);
    await page.getByRole('button', { name: /^Start$/ }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('HTTP 503')).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Retry' })).toBeEnabled();
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole('button', { name: /^Save$/ })).toBeVisible();
  });
});

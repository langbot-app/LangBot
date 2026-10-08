import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

const chat = {
  uuid: 'assistant-test',
  revision: 0,
  status: 'ready',
  messages: [],
  pending: [],
  error: null,
  model_uuid: null,
  model_name: null,
};

test('sending survives model labels appearing and disappearing in stream snapshots', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (/createPortal|removeChild|createRoot/.test(message.text()))
      errors.push(message.text());
  });
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAssistant: true,
  });
  await page.route('**/api/v1/provider/providers', (route) =>
    route.fulfill({
      json: { code: 0, data: { providers: [{ uuid: 'provider' }] } },
    }),
  );
  await page.route('**/api/v1/assistant/recommended-model', (route) =>
    route.fulfill({
      json: { code: 0, data: { uuid: 'llm-valid', name: 'Recommended model' } },
    }),
  );
  let current: Record<string, unknown> = chat;
  await page.route('**/api/v1/assistant/conversations', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data:
          route.request().method() === 'POST' ? chat : { conversations: [] },
      },
    }),
  );
  await page.route(
    '**/api/v1/assistant/conversations/assistant-test',
    (route) =>
      route.fulfill({
        json: { code: 0, data: current },
      }),
  );
  let turn = 0;
  await page.route(
    '**/api/v1/assistant/conversations/*/turn/stream',
    async (route) => {
      turn += 1;
      current = {
        ...chat,
        revision: turn,
        model_uuid: 'llm-valid',
        model_name: turn === 2 ? 'Snapshot model' : null,
        messages: [{ role: 'assistant', content: `Reply ${turn}` }],
      };
      await route.fulfill({
        contentType: 'application/x-ndjson',
        body:
          JSON.stringify({ kind: 'snapshot', data: current }) +
          '\n' +
          JSON.stringify({ kind: 'completed', data: current }) +
          '\n',
      });
    },
  );
  await page.goto('/home/bots');
  const assistant = page.getByRole('dialog', { name: 'Workspace assistant' });
  const model = assistant.getByRole('combobox', { name: 'Select Model' });
  await expect(model).toContainText('Recommended model');
  for (let i = 1; i <= 3; i++) {
    await assistant.getByRole('textbox').fill(`Hello ${i}`);
    await assistant.getByRole('button', { name: 'Send', exact: true }).click();
    await expect(
      assistant.getByText(`Reply ${i}`, { exact: true }),
    ).toBeVisible();
    await expect(model).toContainText(
      i === 2 ? 'Snapshot model' : 'Valid Mock Model',
    );
  }
  expect(errors).toEqual([]);
});

test('selects the recommendation on entry and submits the visible model', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAssistant: true,
  });
  await page.route('**/api/v1/provider/providers', (route) =>
    route.fulfill({
      json: { code: 0, data: { providers: [{ uuid: 'provider' }] } },
    }),
  );
  await page.route('**/api/v1/assistant/recommended-model', (route) =>
    route.fulfill({
      json: { code: 0, data: { uuid: 'llm-valid', name: 'Recommended model' } },
    }),
  );
  await page.route('**/api/v1/assistant/conversations', (route) =>
    route.fulfill({ json: { code: 0, data: chat } }),
  );
  await page.route(
    '**/api/v1/assistant/conversations/*/turn/stream',
    async (route) => {
      expect(route.request().postDataJSON().model_uuid).toBe('llm-valid');
      const result = {
        ...chat,
        revision: 1,
        model_uuid: 'llm-valid',
        model_name: 'Recommended model',
        messages: [
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hello back' },
        ],
      };
      await route.fulfill({
        contentType: 'application/x-ndjson',
        body: JSON.stringify({ kind: 'completed', data: result }) + '\n',
      });
    },
  );
  await page.goto('/home/bots');
  const assistant = page.getByRole('dialog', { name: 'Workspace assistant' });
  await expect(
    assistant.getByRole('combobox', { name: 'Select Model' }),
  ).toContainText('Recommended model');
  await assistant.getByRole('textbox').fill('Hello');
  await assistant.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(
    assistant.getByText('Hello back', { exact: true }),
  ).toBeVisible();
});

test('late recommendation cannot overwrite manual selection, including request payload', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAssistant: true,
  });
  await page.route('**/api/v1/provider/providers', (route) =>
    route.fulfill({
      json: { code: 0, data: { providers: [{ uuid: 'provider' }] } },
    }),
  );
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/api/v1/assistant/recommended-model', async (route) => {
    await gate;
    await route.fulfill({
      json: {
        code: 0,
        data: { uuid: 'recommended-other', name: 'Other recommendation' },
      },
    });
  });
  await page.route('**/api/v1/assistant/conversations', (route) =>
    route.fulfill({ json: { code: 0, data: chat } }),
  );
  await page.route(
    '**/api/v1/assistant/conversations/*/turn/stream',
    async (route) => {
      expect(route.request().postDataJSON().model_uuid).toBe('llm-valid');
      await route.fulfill({
        contentType: 'application/x-ndjson',
        body:
          JSON.stringify({
            kind: 'completed',
            data: {
              ...chat,
              revision: 1,
              model_uuid: 'llm-valid',
              model_name: 'Valid Mock Model',
              messages: [{ role: 'assistant', content: 'Manual model used' }],
            },
          }) + '\n',
      });
    },
  );
  await page.goto('/home/bots');
  const assistant = page.getByRole('dialog', { name: 'Workspace assistant' });
  await assistant.getByRole('combobox', { name: 'Select Model' }).click();
  await page.getByRole('option', { name: /Valid Mock Model/ }).click();
  release();
  await expect(assistant.getByText('Preparing assistant…')).toHaveCount(0);
  await expect(
    assistant.getByRole('combobox', { name: 'Select Model' }),
  ).toContainText('Valid Mock Model');
  await assistant.getByRole('textbox').fill('Hello');
  await assistant.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(
    assistant.getByText('Manual model used', { exact: true }),
  ).toBeVisible();
});

test('renders streaming text and tool progress before completion', async ({
  page,
}) => {
  const { createServer } = await import('node:http');
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const started = {
    ...chat,
    revision: 1,
    status: 'running',
    model_uuid: 'llm-valid',
    model_name: 'Recommended model',
    messages: [{ role: 'user', content: 'Inspect resources' }],
  };
  let currentConversation: Record<string, unknown> = started;
  const server = createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*');
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader(
      'Access-Control-Allow-Headers',
      req.headers['access-control-request-headers'] || '*',
    );
    if (req.method === 'OPTIONS') {
      res.end();
      return;
    }
    res.writeHead(200, { 'Content-Type': 'application/x-ndjson' });
    const emit = (kind: string, data: unknown) =>
      res.write(JSON.stringify({ kind, data }) + '\n');
    emit('snapshot', started);
    emit('phase', { phase: 'thinking', round: 1 });
    emit('text', { text: 'Inspecting your resources' });
    emit('phase', {
      phase: 'tool',
      tool: { name: 'list_resources', arguments: { kind: 'models' } },
    });
    await gate;
    currentConversation = {
      ...started,
      status: 'ready',
      messages: [
        ...started.messages,
        {
          role: 'tool',
          content: '{}',
          tool: {
            name: 'list_resources',
            arguments: { kind: 'models' },
            result: { total: 1, items: [] },
          },
        },
        { role: 'assistant', content: 'Found your model' },
      ],
    };
    emit('completed', currentConversation);
    res.end();
  });
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address() as { port: number };
  try {
    await installLangBotApiMocks(page, {
      authenticated: true,
      withAssistant: true,
    });
    // The panel refreshes the persisted conversation after streaming finishes.
    // Return the same snapshot as the stream instead of the generic API fallback.
    await page.route(
      '**/api/v1/assistant/conversations/assistant-test',
      (route) =>
        route.fulfill({ json: { code: 0, data: currentConversation } }),
    );
    await page.route('**/api/v1/provider/providers', (route) =>
      route.fulfill({
        json: { code: 0, data: { providers: [{ uuid: 'provider' }] } },
      }),
    );
    await page.route('**/api/v1/assistant/recommended-model', (route) =>
      route.fulfill({
        json: {
          code: 0,
          data: { uuid: 'llm-valid', name: 'Recommended model' },
        },
      }),
    );
    await page.route('**/api/v1/assistant/conversations', (route) =>
      route.fulfill({ json: { code: 0, data: chat } }),
    );
    await page.route(
      '**/api/v1/assistant/conversations/*/turn/stream',
      (route) =>
        route.continue({ url: `http://127.0.0.1:${address.port}/stream` }),
    );
    await page.goto('/home/bots');
    const assistant = page.getByRole('dialog', { name: 'Workspace assistant' });
    await expect(
      assistant.getByRole('combobox', { name: 'Select Model' }),
    ).toContainText('Recommended model');
    await assistant.getByRole('textbox').fill('Inspect resources');
    await assistant.getByRole('button', { name: 'Send', exact: true }).click();
    await expect(
      assistant.getByText('Inspecting your resources', { exact: true }),
    ).toBeVisible();
    await expect(
      assistant.getByRole('button', { name: /Find chat models Running/ }),
    ).toBeVisible();
    await expect(
      assistant.getByRole('button', { name: 'Stop task', exact: true }),
    ).toBeEnabled();
    release();
    await expect(
      assistant.getByText('Found your model', { exact: true }),
    ).toBeVisible();
    await expect(
      assistant.getByText('Inspecting your resources', { exact: true }),
    ).toHaveCount(0);
    const bubble = assistant
      .locator('[class*="assistantMessage"]')
      .filter({ hasText: 'Found your model' });
    await expect(
      bubble.getByRole('button', { name: /Find chat models Completed/ }),
    ).toBeVisible();
  } finally {
    release();
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
});

test('without providers shows setup only and rechecks after model settings close', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAssistant: true,
  });
  await page.route('**/api/v1/provider/requesters', (route) =>
    route.fulfill({ json: { code: 0, data: { requesters: [] } } }),
  );
  let configured = false;
  let recommendations = 0;
  await page.route('**/api/v1/provider/providers', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          providers: configured
            ? [
                {
                  uuid: 'provider',
                  name: 'Custom provider',
                  requester: 'openai-chat-completions',
                  config: {},
                },
              ]
            : [],
        },
      },
    }),
  );
  await page.route('**/api/v1/assistant/recommended-model', (route) => {
    recommendations++;
    return route.fulfill({
      json: { code: 0, data: { uuid: 'llm-valid', name: 'Recommended model' } },
    });
  });
  await page.goto('/home/bots');
  const setup = page.getByRole('complementary', {
    name: 'Workspace assistant',
  });
  await expect(
    setup.getByRole('button', { name: 'Sign in to LangBot Account' }),
  ).toBeVisible();
  await expect(
    page.getByRole('dialog', { name: 'Workspace assistant' }),
  ).toHaveCount(0);
  expect(recommendations).toBe(0);
  await setup.getByRole('button', { name: 'Configure models' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  configured = true;
  await page.keyboard.press('Escape');
  await expect(
    page
      .getByRole('dialog', { name: 'Workspace assistant' })
      .getByRole('combobox', { name: 'Select Model' }),
  ).toContainText('Recommended model');
});

test('setup login starts the existing LangBot Account authorization flow', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAssistant: true,
  });
  await page.route('**/api/v1/provider/providers', (route) =>
    route.fulfill({
      json: { code: 0, data: { providers: [] } },
    }),
  );
  await page.goto('/home/bots');
  const request = page.waitForRequest(
    (request) =>
      request.url().includes('/space/') && request.url().includes('authorize'),
  );
  await page
    .getByRole('complementary', { name: 'Workspace assistant' })
    .getByRole('button', { name: 'Sign in to LangBot Account' })
    .click();
  expect((await request).url()).toContain('authorize');
});

test('switches conversations, restores background progress after reload and stops only the selected task', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAssistant: true,
  });
  await page.route('**/api/v1/provider/providers', (route) =>
    route.fulfill({
      json: { code: 0, data: { providers: [{ uuid: 'provider' }] } },
    }),
  );
  await page.route('**/api/v1/assistant/recommended-model', (route) =>
    route.fulfill({
      json: { code: 0, data: { uuid: 'llm-valid', name: 'Recommended model' } },
    }),
  );
  const running = {
    ...chat,
    uuid: 'running-chat',
    revision: 3,
    status: 'running',
    model_uuid: 'llm-valid',
    model_name: 'Recommended model',
    messages: [{ role: 'user', content: 'Background request' }],
    progress: {
      text: 'Working in the background',
      phase: 'thinking',
      round: 2,
    },
  };
  const ready = {
    ...chat,
    uuid: 'ready-chat',
    model_uuid: 'llm-valid',
    model_name: 'Recommended model',
    messages: [{ role: 'assistant', content: 'Previous answer' }],
  };
  let stopped = false;
  await page.route('**/api/v1/assistant/conversations', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          conversations: [
            {
              uuid: running.uuid,
              title: 'Background request',
              status: stopped ? 'failed' : 'running',
            },
            {
              uuid: ready.uuid,
              title: 'Previous conversation',
              status: 'ready',
            },
          ],
        },
      },
    }),
  );
  await page.route('**/api/v1/assistant/conversations/*', (route) => {
    const data = route.request().url().endsWith('ready-chat')
      ? ready
      : stopped
        ? {
            ...running,
            status: 'failed',
            error: 'stopped',
            progress: undefined,
          }
        : running;
    return route.fulfill({ json: { code: 0, data } });
  });
  await page.route(
    '**/api/v1/assistant/conversations/running-chat/stop',
    (route) => {
      expect(route.request().postDataJSON()).toEqual({ revision: 3 });
      stopped = true;
      return route.fulfill({
        json: {
          code: 0,
          data: {
            ...running,
            status: 'failed',
            error: 'stopped',
            progress: undefined,
          },
        },
      });
    },
  );
  await page.goto('/home/bots');
  const assistant = page.getByRole('dialog', { name: 'Workspace assistant' });
  await assistant
    .getByRole('combobox', { name: 'Conversations', exact: true })
    .click();
  await page
    .getByRole('option', { name: '◌ Background request', exact: true })
    .click();
  await expect(
    assistant.getByText('Working in the background', { exact: true }),
  ).toBeVisible();
  await assistant
    .getByRole('combobox', { name: 'Conversations', exact: true })
    .click();
  await page
    .getByRole('option', { name: 'Previous conversation', exact: true })
    .click();
  await expect(
    assistant.getByText('Previous answer', { exact: true }),
  ).toBeVisible();
  expect(stopped).toBe(false);
  await assistant
    .getByRole('combobox', { name: 'Conversations', exact: true })
    .click();
  await page
    .getByRole('option', { name: '◌ Background request', exact: true })
    .click();
  await page.reload();
  await expect(
    assistant.getByText('Working in the background', { exact: true }),
  ).toBeVisible();
  await assistant
    .getByRole('button', { name: 'Stop task', exact: true })
    .click();
  await expect(assistant.getByRole('alert')).toContainText('Stopped.');
  await expect(
    assistant.getByRole('button', { name: 'Stop task', exact: true }),
  ).toHaveCount(0);
  await assistant
    .getByRole('button', { name: 'New conversation', exact: true })
    .click();
  await expect(assistant.getByRole('textbox')).toBeEmpty();
});

test('keeps the reading position through background updates and resumes following at the bottom', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAssistant: true,
  });
  await page.route('**/api/v1/provider/providers', (route) =>
    route.fulfill({
      json: { code: 0, data: { providers: [{ uuid: 'provider' }] } },
    }),
  );
  await page.route('**/api/v1/assistant/recommended-model', (route) =>
    route.fulfill({
      json: { code: 0, data: { uuid: 'llm-valid', name: 'Model' } },
    }),
  );
  let updates = 0;
  await page.route('**/api/v1/assistant/conversations', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          conversations: [
            {
              uuid: 'scroll-chat',
              title: 'Long conversation',
              status: 'running',
            },
          ],
        },
      },
    }),
  );
  await page.route('**/api/v1/assistant/conversations/scroll-chat', (route) => {
    updates++;
    return route.fulfill({
      json: {
        code: 0,
        data: {
          ...chat,
          uuid: 'scroll-chat',
          status: 'running',
          model_uuid: 'llm-valid',
          model_name: 'Model',
          messages: [
            {
              role: 'assistant',
              content: Array.from(
                { length: 40 },
                (_, i) => `Paragraph ${i}`,
              ).join('\n\n'),
            },
          ],
          progress: {
            text: Array.from({ length: updates }, (_, i) => `Update ${i}`).join(
              '\n\n',
            ),
            phase: 'thinking',
          },
        },
      },
    });
  });
  await page.goto('/home/bots');
  const panel = page.getByRole('dialog', { name: 'Workspace assistant' });
  await panel
    .getByRole('combobox', { name: 'Conversations', exact: true })
    .click();
  await page
    .getByRole('option', { name: '◌ Long conversation', exact: true })
    .click();
  const messages = panel.locator('[aria-live="polite"]');
  const gap = () =>
    messages.evaluate((el) => el.scrollHeight - el.clientHeight - el.scrollTop);
  await expect.poll(gap).toBeLessThan(2);
  await messages.hover();
  await page.mouse.wheel(0, -600);
  await expect.poll(gap).toBeGreaterThan(200);
  const position = await messages.evaluate((el) => el.scrollTop);
  const previousUpdates = updates;
  await expect.poll(() => updates).toBeGreaterThan(previousUpdates + 1);
  await expect
    .poll(() => messages.evaluate((el) => el.scrollTop))
    .toBeCloseTo(position, 0);
  await messages.hover();
  await page.mouse.wheel(0, 10000);
  await expect.poll(gap).toBeLessThan(2);
  const beforeFollow = updates;
  await expect.poll(() => updates).toBeGreaterThan(beforeFollow + 1);
  await expect.poll(gap).toBeLessThan(2);
});

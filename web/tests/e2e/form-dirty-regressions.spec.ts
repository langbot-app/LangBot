import { expect, test, type Page } from '@playwright/test';
import {
  installLangBotApiMocks,
  pipelineMetadata,
} from './fixtures/langbot-api';

const runner = 'plugin:langbot-team/LocalAgent/default';

async function setup(page: Page, kind: 'agent' | 'pipeline' = 'agent') {
  await installLangBotApiMocks(page, { authenticated: true });
  // Exercise the self-hosted form, without the unrelated account assistant overlay.
  await page.route('**/api/v1/user/info', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: { account_uuid: null, user_id: 1, username: 'Form tester' },
      },
    }),
  );
  const metadata = pipelineMetadata();
  let pipelineSaved = false;
  page.on('request', (r) => {
    if (r.method() === 'PUT' && r.url().endsWith('/pipelines/pipeline-draft'))
      pipelineSaved = true;
  });
  await page.route('**/api/v1/pipelines/pipeline-draft', async (route) => {
    if (route.request().method() !== 'GET' || pipelineSaved)
      return route.fallback();
    await route.fulfill({
      json: {
        code: 0,
        data: {
          pipeline: {
            uuid: 'pipeline-draft',
            name: 'Pipeline draft',
            emoji: '⚙️',
            description: '',
            config: {
              ai: {
                runner: { id: runner },
                runner_config: {
                  [runner]: {
                    model: { primary: 'llm-valid', fallbacks: [] },
                    instruction: 'Original instruction',
                    advanced: false,
                    detail: 'Original detail',
                  },
                },
              },
              trigger: {},
              safety: {},
              output: {},
            },
          },
        },
      },
    });
  });
  metadata.configs[0].stages[1].config.push(
    ...([
      {
        name: 'instruction',
        label: { en_US: 'Instruction' },
        type: 'text',
        required: true,
        default: 'Original instruction',
      },
      {
        name: 'advanced',
        label: { en_US: 'Advanced' },
        type: 'boolean',
        default: false,
      },
      {
        name: 'detail',
        label: { en_US: 'Detail' },
        type: 'text',
        default: 'Original detail',
        show_if: { field: 'advanced', operator: 'eq', value: true },
      },
    ] as any),
  );
  await page.route(
    `**/api/v1/${kind === 'agent' ? 'agents' : 'pipelines'}/_/metadata`,
    (route) =>
      route.fulfill({
        json: {
          code: 0,
          data:
            kind === 'agent'
              ? {
                  runner_config: metadata.configs[0],
                  kinds: [],
                  event_processors: [],
                }
              : metadata,
        },
      }),
  );
  await page.goto(
    `/home/${kind === 'agent' ? 'agents' : 'pipelines'}?id=${kind}-draft`,
  );
  if (kind === 'pipeline')
    await page.getByRole('tab', { name: /^AI$/ }).click();
  const input = page.locator('textarea[name="instruction"]');
  await expect(input).toHaveValue('Original instruction');
  return {
    input,
    save: page.getByRole('button', { name: 'Save', exact: true }),
    endpoint: `/api/v1/${kind === 'agent' ? 'agents' : 'pipelines'}/${kind}-draft`,
  };
}

for (const kind of ['agent', 'pipeline'] as const) {
  test(`${kind}: revert, conditional fields, immediate save and reload retain the latest draft`, async ({
    page,
  }) => {
    const { input, save, endpoint } = await setup(page, kind);
    await expect(save).toBeDisabled();
    await input.fill('Changed');
    await expect(save).toBeEnabled();
    await input.fill('Original instruction');
    await expect(save).toBeDisabled();
    await page
      .locator('label')
      .filter({ hasText: /^Advanced$/ })
      .locator('../..')
      .getByRole('switch')
      .click();
    const detail = page.locator('textarea[name="detail"]');
    await detail.fill('Retained while hidden');
    await page
      .locator('label')
      .filter({ hasText: /^Advanced$/ })
      .locator('../..')
      .getByRole('switch')
      .click();
    await expect(detail).toHaveCount(0);
    await input.pressSequentially(' final characters');
    const request = page.waitForRequest(
      (r) => new URL(r.url()).pathname === endpoint && r.method() === 'PUT',
    );
    await save.click();
    const payload = (await request).postDataJSON();
    const config = kind === 'agent' ? payload.config : payload.config.ai;
    expect(config.runner_config[runner]).toMatchObject({
      instruction: 'Original instruction final characters',
      detail: 'Retained while hidden',
      advanced: false,
    });
    await expect(save).toBeDisabled();
    await page.reload();
    if (kind === 'pipeline')
      await page.getByRole('tab', { name: /^AI$/ }).click();
    await expect(input).toHaveValue('Original instruction final characters');
    await expect(save).toBeDisabled();
    await page
      .locator('label')
      .filter({ hasText: /^Advanced$/ })
      .locator('../..')
      .getByRole('switch')
      .click();
    await expect(detail).toHaveValue('Retained while hidden');
  });
}

test('agent: save completion does not absorb edits made while the request is pending', async ({
  page,
}) => {
  const { input, save, endpoint } = await setup(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() === 'PUT') await gate;
    await route.fallback();
  });
  await input.fill('First draft');
  const request = page.waitForRequest(
    (r) => r.method() === 'PUT' && r.url().endsWith(endpoint),
  );
  await save.click();
  await request;
  await input.fill('Second draft typed during save');
  release();
  await expect(save).toBeEnabled();
  const next = page.waitForRequest(
    (r) => r.method() === 'PUT' && r.url().endsWith(endpoint),
  );
  await save.click();
  expect(
    (await next).postDataJSON().config.runner_config[runner].instruction,
  ).toBe('Second draft typed during save');
  await expect(save).toBeDisabled();
});

test('agent: failed save keeps the draft, and debugging saves the latest value first', async ({
  page,
}) => {
  const { input, save, endpoint } = await setup(page);
  let fail = true;
  const operations: string[] = [];
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() !== 'PUT') return route.fallback();
    if (fail)
      return route.fulfill({
        status: 500,
        json: { code: 500, msg: 'Deliberate save failure' },
      });
    operations.push('save');
    expect(
      route.request().postDataJSON().config.runner_config[runner].instruction,
    ).toBe('Latest before debug');
    await route.fallback();
  });
  await input.fill('Unsaved draft');
  await save.click();
  await expect(page.getByText(/Deliberate save failure/)).toBeVisible();
  await expect(save).toBeEnabled();
  await expect(input).toHaveValue('Unsaved draft');
  fail = false;
  page.on('request', (request) => {
    if (request.url().includes('/debug/stream')) operations.push('debug');
  });
  await page.getByRole('textbox', { name: 'Message content' }).fill('Hello');
  await input.fill('Latest before debug');
  await page.getByRole('button', { name: 'Save and run', exact: true }).click();
  await expect(page.getByText('Mock Agent response')).toBeVisible();
  expect(operations).toEqual(['save', 'debug']);
  await expect(save).toBeDisabled();
});

test('agent: required-field status still reacts after unrelated keystrokes are isolated', async ({
  page,
}) => {
  const { input } = await setup(page);
  await expect(page.getByText('Runner ready', { exact: true })).toBeVisible();
  await input.fill('');
  await expect(page.getByText('Runner ready', { exact: true })).toHaveCount(0);
  await input.fill('Valid again');
  await expect(page.getByText('Runner ready', { exact: true })).toBeVisible();
});

test('knowledge: early edits are not absorbed into initialization, and save uses a submitted snapshot', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const engine = {
    plugin_id: 'builtin/minimal-knowledge',
    name: { en_US: 'Test engine' },
    capabilities: ['text_retrieval'],
    creation_schema: [],
    retrieval_schema: [
      {
        name: 'instructions',
        type: 'text',
        label: { en_US: 'Retrieval instructions' },
        default: 'Original',
      },
    ],
  };
  let base = {
    uuid: 'kb-draft',
    name: 'Knowledge draft',
    description: '',
    emoji: '📚',
    initialized: true,
    knowledge_engine_plugin_id: engine.plugin_id,
    knowledge_engine: engine,
    creation_settings: {},
    retrieval_settings: { instructions: 'Original' },
  };
  await page.route('**/api/v1/knowledge/engines', (route) =>
    route.fulfill({ json: { code: 0, data: { engines: [engine] } } }),
  );
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let saving = false;
  await page.route('**/api/v1/knowledge/bases/kb-draft', async (route) => {
    if (route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON();
      saving = true;
      await gate;
      base = { ...base, ...payload };
      return route.fulfill({ json: { code: 0, data: { uuid: base.uuid } } });
    }
    return route.fulfill({ json: { code: 0, data: { base } } });
  });
  await page.goto('/home/knowledge?id=kb-draft');
  const input = page.locator('textarea[name="instructions"]');
  const save = page.getByRole('button', { name: 'Save', exact: true });
  await expect(input).toHaveValue('Original');
  await input.fill('Early edit');
  await expect(save).toBeEnabled();
  await input.fill('Original');
  await expect(save).toBeDisabled();
  await input.fill('Submitted value');
  await save.click();
  await expect.poll(() => saving).toBe(true);
  await input.fill('Typed while saving');
  release();
  await expect
    .poll(() => base.retrieval_settings.instructions)
    .toBe('Submitted value');
  await expect(save).toBeEnabled();
  await save.click();
  await expect
    .poll(() => base.retrieval_settings.instructions)
    .toBe('Typed while saving');
  await expect(save).toBeDisabled();
  await page.reload();
  await expect(input).toHaveValue('Typed while saving');
  await expect(save).toBeDisabled();
});

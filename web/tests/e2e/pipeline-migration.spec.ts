import { expect, test, type Page, type Route } from '@playwright/test';
import { readFileSync } from 'node:fs';

const canonicalConfig = JSON.parse(
  readFileSync('../src/langbot/templates/default-pipeline-config.json', 'utf8'),
);
import type {
  MigrationInstallation,
  PipelineMigrationItem,
  PipelineMigrationResult,
  PipelineMigrationState,
} from '../../src/app/infra/entities/api/pipeline-migration';
import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

const root = '/api/v1/pipelines/_/migration';
const runner = 'plugin:langbot-team/DifyAgent/default';
const row = (
  pipeline_uuid: string,
  state: PipelineMigrationState = 'ready',
): PipelineMigrationItem => ({
  pipeline_uuid,
  name: `Legacy ${pipeline_uuid}`,
  state,
  legacy_runner: 'dify-service-api',
  target_runner_id: runner,
  target_plugin: {
    author: 'langbot-team',
    name: 'DifyAgent',
    version: '1.0.0',
  },
  changed_paths: ['ai.runner.id'],
  blockers: [],
  warnings: [],
  preview_token: state === 'ready' ? `token-${pipeline_uuid}` : null,
});
const reply = (route: Route, data: unknown) =>
  route.fulfill({ json: { code: 0, data } });

async function setup(
  page: Page,
  options: { viewer?: boolean; current?: boolean; cloud?: boolean } = {},
) {
  const workspace = makeWorkspaceEntry(
    'workspace-playwright',
    'Migration workspace',
    options.cloud ? 'cloud_projection' : 'local',
  );
  if (options.viewer)
    workspace.permissions = ['resource.view', 'workspace.view'];
  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [workspace],
  });
  await page.routeWebSocket('**/api/v1/pipelines/**/ws/connect**', (ws) => {
    ws.onMessage((raw) => {
      if (JSON.parse(String(raw)).type === 'authenticate')
        ws.send(
          JSON.stringify({
            type: 'connected',
            connection_id: 'migration-test',
            session_type: 'person',
          }),
        );
    });
  });
  const state = {
    items: [row('one'), row('two')],
    posts: [] as unknown[],
    writes: [] as unknown[],
    previews: 0,
    polls: 0,
    installations: [] as MigrationInstallation[],
    metadataReads: 0,
    pipelineReads: 0,
    executeStatus: 200,
    pollLost: false,
    done: true,
    taskException: false,
    results: [
      { pipeline_uuid: 'one', state: 'migrated', code: null },
      { pipeline_uuid: 'two', state: 'migrated', code: null },
    ] as PipelineMigrationResult[],
    holdExecute: null as Promise<void> | null,
    holdPreview: null as Promise<void> | null,
    holdPoll: null as Promise<void> | null,
  };
  let config = options.current
    ? {
        ai: {
          runner: { id: 'plugin:langbot-team/LocalAgent/default' },
          runner_config: {},
        },
      }
    : {
        ai: {
          runner: { runner: 'dify-service-api' },
          'dify-service-api': { 'api-key': 'fixture-not-a-secret' },
        },
      };
  await page.route(`**${root}/preview`, async (route) => {
    state.previews++;
    const items = structuredClone(state.items);
    const scope =
      route.request().headers()['x-workspace-id'] || 'workspace-playwright';
    if (state.holdPreview) await state.holdPreview;
    await reply(route, {
      planner_version: '1',
      workspace_uuid: scope,
      items,
      total: items.length,
    });
  });
  await page.route(`**${root}/execute`, async (route) => {
    state.posts.push(route.request().postDataJSON());
    if (state.holdExecute) await state.holdExecute;
    if (state.executeStatus !== 200)
      return route.fulfill({
        status: state.executeStatus,
        json: { code: state.executeStatus, msg: 'unsafe-upstream-secret' },
      });
    await reply(route, {
      task_id: 411,
      pipeline_uuids: state.items
        .filter((r) => !['already_current', 'not_legacy'].includes(r.state))
        .map((r) => r.pipeline_uuid),
    });
  });
  await page.route('**/api/v1/system/tasks/411', async (route) => {
    state.polls++;
    if (state.holdPoll) await state.holdPoll;
    if (state.pollLost)
      return route.fulfill({ status: 404, json: { code: 404 } });
    if (
      state.done &&
      state.results.some(
        (item) => item.pipeline_uuid === 'one' && item.state === 'migrated',
      )
    ) {
      config = {
        ai: {
          runner: { id: 'plugin:langbot-team/LocalAgent/default' },
          runner_config: {},
        },
      };
    }
    await reply(route, {
      id: 411,
      runtime: {
        done: state.done,
        exception: state.taskException ? 'unsafe-upstream-secret' : null,
      },
      task_context: {
        metadata: {
          kind: 'pipeline_migration',
          results: state.results,
          installations: state.installations,
        },
      },
    });
  });
  await page.route('**/api/v1/pipelines/one', async (route) => {
    if (route.request().method() !== 'GET')
      state.writes.push(route.request().postDataJSON());
    state.pipelineReads++;
    await reply(route, {
      pipeline: {
        uuid: 'one',
        name: 'Legacy one',
        description: 'Preserved metadata',
        emoji: '⚙️',
        config,
        is_default: false,
      },
    });
  });
  await page.route('**/api/v1/pipelines/_/metadata', async (route) => {
    state.metadataReads++;
    await route.fallback();
  });
  return state;
}

async function open(page: Page, detail = false) {
  await page.goto(`/home/pipelines${detail ? '?id=one' : ''}`);
  await page
    .getByRole('button', { name: 'Review migration', exact: true })
    .click();
  return page.getByRole('dialog', { name: 'Pipeline migration' });
}
test('legacy detail never mounts editable runner defaults or debug autosave, metadata stays available', async ({
  page,
}) => {
  const state = await setup(page);
  await page.goto('/home/pipelines?id=one');
  await expect(
    page.getByText(
      'Legacy configuration is read-only until migration. Save and debug are unavailable to prevent implicit conversion.',
    ),
  ).toBeVisible();
  await expect(page.getByText('Preserved metadata')).toBeVisible();
  await expect(page.getByRole('tab', { name: 'AI', exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole('button', { name: 'Save', exact: true }),
  ).toHaveCount(0);
  expect(state.writes).toEqual([]);
  expect(state.posts).toEqual([]);
});

const installButton = (page: Page) =>
  page.getByRole('button', {
    name: 'Install plugins and migrate',
    exact: true,
  });
const dataButton = (page: Page) =>
  page.getByRole('button', { name: 'Migrate data only', exact: true });

test('compact assistant hides details, has no checkboxes and does not execute on open or close', async ({
  page,
}) => {
  const state = await setup(page);
  const dialog = await open(page);
  await expect(dialog.getByRole('checkbox')).toHaveCount(0);
  await expect(dialog.getByText('Legacy one', { exact: true })).toHaveCount(0);
  await expect(installButton(page)).toBeEnabled();
  await expect(dataButton(page)).toBeEnabled();
  await dialog.getByRole('button', { name: 'View pipelines' }).click();
  await expect(dialog.getByText('Legacy one', { exact: true })).toBeVisible();
  await expect(dialog).not.toContainText('ai.runner.id');
  await dialog
    .getByRole('button', { name: 'Close', exact: true })
    .first()
    .click();
  expect(state.posts).toEqual([]);
});

for (const install of [true, false]) {
  test(`one click migrates all pipelines, install_plugins=${install}`, async ({
    page,
  }) => {
    const state = await setup(page);
    state.items.push(row('missing', 'needs_plugin'));
    state.results.push({
      pipeline_uuid: 'missing',
      state: 'migrated',
      code: install ? null : 'data_only',
    });
    const dialog = await open(page);
    await (install ? installButton(page) : dataButton(page)).click();
    await expect(dialog).toContainText('3 migrated; 0 need attention.');
    expect(state.posts).toEqual([
      { confirmed: true, all: true, install_plugins: install },
    ]);
    expect(state.writes).toEqual([]);
    if (!install)
      await expect(dialog).toContainText(
        'Install the corresponding runner plugins yourself',
      );
    await expect(installButton(page)).toHaveCount(0);
    await expect(dataButton(page)).toHaveCount(0);
    await Promise.all([
      page.waitForEvent('load'),
      dialog.getByRole('button', { name: 'Done', exact: true }).click(),
    ]);
    await expect(dialog).toHaveCount(0);
    expect(state.posts).toHaveLength(1);
  });
}

test('read-only users can inspect but cannot migrate', async ({ page }) => {
  const state = await setup(page, { viewer: true });
  await open(page);
  await expect(installButton(page)).toBeDisabled();
  await expect(dataButton(page)).toBeDisabled();
  expect(state.posts).toEqual([]);
});

test('double clicks do not submit duplicate tasks; close does not cancel running task', async ({
  page,
}) => {
  const state = await setup(page);
  state.done = false;
  const dialog = await open(page);
  await installButton(page).dblclick();
  await expect(dialog.getByRole('status')).toContainText(
    'Installing required plugins',
  );
  await expect(installButton(page)).toHaveCount(0);
  await dialog
    .getByRole('button', { name: 'Close', exact: true })
    .first()
    .click();
  await page
    .getByRole('button', { name: 'Review migration', exact: true })
    .click();
  await expect(dialog.getByRole('status')).toContainText(
    'Installing required plugins',
  );
  expect(state.posts).toHaveLength(1);
  state.done = true;
  await expect(dialog).toContainText('2 migrated; 0 need attention.');
});

test('partial failures are reported without exposing upstream errors, and reopening allows retry', async ({
  page,
}) => {
  const state = await setup(page);
  state.results = [
    { pipeline_uuid: 'one', state: 'migrated', code: null },
    { pipeline_uuid: 'two', state: 'blocked', code: 'plugin_install_failed' },
  ];
  const dialog = await open(page);
  await installButton(page).click();
  await expect(dialog).toContainText('1 migrated; 1 need attention.');
  await dialog.getByRole('button', { name: 'View pipelines' }).click();
  await expect(dialog.getByTestId('migration-result-two')).toContainText(
    'Plugin installation failed',
  );
  await expect(dialog).not.toContainText('unsafe-upstream-secret');
  await expect(installButton(page)).toBeEnabled();
  await expect(
    dialog.getByRole('button', { name: 'Refresh preview' }),
  ).toHaveCount(0);
  await dialog
    .getByRole('button', { name: 'Close', exact: true })
    .first()
    .click();
  await page
    .getByRole('button', { name: 'Review migration', exact: true })
    .click();
  await expect(installButton(page)).toBeEnabled();
  expect(state.posts).toHaveLength(1);
});

test('all pipelines including more than fifty can be migrated, expanded list scrolls without moving actions', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 650 });
  const state = await setup(page);
  state.items = Array.from({ length: 65 }, (_, i) => row(`many-${i}`));
  state.results = state.items.map((r) => ({
    pipeline_uuid: r.pipeline_uuid,
    state: 'migrated',
    code: null,
  }));
  const dialog = await open(page);
  await dialog.getByRole('button', { name: 'View pipelines' }).click();
  const viewport = dialog
    .getByTestId('migration-scroll-area')
    .locator('[data-slot="scroll-area-viewport"]');
  const before = await installButton(page).boundingBox();
  const bounds = await viewport.boundingBox();
  await page.mouse.move(
    bounds!.x + bounds!.width / 2,
    bounds!.y + bounds!.height / 2,
  );
  await page.mouse.wheel(0, 20000);
  await expect
    .poll(() =>
      viewport.evaluate(
        (el) => el.scrollTop + el.clientHeight >= el.scrollHeight - 2,
      ),
    )
    .toBe(true);
  await expect(
    dialog.getByText('Legacy many-64', { exact: true }),
  ).toBeInViewport();
  expect((await installButton(page).boundingBox())!.y).toBeCloseTo(
    before!.y,
    0,
  );
  await expect(installButton(page)).toBeInViewport();
  await dataButton(page).click();
  await expect(dialog).toContainText('65 migrated; 0 need attention.');
  expect(state.posts).toEqual([
    { confirmed: true, all: true, install_plugins: false },
  ]);
});

for (const failure of [
  'missing',
  'extra',
  'duplicate',
  'invalid-state',
  'pending',
  'poll-lost',
  'task-error',
]) {
  test(`task result boundary: ${failure}`, async ({ page }) => {
    const state = await setup(page);
    if (failure === 'missing') state.results.pop();
    if (failure === 'extra')
      state.results.push({
        pipeline_uuid: 'foreign',
        state: 'migrated',
        code: null,
      });
    if (failure === 'duplicate') state.results.push(state.results[0]);
    if (failure === 'invalid-state')
      state.results[0].state = 'bogus' as PipelineMigrationResult['state'];
    if (failure === 'pending') state.results[0].state = 'pending';
    if (failure === 'poll-lost') state.pollLost = true;
    if (failure === 'task-error') state.taskException = true;
    const dialog = await open(page);
    await installButton(page).click();
    await expect(dialog).toContainText(
      failure === 'task-error' ? 'Task failed' : 'Task observation lost',
    );
    await expect(installButton(page)).toBeDisabled();
    await expect(dialog).not.toContainText('unsafe-upstream-secret');
    expect(state.posts).toHaveLength(1);
  });
}

test('workspace changes discard previous task results and stop polling', async ({
  page,
}) => {
  const state = await setup(page);
  let release!: () => void;
  state.holdPoll = new Promise((resolve) => {
    release = resolve;
  });
  await open(page);
  await installButton(page).click();
  await expect.poll(() => state.polls).toBe(1);
  await page.evaluate(async () => {
    const path = '/src/app/infra/http/currentWorkspaceStore.ts';
    const store = await import(path);
    const current = store.getCurrentWorkspaceSnapshot();
    store.setCurrentWorkspaceSnapshot({ ...current, placement_generation: 2 });
  });
  release();
  await expect(
    page.getByRole('dialog', { name: 'Pipeline migration' }),
  ).toHaveCount(0);
  expect(state.posts).toHaveLength(1);
});

for (const [language, title, review, action] of [
  ['zh-Hans', '流水线迁移', '检查迁移', '自动安装插件并迁移'],
  [
    'ja-JP',
    'パイプライン移行',
    '移行を確認',
    'プラグインを自動インストールして移行',
  ],
]) {
  test(`localized automatic assistant (${language})`, async ({ page }) => {
    await setup(page);
    await page.addInitScript(
      (locale) => localStorage.setItem('langbot_language', locale),
      language,
    );
    await page.goto('/home/pipelines');
    await page.getByRole('button', { name: review, exact: true }).click();
    const dialog = page.getByRole('dialog', { name: title });
    await expect(
      dialog.getByRole('button', { name: action, exact: true }),
    ).toBeEnabled();
    await expect(dialog).not.toContainText('pipelineMigration.');
  });
}

async function actualAgentRoute(page: Page) {
  const state = await setup(page);
  const agent = {
    uuid: 'one',
    name: 'Legacy one',
    description: 'Preserved metadata',
    emoji: '⚙️',
    kind: 'pipeline',
    config: canonicalConfig,
  };
  let listReads = 0;
  await page.route('**/api/v1/agents', async (route) => {
    listReads++;
    await reply(route, { agents: [agent] });
  });
  await page.route('**/api/v1/agents/one', (route) => reply(route, { agent }));
  return { state, listReads: () => listReads };
}

async function clickSidebarPipeline(page: Page) {
  const sidebar = page.locator('[data-slot="sidebar"]');
  const entry = sidebar.getByText('Legacy one', { exact: true });
  if (!(await entry.isVisible())) {
    await sidebar.getByText('Processors', { exact: true }).click();
  }
  await entry.click();
  await expect(page).toHaveURL(/\/home\/agents\?id=one$/);
}

test('SPEC canonical empty current detail allows selecting and saving a runner', async ({
  page,
}) => {
  const { state } = await actualAgentRoute(page);
  await page.route('**/api/v1/pipelines/one', async (route) => {
    if (route.request().method() !== 'GET')
      state.writes.push(route.request().postDataJSON());
    await reply(route, {
      pipeline: {
        uuid: 'one',
        name: 'Legacy one',
        description: 'Preserved metadata',
        emoji: '⚙️',
        config: canonicalConfig,
        is_default: false,
      },
    });
  });
  await page.goto('/home/agents?id=one');
  await expect(
    page.getByRole('tab', { name: 'AI', exact: true }),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'AI', exact: true }).click();
  const selector = page.getByRole('combobox', { name: 'Runner', exact: true });
  await selector.click();
  await page.getByRole('option', { name: /Local Agent/ }).click();
  const save = page.getByRole('button', { name: 'Save', exact: true });
  await expect(save).toBeEnabled();
  await save.click();
  await expect
    .poll(() => state.writes)
    .toMatchObject([
      {
        config: {
          ai: {
            runner: { id: 'plugin:langbot-team/LocalAgent/default' },
          },
        },
      },
    ]);
  expect(state.posts).toEqual([]);
});

test('SPEC actual legacy on second read remains guarded on the sidebar route', async ({
  page,
}) => {
  const { state } = await actualAgentRoute(page);
  let reads = 0;
  await page.route('**/api/v1/pipelines/one', async (route) => {
    if (route.request().method() !== 'GET')
      state.writes.push(route.request().postDataJSON());
    reads++;
    await reply(route, {
      pipeline: {
        uuid: 'one',
        name: 'Legacy one',
        description: 'Preserved metadata',
        emoji: '⚙️',
        config:
          reads === 1
            ? canonicalConfig
            : { ai: { runner: { runner: 'local-agent' } } },
      },
    });
  });
  await page.goto('/home');
  await clickSidebarPipeline(page);
  await expect.poll(() => reads).toBeGreaterThan(1);
  await expect(
    page.getByText(
      'Legacy configuration is read-only until migration. Save and debug are unavailable to prevent implicit conversion.',
    ),
  ).toBeVisible();
  await expect(page.getByRole('tab', { name: 'AI', exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole('button', { name: 'Save', exact: true }),
  ).toHaveCount(0);
  expect(state.writes).toEqual([]);
});

test('Box reuse notice stays concise and template validation has an actionable message', async ({
  page,
}) => {
  const state = await setup(page);
  state.items[0].legacy_runner = 'local-agent';
  state.items[0].warnings = [
    {
      code: 'local.box_state_reset',
      field: 'ai.local-agent.box-session-id-template',
    },
  ];
  state.items[1].state = 'blocked';
  state.items[1].blockers = [
    {
      code: 'local.box_template_invalid',
      field: 'ai.local-agent.box-session-id-template',
    },
  ];
  const dialog = await open(page);
  await expect(
    dialog.getByText('Sandbox reuse settings are preserved.', { exact: false }),
  ).not.toBeVisible();
  await dialog.getByRole('button', { name: 'View pipelines' }).click();
  await expect(
    dialog.getByText('Sandbox reuse settings are preserved.', { exact: false }),
  ).toBeVisible();
  await expect(
    dialog.getByText('Invalid sandbox reuse template.', { exact: false }),
  ).toBeVisible();
  await expect(dialog).not.toContainText('ai.local-agent');
  await expect(dialog.getByRole('checkbox')).toHaveCount(0);
});

test('installation progress remains inspectable during work and after a missing release failure', async ({
  page,
}) => {
  const state = await setup(page);
  await page.route(
    '**/api/v1/marketplace/plugins/langbot-team/DifyAgent',
    (route) =>
      reply(route, {
        plugin: {
          author: 'langbot-team',
          name: 'DifyAgent',
          label: { en_US: 'Dify Agent' },
          description: { en_US: 'Connect your Dify workflows.' },
          icon: 'https://market.test/dify.svg',
        },
      }),
  );
  await page.route('https://market.test/dify.svg', (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32"/></svg>',
    }),
  );
  state.done = false;
  state.results = state.items.map((item) => ({
    pipeline_uuid: item.pipeline_uuid,
    state: 'pending',
    code: null,
  }));
  state.installations = [
    {
      author: 'langbot-team',
      name: 'DifyAgent',
      version: '1.0.0',
      status: 'installing',
      stage: 'downloading',
      code: null,
      progress_percent: 15,
      download_current: 1024,
      download_total: 2048,
      started_at: 100,
      updated_at: 103,
      finished_at: null,
      steps: [
        { stage: 'checking', started_at: 100, finished_at: 101 },
        { stage: 'downloading', started_at: 101, finished_at: null },
      ],
    },
  ];
  const dialog = await open(page);
  await installButton(page).click();
  await expect(dialog.getByRole('progressbar')).toHaveAttribute(
    'aria-valuenow',
    '15',
  );
  await expect(dialog.getByText('Dify Agent', { exact: true })).toBeVisible();
  await expect(
    dialog.getByText('Connect your Dify workflows.', { exact: true }),
  ).toBeVisible();
  await expect(dialog.getByRole('img', { name: 'Dify Agent' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Installation details' }).click();
  await expect(dialog.getByText('Downloaded 1.0 KB / 2.0 KB')).toBeVisible();
  await dialog.getByRole('button', { name: 'View pipelines' }).click();
  await expect(dialog.getByText('Legacy one', { exact: true })).toBeVisible();
  state.installations[0] = {
    ...state.installations[0],
    status: 'failed',
    code: 'plugin_version_unavailable',
    finished_at: 104,
    updated_at: 104,
  };
  state.results = state.items.map((item) => ({
    pipeline_uuid: item.pipeline_uuid,
    state: 'blocked',
    code: 'plugin_version_unavailable',
  }));
  state.done = true;
  await expect(
    dialog
      .getByTestId('migration-installations')
      .getByText(
        'The required plugin version is not available in the marketplace. Retry after it is published, or migrate data only.',
      ),
  ).toBeVisible();
  await expect(dialog.getByRole('progressbar')).toHaveCount(0);
  await expect(dialog.getByText('Downloaded 1.0 KB / 2.0 KB')).toBeVisible();
});

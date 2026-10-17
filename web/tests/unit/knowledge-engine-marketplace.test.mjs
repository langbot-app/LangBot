import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

function setup({
  tasks = [{ runtime: { done: true } }],
  engines = [{ engines: [] }],
  cloud,
} = {}) {
  const source = fs.readFileSync(
    new URL(
      '../../src/app/home/knowledge/components/kb-form/knowledge-engine-marketplace.ts',
      import.meta.url,
    ),
    'utf8',
  );
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const storage = new Map(),
    calls = [];
  let workspace = 'alpha',
    now = 0,
    taskIndex = 0,
    engineIndex = 0;
  const http = {
    getPlugins: async () => ({
      plugins: [
        {
          manifest: {
            manifest: { metadata: { author: 'qa', name: 'existing' } },
          },
        },
      ],
    }),
    installPluginFromMarketplace: async (...args) => {
      calls.push(['install', ...args]);
      return { task_id: 42 };
    },
    getAsyncTask: async (id) => {
      calls.push(['task', id]);
      return tasks[Math.min(taskIndex++, tasks.length - 1)];
    },
    getKnowledgeEngines: async () => {
      calls.push(['engines']);
      return engines[Math.min(engineIndex++, engines.length - 1)];
    },
  };
  const deps = {
    '@/app/infra/http': { getCloudServiceClient: async () => cloud },
    '@/app/infra/http/HttpClient': { httpClient: http },
    '@/app/infra/http/workspaceContext': {
      getActiveWorkspaceUuid: () => workspace,
    },
  };
  const mod = { exports: {} };
  new Function(
    'require',
    'module',
    'exports',
    'window',
    'sessionStorage',
    'CustomEvent',
    'Date',
    'setTimeout',
    code,
  )(
    (name) => {
      assert.ok(name in deps, name);
      return deps[name];
    },
    mod,
    mod.exports,
    new EventTarget(),
    {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
    CustomEvent,
    { now: () => now },
    (callback, ms) => {
      now += ms;
      queueMicrotask(callback);
    },
  );
  return {
    api: mod.exports,
    storage,
    calls,
    setWorkspace: (value) => {
      workspace = value;
    },
  };
}
const plugin = {
  author: 'qa',
  name: 'engine',
  label: { en_US: 'QA Engine' },
  latest_version: '2.0.0',
};
const engine = { plugin_id: 'qa/engine', name: 'Registered QA Engine' };

test('catalog loads every page with the engine filter and excludes unrelated components', async () => {
  const searches = [];
  const { api } = setup({
    cloud: {
      searchMarketplaceExtensions: async (args) => {
        searches.push(args);
        return {
          total: 201,
          plugins:
            args.page === 1
              ? [
                  {
                    ...plugin,
                    components: { KnowledgeEngine: 1 },
                    install_count: 5,
                  },
                ]
              : args.page === 2
                ? [
                    {
                      name: 'runner',
                      components: { Runner: 1 },
                      install_count: 999,
                    },
                  ]
                : [
                    {
                      ...plugin,
                      name: 'popular',
                      components: { KnowledgeEngine: 1 },
                      install_count: 20,
                    },
                  ],
        };
      },
    },
  });
  const result = await api.loadKnowledgeEngineCatalog();
  assert.deepEqual(
    searches.map((value) => value.page),
    [1, 2, 3],
  );
  for (const args of searches)
    assert.deepEqual(args, {
      query: '',
      page: args.page,
      page_size: 100,
      type_filter: 'plugin',
      component_filter: 'KnowledgeEngine',
    });
  assert.deepEqual(
    result.marketplaceEngines.map((value) => value.name),
    ['popular', 'engine'],
  );
  assert.deepEqual(result.installedPluginIds, ['qa/existing']);
});

test('installation persists a scoped task before polling and waits for component registration', async () => {
  const { api, storage, calls } = setup({
    tasks: [{ runtime: { done: false } }, { runtime: { done: true } }],
    engines: [{ engines: [{ plugin_id: 'qa/other' }] }, { engines: [engine] }],
  });
  let created;
  const installed = await api.installMarketplaceKnowledgeEngine(plugin, {
    scope: 'kb:new',
    onTaskCreated: (id) => {
      created = id;
      assert.equal(api.readPendingKnowledgeEngineInstall('kb:new').taskId, 42);
    },
  });
  assert.equal(installed, engine);
  assert.equal(created, 42);
  assert.deepEqual(calls, [
    ['install', 'qa', 'engine', '2.0.0'],
    ['task', 42],
    ['task', 42],
    ['engines'],
    ['engines'],
  ]);
  assert.equal(storage.size, 0);
});

test('a pending engine install resumes only in its original workspace and form scope', async () => {
  const { api, storage, calls, setWorkspace } = setup({
    engines: [{ engines: [engine] }],
  });
  storage.set(
    'langbot-knowledge-engine-install:alpha:kb:new',
    JSON.stringify({
      taskId: 42,
      pluginId: 'qa/engine',
      pluginAuthor: 'qa',
      pluginName: 'engine',
      pluginLabel: 'QA Engine',
      scope: 'kb:new',
      startedAt: 0,
    }),
  );
  setWorkspace('beta');
  assert.equal(await api.resumePendingKnowledgeEngineInstall('kb:new'), null);
  setWorkspace('alpha');
  assert.equal(await api.resumePendingKnowledgeEngineInstall('kb:other'), null);
  assert.equal(await api.resumePendingKnowledgeEngineInstall('kb:new'), engine);
  assert.deepEqual(calls, [['task', 42], ['engines']]);
  assert.equal(storage.size, 0);
});

test('failed tasks clear their intent and never query component registration', async () => {
  const { api, calls, storage } = setup({
    tasks: [{ runtime: { done: true, exception: 'Package invalid' } }],
  });
  await assert.rejects(
    api.installMarketplaceKnowledgeEngine(plugin, { scope: 'kb:new' }),
    /Package invalid/,
  );
  assert.deepEqual(calls, [
    ['install', 'qa', 'engine', '2.0.0'],
    ['task', 42],
  ]);
  assert.equal(storage.size, 0);
});

test('an unfinished task times out with a recoverable intent, while missing registration clears it', async () => {
  const pending = setup({ tasks: [{ runtime: { done: false } }] });
  await assert.rejects(
    pending.api.installMarketplaceKnowledgeEngine(plugin, { scope: 'kb:new' }),
    (error) => error.code === 'install-timeout',
  );
  assert.equal(
    pending.api.readPendingKnowledgeEngineInstall('kb:new').taskId,
    42,
  );
  assert.equal(
    pending.calls.some((value) => value[0] === 'engines'),
    false,
  );
  const unregistered = setup();
  await assert.rejects(
    unregistered.api.installMarketplaceKnowledgeEngine(plugin, {
      scope: 'kb:new',
    }),
    (error) => error.code === 'registration-timeout',
  );
  assert.equal(unregistered.storage.size, 0);
});

test('a plugin without a version never starts an install task', async () => {
  const { api, calls } = setup();
  await assert.rejects(
    api.installMarketplaceKnowledgeEngine(
      { ...plugin, latest_version: '' },
      { scope: 'kb:new' },
    ),
    (error) => error.code === 'version-unavailable',
  );
  assert.deepEqual(calls, []);
});

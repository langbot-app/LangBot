import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

function load(source, deps = {}, globals = {}) {
  const code = ts.transpileModule(
    fs.readFileSync(new URL('../../src/' + source, import.meta.url), 'utf8'),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText;
  const mod = { exports: {} };
  new Function('require', 'module', 'exports', ...Object.keys(globals), code)(
    (id) => {
      assert.ok(id in deps, id);
      return deps[id];
    },
    mod,
    mod.exports,
    ...Object.values(globals),
  );
  return mod.exports;
}

test('wizard Runner recovery waits for the matching plugin registration without installing twice', async () => {
  const scope = 'wizard-ai-runner';
  const pending = {
    scope,
    taskId: 12,
    pluginId: 'qa/runner',
    pluginAuthor: 'qa',
    pluginName: 'runner',
    pluginLabel: 'QA Runner',
    startedAt: -1000000,
  };
  const storage = new Map([
    [`langbot-runner-install:alpha:${scope}`, JSON.stringify(pending)],
  ]);
  const calls = [],
    progress = [];
  let workspace = 'beta',
    tick = 0,
    polls = 0;
  const option = {
    name: 'plugin:qa/runner/default',
    label: { en_US: 'Registered Runner' },
  };
  const configTab = {
    name: 'ai',
    stages: [
      {
        name: 'runner',
        config: [
          {
            name: 'id',
            options: [{ name: 'plugin:qa/runner-neighbor/default' }],
          },
        ],
      },
    ],
  };
  const httpClient = {
    getAsyncTask: async (id) => {
      calls.push(['task', id]);
      return { runtime: { done: ++polls >= 2 } };
    },
    getGeneralPipelineMetadata: async () => {
      calls.push(['metadata']);
      if (calls.filter((value) => value[0] === 'metadata').length === 2)
        configTab.stages[0].config[0].options.push(option);
      return { configs: [configTab] };
    },
    installPluginFromMarketplace: async () =>
      assert.fail('recovery must not reinstall'),
  };
  const api = load(
    'app/home/agents/runner-marketplace.ts',
    {
      '@/app/infra/http/HttpClient': { httpClient },
      '@/app/infra/http': {},
      '@/app/infra/http/workspaceContext': {
        getActiveWorkspaceUuid: () => workspace,
      },
      '@/app/infra/entities/plugin': {},
    },
    {
      window: new EventTarget(),
      CustomEvent,
      sessionStorage: {
        getItem: (key) => storage.get(key) ?? null,
        removeItem: (key) => storage.delete(key),
      },
      Date: { now: () => tick },
      setTimeout: (callback, ms) => {
        tick += ms;
        queueMicrotask(callback);
      },
    },
  );
  assert.equal(await api.resumePendingRunnerInstall(scope), null);
  workspace = 'alpha';
  assert.equal(await api.resumePendingRunnerInstall('other'), null);
  const recovered = await api.resumePendingRunnerInstall(scope, (task) =>
    progress.push(task.runtime.done),
  );
  assert.equal(recovered.runner, option);
  assert.equal(recovered.configTab, configTab);
  assert.deepEqual(progress, [false, true]);
  assert.deepEqual(calls, [
    ['task', 12],
    ['task', 12],
    ['metadata'],
    ['metadata'],
  ]);
  assert.equal(storage.size, 0);
});

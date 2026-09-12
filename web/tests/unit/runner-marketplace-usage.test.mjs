import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
function load(path, imports = {}) {
  const exports = {};
  const source = fs.readFileSync(new URL(path, import.meta.url), 'utf8');
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  new Function('exports', 'require', js)(exports, (name) => {
    if (!(name in imports)) throw new Error(`Unexpected import: ${name}`);
    return imports[name];
  });
  return exports;
}
const entities = load('../../src/app/infra/entities/plugin/index.ts');
const plugin = (name, runner_usages) => ({
  name,
  author: 'test',
  components: { Runner: 1 },
  runner_usages,
  install_count: 0,
  latest_version: '1',
});
const plugins = [
  plugin('agent', ['agent']),
  plugin('event', ['event']),
  plugin('both', ['agent', 'event']),
  plugin('unknown', undefined),
];
test('recommendations require explicit usage and Runner component', () => {
  assert.deepEqual(
    plugins
      .filter((p) => entities.supportsRunnerUsage(p, 'agent'))
      .map((p) => p.name),
    ['agent', 'both'],
  );
  assert.deepEqual(
    plugins
      .filter((p) => entities.supportsRunnerUsage(p, 'event'))
      .map((p) => p.name),
    ['event', 'both'],
  );
  assert.equal(
    entities.supportsRunnerUsage({ ...plugins[0], components: {} }, 'agent'),
    false,
  );
});
test('catalog filters every page and recommendations cannot reintroduce incompatible plugins', async () => {
  const requests = [];
  const catalog = load('../../src/app/home/agents/runner-marketplace.ts', {
    '@/app/infra/entities/plugin': entities,
    '@/app/infra/http/HttpClient': {
      httpClient: { getPlugins: async () => ({ plugins: [] }) },
    },
    '@/app/infra/http': {
      getCloudServiceClient: async () => ({
        searchMarketplaceExtensions: async (request) => {
          requests.push(request);
          return {
            total: 101,
            plugins:
              request.page === 1 ? plugins.slice(0, 2) : plugins.slice(2),
          };
        },
        getRecommendationLists: async () => ({
          lists: [{ plugins: [plugins[1], plugins[2]] }],
        }),
      }),
    },
    '@/app/infra/http/workspaceContext': {},
  });
  const result = await catalog.loadRunnerCatalog('agent');
  assert.deepEqual(
    result.marketplaceRunners.map((p) => p.name),
    ['both', 'agent'],
  );
  assert.deepEqual(
    requests.map((r) => r.runner_usage),
    ['agent', 'agent'],
  );
});
test('legacy API fallback preserves usage and rejects missing usage metadata', async () => {
  const requests = [];
  class BaseHttpClient {
    async post(url, data) {
      requests.push({ url, data });
      if (url.endsWith('/extensions/search')) throw new Error('old endpoint');
      return { plugins, total: plugins.length };
    }
  }
  const { CloudServiceClient } = load(
    '../../src/app/infra/http/CloudServiceClient.ts',
    {
      './BaseHttpClient': { BaseHttpClient },
      '@/app/infra/entities/plugin': entities,
    },
  );
  const result = await new CloudServiceClient().searchMarketplaceExtensions({
    page: 1,
    page_size: 100,
    type_filter: 'plugin',
    component_filter: 'Runner',
    runner_usage: 'event',
  });
  assert.deepEqual(
    result.plugins.map((p) => p.name),
    ['event', 'both'],
  );
  assert.equal(requests[1].data.runner_usage, 'event');
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

function load(relative, deps, globals = {}) {
  const source = fs.readFileSync(
    new URL('../../src/' + relative, import.meta.url),
    'utf8',
  );
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const mod = { exports: {} };
  new Function('require', 'module', 'exports', ...Object.keys(globals), code)(
    (name) => {
      assert.ok(name in deps, name);
      return deps[name];
    },
    mod,
    mod.exports,
    ...Object.values(globals),
  );
  return mod.exports;
}

test('likes reuse the browser fingerprint, update cached state and notify only until unsubscribed', async () => {
  const calls = [],
    events = [];
  const client = {
    getMarketplaceLikedExtensions: async (fingerprint) => {
      calls.push(['status', fingerprint]);
      return {
        extensions: [{ type: 'plugin', extension_id: 'qa/already-liked' }],
      };
    },
    setMarketplaceExtensionLike: async (...args) => {
      calls.push(['toggle', ...args]);
      return { liked: args[4], like_count: args[4] ? 8 : 7 };
    },
  };
  const api = load(
    'app/home/plugins/components/plugin-market/marketplace-likes.ts',
    {
      '@fingerprintjs/fingerprintjs': {
        default: {
          load: async (options) => {
            calls.push(['fingerprint', options]);
            return { get: async () => ({ visitorId: 'browser-id' }) };
          },
        },
      },
      '@/app/infra/http': { getCloudServiceClient: async () => client },
    },
    { window: new EventTarget(), CustomEvent },
  );
  assert.equal(
    await api.getMarketplaceExtensionLiked(undefined, 'qa', 'already-liked'),
    true,
  );
  assert.equal(
    await api.getMarketplaceExtensionLiked('skill', 'qa', 'already-liked'),
    false,
  );
  const unsubscribe = api.subscribeMarketplaceLikeChanges((change) =>
    events.push(change),
  );
  assert.deepEqual(
    await api.toggleMarketplaceExtensionLike(undefined, 'qa', 'new', true),
    { key: 'plugin:qa/new', liked: true, likeCount: 8 },
  );
  assert.equal(
    await api.getMarketplaceExtensionLiked('plugin', 'qa', 'new'),
    true,
  );
  await api.toggleMarketplaceExtensionLike('plugin', 'qa', 'new', false);
  assert.equal(
    await api.getMarketplaceExtensionLiked('plugin', 'qa', 'new'),
    false,
  );
  unsubscribe();
  await api.toggleMarketplaceExtensionLike('skill', 'qa', 'new', true);
  assert.deepEqual(events, [
    { key: 'plugin:qa/new', liked: true, likeCount: 8 },
    { key: 'plugin:qa/new', liked: false, likeCount: 7 },
  ]);
  assert.deepEqual(calls, [
    ['fingerprint', { monitoring: false }],
    ['status', 'browser-id'],
    ['toggle', 'plugin', 'qa', 'new', 'browser-id', true],
    ['toggle', 'plugin', 'qa', 'new', 'browser-id', false],
    ['toggle', 'skill', 'qa', 'new', 'browser-id', true],
  ]);
});

test('legacy marketplace search converts hot sorting while preserving filters', async () => {
  const calls = [];
  class BaseHttpClient {
    async post(path, body) {
      calls.push([path, body]);
      if (path === '/api/v1/marketplace/extensions/search')
        throw new Error('Legacy server');
      return {
        plugins: [{ author: 'qa', name: 'legacy', type: 'plugin' }],
        total: 1,
      };
    }
  }
  const { CloudServiceClient } = load('app/infra/http/CloudServiceClient.ts', {
    './BaseHttpClient': { BaseHttpClient },
    '@/app/infra/entities/plugin': {},
  });
  const result = await new CloudServiceClient().searchMarketplaceExtensions({
    query: 'needle',
    page: 2,
    page_size: 10,
    sort_by: 'hot_score',
    sort_order: 'DESC',
    type_filter: 'plugin',
    tags_filter: ['qa'],
  });
  assert.deepEqual(
    result.plugins.map((value) => value.name),
    ['legacy'],
  );
  assert.deepEqual(calls, [
    [
      '/api/v1/marketplace/extensions/search',
      {
        query: 'needle',
        page: 2,
        page_size: 10,
        sort_by: 'hot_score',
        sort_order: 'DESC',
        type_filter: 'plugin',
        tags_filter: ['qa'],
      },
    ],
    [
      '/api/v1/marketplace/plugins/search',
      {
        query: 'needle',
        page: 2,
        page_size: 10,
        sort_by: 'install_count',
        sort_order: 'DESC',
        component_filter: undefined,
        tags_filter: ['qa'],
        type_filter: 'plugin',
        runner_usage: undefined,
      },
    ],
  ]);
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(
  currentDirectory,
  '../../src/app/infra/hooks/useInstalledPluginIcon.ts',
);
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;

// --- minimal React + backend mocks so the hook can run under node:test ---
let stateSlots = [];
let lastCleanup;

const reactMock = {
  useState(initial) {
    const value = typeof initial === 'function' ? initial() : initial;
    const index = stateSlots.length;
    stateSlots.push(value);
    return [
      value,
      (next) => {
        stateSlots[index] =
          typeof next === 'function' ? next(stateSlots[index]) : next;
      },
    ];
  },
  useEffect(effect) {
    const cleanup = effect();
    if (typeof cleanup === 'function') lastCleanup = cleanup;
  },
};

const httpMock = {
  httpClient: {
    getAuthenticatedPluginIconURL: () => {
      throw new Error('fetch not configured for this test');
    },
  },
};

const sourceRequire = createRequire(sourcePath);

function loadHook() {
  const loadedModule = { exports: {} };
  const requireShim = (id) => {
    if (id === 'react') return reactMock;
    if (id === '@/app/infra/http') return httpMock;
    return sourceRequire(id);
  };
  new Function('require', 'module', 'exports', compiled)(
    requireShim,
    loadedModule,
    loadedModule.exports,
  );
  return loadedModule.exports.useInstalledPluginIcon;
}

const revoked = [];
globalThis.URL.revokeObjectURL = (url) => revoked.push(url);

function reset() {
  stateSlots = [];
  lastCleanup = undefined;
  revoked.length = 0;
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

test('caches per author/name and revokes once the last subscriber leaves', async () => {
  let fetches = 0;
  let resolveFetch;
  httpMock.httpClient.getAuthenticatedPluginIconURL = () => {
    fetches += 1;
    return new Promise((resolve) => {
      resolveFetch = resolve;
    });
  };
  reset();
  const useInstalledPluginIcon = loadHook();

  const first = useInstalledPluginIcon('acme', 'demo');
  const firstCleanup = lastCleanup;
  assert.equal(first, null);
  assert.equal(fetches, 1);

  resolveFetch('blob:acme/demo');
  await flush();

  // Second subscriber reuses the cached object URL synchronously.
  const second = useInstalledPluginIcon('acme', 'demo');
  const secondCleanup = lastCleanup;
  assert.equal(second, 'blob:acme/demo');
  assert.equal(fetches, 1);

  firstCleanup();
  assert.deepEqual(revoked, []);
  secondCleanup();
  assert.deepEqual(revoked, ['blob:acme/demo']);

  // Cache was dropped with the last subscriber, so a new mount refetches.
  useInstalledPluginIcon('acme', 'demo');
  assert.equal(fetches, 2);
});

test('de-duplicates concurrent subscribers and revokes a shared icon once', async () => {
  let fetches = 0;
  let resolveFetch;
  httpMock.httpClient.getAuthenticatedPluginIconURL = () => {
    fetches += 1;
    return new Promise((resolve) => {
      resolveFetch = resolve;
    });
  };
  reset();
  const useInstalledPluginIcon = loadHook();

  useInstalledPluginIcon('acme', 'demo');
  const firstCleanup = lastCleanup;
  useInstalledPluginIcon('acme', 'demo');
  const secondCleanup = lastCleanup;
  assert.equal(fetches, 1);

  resolveFetch('blob:shared');
  await flush();

  firstCleanup();
  assert.deepEqual(revoked, []);
  secondCleanup();
  assert.deepEqual(revoked, ['blob:shared']);
});

test('caches nothing and revokes nothing when the authenticated fetch fails', async () => {
  let fetches = 0;
  httpMock.httpClient.getAuthenticatedPluginIconURL = () => {
    fetches += 1;
    return Promise.reject(new Error('not found'));
  };
  reset();
  const useInstalledPluginIcon = loadHook();

  const value = useInstalledPluginIcon('acme', 'missing');
  const cleanup = lastCleanup;
  assert.equal(value, null);

  await flush();
  assert.equal(useInstalledPluginIcon('acme', 'missing'), null);
  assert.equal(fetches, 2); // failures are not negatively cached

  cleanup();
  assert.deepEqual(revoked, []);
});

test('returns a marketplace URL verbatim without fetching', () => {
  let fetches = 0;
  httpMock.httpClient.getAuthenticatedPluginIconURL = () => {
    fetches += 1;
    return Promise.resolve('blob:unused');
  };
  reset();
  const useInstalledPluginIcon = loadHook();

  const value = useInstalledPluginIcon(
    'acme',
    'demo',
    'https://space.langbot.app/icon',
  );
  assert.equal(value, 'https://space.langbot.app/icon');
  assert.equal(fetches, 0);
  assert.equal(lastCleanup, undefined);
});

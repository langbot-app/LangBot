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
  '../../src/app/home/plugins/components/plugin-market/marketplace-installed.ts',
);
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const sourceRequire = createRequire(sourcePath);
const loadedModule = { exports: {} };
new Function('require', 'module', 'exports', compiled)(
  sourceRequire,
  loadedModule,
  loadedModule.exports,
);

const { buildInstalledIndex, resolveInstalledState, installedExtensionKey } =
  loadedModule.exports;

test('matches installed plugins by author and name', () => {
  const index = buildInstalledIndex(
    [{ id: 'alice/review', hasUpdate: true }],
    [],
    [],
  );

  assert.deepEqual(
    resolveInstalledState(index, {
      type: 'plugin',
      author: 'alice',
      pluginName: 'review',
    }),
    { installed: true, hasUpdate: true },
  );
  assert.deepEqual(
    resolveInstalledState(index, {
      type: 'plugin',
      author: 'bob',
      pluginName: 'review',
    }),
    { installed: false, hasUpdate: false },
    'a different publisher must not match',
  );
});

test('normalises MCP servers from `author__name` to `author/name`', () => {
  const index = buildInstalledIndex([], [{ id: 'acme__search' }], []);

  assert.equal(
    resolveInstalledState(index, {
      type: 'mcp',
      author: 'acme',
      pluginName: 'search',
    }).installed,
    true,
  );
  assert.equal(
    resolveInstalledState(index, {
      type: 'mcp',
      author: 'other',
      pluginName: 'search',
    }).installed,
    false,
  );
});

test('does not mark skills installed from a bare name', () => {
  // Two publishers ship a skill that both install as the plain name
  // `review`; the sidebar records no publisher for either.
  const index = buildInstalledIndex([], [], [{ id: 'review' }]);

  const alice = resolveInstalledState(index, {
    type: 'skill',
    author: 'alice',
    pluginName: 'review',
  });
  const bob = resolveInstalledState(index, {
    type: 'skill',
    author: 'bob',
    pluginName: 'review',
  });

  assert.equal(
    alice.installed,
    false,
    'alice/review must not be reported installed from a bare skill name',
  );
  assert.equal(
    bob.installed,
    false,
    'bob/review must not be reported installed from a bare skill name',
  );
});

test('keeps extension kinds separate for identical identities', () => {
  const index = buildInstalledIndex([{ id: 'alice/toolkit' }], [], []);

  assert.equal(
    resolveInstalledState(index, {
      type: 'mcp',
      author: 'alice',
      pluginName: 'toolkit',
    }).installed,
    false,
    'a plugin must not mark the same-named MCP server as installed',
  );
  assert.equal(
    installedExtensionKey(undefined, 'alice', 'toolkit'),
    'plugin:alice/toolkit',
    'a missing type must default to plugin',
  );
});

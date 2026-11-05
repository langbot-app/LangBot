import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = fs.readFileSync(
  new URL(
    '../../src/app/home/plugins/components/permission-grants.ts',
    import.meta.url,
  ),
  'utf8',
);
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', compiled)(loaded, loaded.exports);
const {
  permissionGrantRequest,
  permissionSelectionDiff,
  initialPermissionSelection,
} = loaded.exports;

const state = {
  compatibility_mode: false,
  grants: {
    workspace_operations: ['stats.basic'],
    capabilities: ['bot.message.send', 'sandbox'],
  },
  permissions: [
    { id: 'stats.basic', category: 'workspace_operations' },
    { id: 'bot.message.send', category: 'capabilities' },
    { id: 'sandbox', category: 'capabilities' },
  ],
};

test('strict confirmation sends only the selected installation grants', () => {
  assert.deepEqual(
    permissionGrantRequest(
      state,
      new Set(['stats.basic', 'bot.message.send']),
      true,
    ),
    {
      workspace_operations: ['stats.basic'],
      capabilities: ['bot.message.send'],
      confirm: true,
    },
  );
});

test('strict confirmation can omit every optional grant', () => {
  assert.deepEqual(permissionGrantRequest(state, new Set(), true), {
    workspace_operations: [],
    capabilities: [],
    confirm: true,
  });
});

test('compatibility confirmation grants all sixteen declared legacy capabilities', () => {
  const capabilities = [
    'langbot.info',
    'bot.read',
    'bot.message.send',
    'bot.platform_api',
    'models.read',
    'models.invoke',
    'storage.plugin',
    'storage.workspace',
    'knowledge.read',
    'knowledge.vector',
    'knowledge.parser',
    'config.read',
    'plugin_tools',
    'mcp',
    'sandbox',
    'plugin.read',
  ];
  const legacy = {
    ...state,
    compatibility_mode: true,
    permissions: capabilities.map((id) => ({ id, category: 'capabilities' })),
  };
  assert.deepEqual(permissionGrantRequest(legacy, new Set(), true), {
    workspace_operations: [],
    capabilities,
    confirm: true,
  });
});

test('saving without confirmation keeps only selected existing grants', () => {
  const granted = {
    ...state,
    permissions: [
      { id: 'stats.basic', category: 'workspace_operations', granted: true },
      { id: 'bot.message.send', category: 'capabilities', granted: true },
      { id: 'sandbox', category: 'capabilities', granted: true },
      { id: 'mcp', category: 'capabilities', granted: false },
    ],
  };
  assert.deepEqual(
    permissionGrantRequest(
      granted,
      new Set(['stats.basic', 'sandbox', 'mcp']),
      false,
    ),
    {
      workspace_operations: ['stats.basic'],
      capabilities: ['sandbox'],
      confirm: false,
    },
  );
});

test('selection diff compares against saved grants', () => {
  const confirmed = {
    ...state,
    pending_confirmation: false,
    permissions: [
      { id: 'stats.basic', category: 'workspace_operations', granted: true },
      { id: 'sandbox', category: 'capabilities', granted: true },
      { id: 'mcp', category: 'capabilities', granted: false },
    ],
  };
  const { added, removed } = permissionSelectionDiff(
    confirmed,
    new Set(['stats.basic', 'mcp']),
  );
  assert.deepEqual(
    added.map((item) => item.id),
    ['mcp'],
  );
  assert.deepEqual(
    removed.map((item) => item.id),
    ['sandbox'],
  );
});

test('pending installations start with every grantable permission selected', () => {
  const pending = {
    ...state,
    pending_confirmation: true,
    permissions: [
      {
        id: 'stats.basic',
        category: 'workspace_operations',
        granted: false,
        grantable: true,
      },
      {
        id: 'sandbox',
        category: 'capabilities',
        granted: true,
        grantable: false,
      },
    ],
  };
  assert.deepEqual([...initialPermissionSelection(pending)], ['stats.basic']);
  const { added, removed } = permissionSelectionDiff(
    pending,
    initialPermissionSelection(pending),
  );
  assert.deepEqual(
    added.map((item) => item.id),
    ['stats.basic'],
  );
  assert.deepEqual(removed, []);
});

test('all eight permission dictionaries expose matching translation keys', () => {
  const localeDirectory = new URL(
    '../../src/i18n/locales/plugin-permissions/',
    import.meta.url,
  );
  const locales = fs
    .readdirSync(localeDirectory)
    .filter((name) => name.endsWith('.ts'));
  assert.equal(locales.length, 8);
  let expected;
  for (const locale of locales) {
    const text = fs.readFileSync(new URL(locale, localeDirectory), 'utf8');
    const compiledLocale = ts.transpileModule(text, {
      compilerOptions: { module: ts.ModuleKind.CommonJS },
    }).outputText;
    const module = { exports: {} };
    new Function('module', 'exports', compiledLocale)(module, module.exports);
    const flatten = (value, prefix = '') =>
      Object.entries(value).flatMap(([key, item]) =>
        item && typeof item === 'object'
          ? flatten(item, `${prefix}${key}.`)
          : [[`${prefix}${key}`, item]],
      );
    const entries = flatten(module.exports.default);
    const keys = entries.map(([key]) => key).sort();
    expected ??= keys;
    assert.deepEqual(keys, expected, locale);
    assert.ok(
      entries.every(
        ([, value]) => typeof value === 'string' && value.length > 0,
      ),
      locale,
    );
  }
});

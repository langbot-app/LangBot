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
const { permissionGrantRequest } = loaded.exports;

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

test('revocation uses existing grants rather than unsaved selections', () => {
  assert.deepEqual(
    permissionGrantRequest(
      state,
      new Set(['ungranted.operation']),
      false,
      state.permissions[1],
    ),
    {
      workspace_operations: ['stats.basic'],
      capabilities: ['sandbox'],
      confirm: false,
    },
  );
  assert.deepEqual(state.grants.capabilities, ['bot.message.send', 'sandbox']);
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
    const values = module.exports.default;
    const keys = Object.keys(values).sort();
    expected ??= keys;
    assert.deepEqual(keys, expected, locale);
    assert.ok(
      Object.values(values).every(
        (value) => typeof value === 'string' && value.length > 0,
      ),
      locale,
    );
  }
});

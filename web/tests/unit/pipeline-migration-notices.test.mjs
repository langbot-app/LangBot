import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

function load(path) {
  const context = { exports: {} };
  vm.runInNewContext(
    ts.transpileModule(readFileSync(path, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS },
    }).outputText,
    context,
  );
  return context.exports;
}

const warnings = [
  ...new Set(
    [
      ...readFileSync(
        '../src/langbot/pkg/pipeline/legacy_config_migration.py',
        'utf8',
      ).matchAll(/_warn\(result,\s*'([^']+)'/g),
    ].map((match) => match[1]),
  ),
];

test('every converter warning has a specific explanation in all eight locales', () => {
  const { migrationIssueKey } = load(
    'src/app/home/pipelines/pipeline-migration-issues.ts',
  );
  const base = 'src/i18n/locales/pipeline-migration';
  const locales = readdirSync(base).filter((name) => name.endsWith('.ts'));
  assert.equal(locales.length, 8);
  assert.ok(
    warnings.length > 10,
    'warning discovery must not silently go empty',
  );
  for (const file of locales) {
    const catalog = load(`${base}/${file}`).default;
    for (const code of warnings) {
      const key = migrationIssueKey(code);
      assert.ok(key, `${file}: missing mapping for ${code}`);
      assert.equal(typeof catalog.notices?.[key], 'string', `${file}: ${code}`);
      assert.ok(catalog.notices[key].length > 10);
    }
    assert.ok(catalog.notices.pluginVersion);
    assert.ok(catalog.notices.pendingInteraction);
    for (const code of ['plugin_runtime_unavailable', 'migration_failed']) {
      const key = migrationIssueKey(code);
      assert.ok(key);
      assert.equal(typeof catalog.notices[key], 'string');
      assert.notEqual(catalog.notices[key], catalog.blockerFallback);
    }
  }
});

test('unknown backend issue codes never become translation keys or displayed messages', () => {
  const { migrationIssueKey } = load(
    'src/app/home/pipelines/pipeline-migration-issues.ts',
  );
  for (const code of [
    'unknown',
    '__proto__',
    'constructor',
    'secret-token.example',
  ]) {
    assert.equal(migrationIssueKey(code), undefined);
  }
});

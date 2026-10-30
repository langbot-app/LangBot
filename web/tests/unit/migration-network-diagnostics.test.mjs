import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';

test('network diagnostics use safe, translated messages in all eight locales', () => {
  const base = 'src/i18n/locales/pipeline-migration';
  const locales = readdirSync(base).filter((name) => name.endsWith('.ts'));
  assert.equal(locales.length, 8);
  for (const locale of locales) {
    const source = readFileSync(`${base}/${locale}`, 'utf8');
    const diagnostic = source.match(
      /networkDiagnostics: \{([\s\S]*?)\n  \}/,
    )?.[1];
    assert.ok(diagnostic, locale);
    for (const key of [
      'timeout',
      'connection',
      'incomplete',
      'http',
      'network',
    ]) {
      assert.match(
        diagnostic,
        new RegExp(`${key}:\\s+['"].+['"]`),
        `${locale}: ${key}`,
      );
    }
    assert.doesNotMatch(diagnostic, /https?:\/\/|\{\{kind\}\}/);
  }
  const component = readFileSync(
    'src/app/home/pipelines/MigrationInstallProgress.tsx',
    'utf8',
  );
  assert.match(
    component,
    /t\(networkDiagnosticKey\(item\.diagnostic\.kind\)\)/,
  );
  assert.match(component, /Number\.isInteger\(item\.diagnostic\.http_status\)/);
  assert.doesNotMatch(component, /\{item\.diagnostic\.kind\}/);
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

test('command configuration and platform registration catalogs have matching keys and placeholders', () => {
  let baseline;
  for (const locale of [
    'en-US',
    'zh-Hans',
    'zh-Hant',
    'ja-JP',
    'es-ES',
    'ru-RU',
    'th-TH',
    'vi-VN',
  ]) {
    const source = fs.readFileSync(
      new URL(`../../src/i18n/locales/${locale}.ts`, import.meta.url),
      'utf8',
    );
    const ast = ts.createSourceFile(
      `${locale}.ts`,
      source,
      ts.ScriptTarget.Latest,
      true,
    );
    const entries = {};
    function fields(node, prefix) {
      for (const field of node.properties) {
        const key = `${prefix}.${field.name.getText(ast)}`;
        if (ts.isObjectLiteralExpression(field.initializer))
          fields(field.initializer, key);
        else {
          assert.ok(
            ts.isStringLiteral(field.initializer) &&
              field.initializer.text.trim(),
            `${locale}: ${key}`,
          );
          entries[key] = (
            field.initializer.text.match(/{{[^}]+}}/g) ?? []
          ).sort();
        }
      }
    }
    function visit(node) {
      if (
        ts.isPropertyAssignment(node) &&
        ['commandProcessor', 'platformCommands'].includes(
          node.name.getText(ast),
        )
      ) {
        fields(node.initializer, node.name.getText(ast));
      }
      ts.forEachChild(node, visit);
    }
    visit(ast);
    assert.equal(Object.keys(entries).length, 45, locale);
    if (baseline) assert.deepEqual(entries, baseline, locale);
    else baseline = entries;
  }
});

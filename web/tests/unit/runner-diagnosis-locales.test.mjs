import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

test('Runner diagnosis and draft-safe repair have all eight complete catalogs', () => {
  const locales = [
    'en-US',
    'zh-Hans',
    'zh-Hant',
    'ja-JP',
    'es-ES',
    'ru-RU',
    'th-TH',
    'vi-VN',
  ];
  const expected = ['disabled', 'draft', 'missing', 'repair', 'runtime'];
  for (const locale of locales) {
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
    const found = [];
    function visit(node) {
      if (
        ts.isPropertyAssignment(node) &&
        node.name.getText(ast) === 'runnerDiagnosis'
      ) {
        assert.ok(ts.isObjectLiteralExpression(node.initializer), locale);
        const fields = node.initializer.properties;
        assert.deepEqual(
          fields.map((field) => field.name.getText(ast)).sort(),
          expected,
          locale,
        );
        for (const field of fields) {
          assert.ok(
            ts.isStringLiteral(field.initializer) &&
              field.initializer.text.trim(),
            locale,
          );
          assert.equal(
            field.initializer.text.match(/{{[^}]+}}/g),
            null,
            locale,
          );
        }
        found.push(node);
      }
      ts.forEachChild(node, visit);
    }
    visit(ast);
    assert.equal(found.length, 1, locale);
  }
});

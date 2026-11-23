import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = fs.readFileSync(
  new URL(
    '../../src/app/home/components/workspace-operations/runner-operation-grants.ts',
    import.meta.url,
  ),
  'utf8',
);
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', compiled)(loaded, loaded.exports);
const { operationsForRunner } = loaded.exports;
const operations = [
  { id: 'stats.basic', grantable: false },
  { id: 'stats.private', grantable: true },
];

test('runner operation selection follows installation grants, not member permissions', () => {
  const selected = operationsForRunner(operations, 'plugin:qa/runner/default', {
    'qa/runner': ['stats.basic'],
  });
  assert.deepEqual(selected, [
    { id: 'stats.basic', grantable: true },
    { id: 'stats.private', grantable: false },
  ]);
  assert.equal(operations[0].grantable, false);
});

test('switching to a different plugin does not inherit its predecessor grants', () => {
  assert.ok(
    operationsForRunner(operations, 'plugin:qa/other/default', {
      'qa/runner': ['stats.basic'],
    }).every((item) => !item.grantable),
  );
});

test('missing grants and non-plugin runners expose no selectable workspace operations', () => {
  for (const runner of [undefined, 'local', 'plugin:qa/runner/default']) {
    assert.ok(
      operationsForRunner(operations, runner, {}).every(
        (item) => !item.grantable,
      ),
    );
  }
});

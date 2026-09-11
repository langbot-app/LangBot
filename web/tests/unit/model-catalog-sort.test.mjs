import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = fs.readFileSync(
  new URL(
    '../../src/app/home/components/model-availability/sort-models.ts',
    import.meta.url,
  ),
  'utf8',
);
const exports = {};
new Function(
  'exports',
  ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText,
)(exports);
const { sortModelsByCatalog } = exports;
const model = (name) => ({ uuid: name, name });
const metadata = (listed_at, up, input_credits = 10, output_credits = 20) => ({
  listed_at,
  availability: { up },
  input_credits,
  output_credits,
});
const names = (models) => models.map((m) => m.name);

test('newest UTC day precedes availability; same-day time is ignored', () => {
  const items = ['old-up', 'new-down', 'new-up'].map(model);
  const catalog = {
    'old-up': metadata('2026-09-08T23:59:59Z', true),
    'new-down': metadata('2026-09-09T23:59:59Z', false),
    'new-up': metadata('2026-09-10T01:00:00+08:00', true),
  };
  assert.deepEqual(names(sortModelsByCatalog(items, catalog)), [
    'new-up',
    'new-down',
    'old-up',
  ]);
  assert.deepEqual(names(items), ['old-up', 'new-down', 'new-up']);
});

test('same-day availability ranks up, unknown, down before prices', () => {
  const catalog = {
    down: metadata('2026-09-09', false, 0, 0),
    unknown: metadata('2026-09-09', null, 1, 1),
    up: metadata('2026-09-09', true, 100, 100),
  };
  assert.deepEqual(
    names(sortModelsByCatalog(Object.keys(catalog).map(model), catalog)),
    ['up', 'unknown', 'down'],
  );
});

test('prices compare input then output; free prices remain valid', () => {
  const catalog = {
    expensive: metadata('2026-09-09', true, 20, 1),
    'output-high': metadata('2026-09-09', true, 10, 50),
    'output-low': metadata('2026-09-09', true, 10, 20),
    free: metadata('2026-09-09', true, 0, 0),
    missing: metadata('2026-09-09', true, null, null),
    invalid: metadata('2026-09-09', true, NaN, -1),
  };
  assert.deepEqual(
    names(sortModelsByCatalog(Object.keys(catalog).map(model), catalog)),
    ['free', 'output-low', 'output-high', 'expensive', 'invalid', 'missing'],
  );
});

test('unknown dates sort after known dates and missing catalog entries are safe', () => {
  const catalog = {
    known: metadata('2026-01-01', false, 100, 100),
    invalid: metadata('invalid', true),
    missing: metadata(null, true),
  };
  assert.deepEqual(
    names(
      sortModelsByCatalog(
        ['missing', 'absent', 'invalid', 'known'].map(model),
        catalog,
      ),
    ),
    ['known', 'invalid', 'missing', 'absent'],
  );
});

test('UUID lookup takes precedence, name lookup works, empty metadata preserves order', () => {
  const items = [{ uuid: 'local-id', name: 'alias' }, model('other')];
  const catalog = {
    alias: metadata('2026-09-09', true),
    other: metadata('2026-09-08', true),
  };
  assert.deepEqual(names(sortModelsByCatalog(items, catalog)), [
    'alias',
    'other',
  ]);
  catalog['local-id'] = metadata('2026-09-07', true);
  assert.deepEqual(names(sortModelsByCatalog(items, catalog)), [
    'other',
    'alias',
  ]);
  assert.deepEqual(sortModelsByCatalog(items, {}), items);
});

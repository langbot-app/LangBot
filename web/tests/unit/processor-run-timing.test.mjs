import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
const source = fs.readFileSync(
  new URL(
    '../../src/app/home/agents/components/processor-run-timing.ts',
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
const { processorRunDuration } = exports;
test('duration uses precise lifecycle times, excluding queue wait', () => {
  assert.equal(
    processorRunDuration({
      created_at: 1,
      started_at_ms: 2100,
      finished_at_ms: 2375,
    }),
    275,
  );
});
test('missing or inverted times remain unknown; zero is a valid duration', () => {
  assert.equal(
    processorRunDuration({ created_at: 1, started_at_ms: 1000 }),
    null,
  );
  assert.equal(
    processorRunDuration({ created_at: 1, finished_at_ms: 2000 }),
    null,
  );
  assert.equal(
    processorRunDuration({ started_at_ms: 1000, finished_at_ms: 900 }),
    null,
  );
  assert.equal(
    processorRunDuration({ started_at_ms: 1000, finished_at_ms: 1000 }),
    0,
  );
});
test('old server responses fall back to second precision', () => {
  assert.equal(processorRunDuration({ started_at: 2, finished_at: 4 }), 2000);
});

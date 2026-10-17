import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

// The resolver is pure: recorded calls carry a time and a session, the execution
// list carries the runs' windows, so the link is decided without any re-query.
const source = fs.readFileSync(
  new URL('../../src/app/home/monitoring/utils/callLinks.ts', import.meta.url),
  'utf8',
);
const module = { exports: {} };
new Function(
  'exports',
  ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText,
)(module.exports);
const { findCallExecution, resolveCallTarget } = module.exports;

const at = (iso) => new Date(iso);

function run(overrides) {
  return {
    source: 'agent',
    id: 'run-1',
    session_id: 'session-a',
    started_at_ms: at('2026-10-07T10:00:00Z').getTime(),
    finished_at_ms: at('2026-10-07T10:00:30Z').getTime(),
    ...overrides,
  };
}

function call(overrides) {
  return {
    id: 'call-1',
    timestamp: at('2026-10-07T10:00:10Z'),
    sessionId: 'session-a',
    ...overrides,
  };
}

test('links a pipeline call to the execution carrying its message id', () => {
  const execution = run({
    source: 'pipeline',
    id: 'message-9',
    session_id: null,
  });
  assert.equal(
    findCallExecution(call({ messageId: 'message-9', sessionId: undefined }), [
      execution,
    ]),
    execution,
  );
});

test('links an agent call to the run whose window contains it', () => {
  const execution = run({});
  assert.equal(findCallExecution(call({}), [execution]), execution);
});

test('prefers the run that was live when a session has consecutive runs', () => {
  const first = run({ id: 'run-1' });
  const second = run({
    id: 'run-2',
    started_at_ms: at('2026-10-07T10:05:00Z').getTime(),
    finished_at_ms: at('2026-10-07T10:05:30Z').getTime(),
  });
  assert.equal(
    findCallExecution(call({ timestamp: at('2026-10-07T10:05:10Z') }), [
      first,
      second,
    ]).id,
    'run-2',
  );
});

test('an open run owns every later call of its session', () => {
  const execution = run({ finished_at_ms: null });
  assert.equal(
    findCallExecution(call({ timestamp: at('2026-10-07T10:20:00Z') }), [
      execution,
    ]),
    execution,
  );
});

test('a call outside every window links to nothing', () => {
  const execution = run({});
  assert.equal(
    findCallExecution(call({ timestamp: at('2026-10-07T11:00:00Z') }), [
      execution,
    ]),
    null,
  );
  assert.equal(
    findCallExecution(call({ timestamp: at('2026-10-07T09:00:00Z') }), [
      execution,
    ]),
    null,
  );
  assert.equal(
    findCallExecution(call({ sessionId: 'other' }), [execution]),
    null,
  );
});

test('a call keeps its message target when the execution list cannot resolve it', () => {
  assert.deepEqual(
    resolveCallTarget(
      call({ messageId: 'message-9', sessionId: 'other' }),
      [run({})],
      new Set(['message-9']),
    ),
    { kind: 'message', id: 'message-9' },
  );
  // An Agent call carries its run id in the same field: an id the message list
  // does not hold must not become a jump to the message tab.
  assert.equal(
    resolveCallTarget(
      call({ messageId: 'run-9', sessionId: 'other' }),
      [run({})],
      new Set(['message-9']),
    ),
    null,
  );
  assert.equal(resolveCallTarget(call({}), []), null);
});

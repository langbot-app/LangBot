import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = fs.readFileSync(
  new URL(
    '../../src/app/home/components/event-patterns/event-pattern-groups.ts',
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

for (const [supported, required, covered] of [
  ['message.received', 'message.received', true],
  ['message.received', 'group.member_joined', false],
  ['message.received', 'message.*', false],
  ['message.received', '*', false],
  ['group.*', 'group.member_joined', true],
  ['group.*', 'group.*', true],
  ['group.*', 'groupish.member_joined', false],
  ['group.*', '*', false],
  ['*', 'group.*', true],
  ['*', '*', true],
]) {
  test(`${supported} ${covered ? 'covers' : 'does not cover'} ${required}`, () => {
    assert.equal(exports.eventPatternCovers(supported, required), covered);
  });
}

test('processor events put covered declarations first and report only the intersection', () => {
  const result = exports.processorEventCompatibility(
    [
      'group.member_joined',
      'message.received',
      'friend.request_received',
      'message.received',
    ],
    ['message.received', 'message.edited'],
  );
  assert.deepEqual(result.entries, [
    { pattern: 'message.received', supported: true },
    { pattern: 'group.member_joined', supported: false },
    { pattern: 'friend.request_received', supported: false },
  ]);
  assert.deepEqual(result.matchingEvents, ['message.received']);
});

test('wildcard subscriptions show matching concrete adapter events without claiming full coverage', () => {
  const result = exports.processorEventCompatibility(
    ['group.*'],
    ['group.member_joined', 'message.received'],
  );
  assert.deepEqual(result.entries, [{ pattern: 'group.*', supported: false }]);
  assert.deepEqual(result.matchingEvents, ['group.member_joined']);
  assert.deepEqual(
    exports.processorEventCompatibility(['*'], ['message.received'])
      .matchingEvents,
    ['message.received'],
  );
});

test('adapter wildcards cover concrete subscriptions without expanding the intersection', () => {
  const result = exports.processorEventCompatibility(
    ['group.member_joined'],
    ['group.*'],
  );
  assert.equal(result.entries[0].supported, true);
  assert.deepEqual(result.matchingEvents, ['group.member_joined']);
});

test('legacy adapters default to messages and unmatched subscriptions have an empty intersection', () => {
  assert.deepEqual(
    exports.processorEventCompatibility(['*'], []).matchingEvents,
    ['message.received'],
  );
  assert.deepEqual(
    exports.processorEventCompatibility(['group.*'], []).matchingEvents,
    [],
  );
  assert.deepEqual(exports.processorEventCompatibility([], []).entries, []);
});

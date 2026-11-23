import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = fs.readFileSync(
  new URL(
    '../../src/app/home/bots/components/bot-form/message-routing-template.ts',
    import.meta.url,
  ),
  'utf8',
);
const exports = {};
new Function(
  'exports',
  ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText,
)(exports);
const append = exports.appendMessageRoutingTemplate;

test('message template explicitly separates private messages and mentions of this bot', () => {
  const routes = append([], { target_type: 'pipeline', target_uuid: 'p' });
  assert.equal(routes.length, 2);
  assert.deepEqual(routes[0].filters, [
    { field: 'chat_type', operator: 'eq', value: 'person' },
  ]);
  assert.deepEqual(routes[1].filters, [
    { field: 'chat_type', operator: 'eq', value: 'group' },
    { field: 'is_at_bot', operator: 'eq', value: true },
  ]);
  assert.ok(routes.every((r) => r.target_uuid === 'p' && r.enabled));
});

test('reapplying preserves manual destinations, disabled rules and filter order without duplication', () => {
  const routes = append([], { target_type: 'pipeline', target_uuid: 'p' });
  routes[0].target_uuid = 'manual';
  routes[1].filters.reverse();
  routes[1].enabled = false;
  const manual = {
    event_pattern: '*',
    target_type: 'discard',
    target_uuid: '',
    filters: [],
  };
  routes.unshift(manual);
  const before = structuredClone(routes);
  assert.deepEqual(
    append(routes, { target_type: 'agent', target_uuid: 'other' }),
    before,
  );
  assert.deepEqual(routes, before);
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
const file = 'src/app/home/components/dynamic-form/StructuredFieldValue.ts';
function load() {
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  const m = { exports: {} };
  new Function('module', 'exports', compiled)(m, m.exports);
  return m.exports;
}
test('JSON parsing preserves nested false, zero, null and arrays as typed values', () => {
  const { parseStructuredDraft } = load();
  const value = { n: { a: false, b: 0, c: null, d: [false, 0, null] } };
  assert.deepEqual(parseStructuredDraft(JSON.stringify(value), false), value);
});
test('prompt parsing preserves structured content, null, empty arrays, metadata and first role', () => {
  const { parseStructuredDraft } = load();
  const value = [
    { role: 'user', content: [{ type: 'text', text: 'x' }], name: 'alice' },
    { role: 'assistant', content: null, tool_calls: [] },
    { role: 'tool', content: [], tool_call_id: 'x' },
  ];
  assert.deepEqual(parseStructuredDraft(JSON.stringify(value), true), value);
});
test('prompt metadata edits preserve omitted content without inserting null', () => {
  const { parseStructuredDraft, isPromptValue } = load();
  const value = [
    {
      role: 'assistant',
      tool_calls: [],
      name: 'edited',
      provider_specific_fields: { cache: false },
    },
  ];
  assert.equal(isPromptValue(value), true);
  const result = parseStructuredDraft(JSON.stringify(value), true);
  assert.deepEqual(result, value);
  assert.equal(Object.hasOwn(result[0], 'content'), false);
  for (const content of [false, 0, {}, undefined])
    assert.equal(isPromptValue([{ ...value[0], content }]), false);
});
test('invalid JSON and non-message prompt shapes reject rather than silently retain old values', () => {
  const { parseStructuredDraft } = load();
  for (const raw of ['{broken', '', 'undefined'])
    assert.throws(() => parseStructuredDraft(raw, false));
  for (const raw of [
    '{}',
    'null',
    '[{"role":0,"content":"x"}]',
    '[{"role":"user","content":false}]',
  ])
    assert.throws(() => parseStructuredDraft(raw, true));
});
test('friendly prompt editor is restricted to losslessly represented roles and string content', () => {
  const { isSimplePrompt } = load();
  assert.equal(
    isSimplePrompt([
      { role: 'system', content: '' },
      { role: 'user', content: 'x' },
    ]),
    true,
  );
  for (const value of [
    [{ role: 'user', content: 'x' }],
    [{ role: 'system', content: null }],
    [{ role: 'system', content: [] }],
    [{ role: 'system', content: 'x', name: 'a' }],
    [],
  ])
    assert.equal(isSimplePrompt(value), false);
});

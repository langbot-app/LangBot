import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
const source = fs.readFileSync(
  'src/app/home/components/dynamic-form/DynamicFormItemComponent.tsx',
  'utf8',
);
// Exercise the actual field callback without mocking React's form lifecycle.
const callback = source.slice(
  source.indexOf('const updateModelReasoning ='),
  source.indexOf('const replaceModel ='),
);
function edit(reasoning, uuid, level) {
  let result;
  const code = ts.transpileModule(
    callback + '\nupdateModelReasoning(uuid, level);',
    { compilerOptions: { target: ts.ScriptTarget.ES2020 } },
  ).outputText;
  new Function('modelValue', 'updateValue', 'uuid', 'level', code)(
    { reasoning },
    (value) => {
      result = value.reasoning;
    },
    uuid,
    level,
  );
  return result;
}
test('provider default is an explicit override, not inheritance', () => {
  assert.deepEqual(edit({ a: 'high', b: 'low' }, 'a', 'provider_default'), {
    a: 'provider_default',
    b: 'low',
  });
});
test('changing one model preserves other overrides without mutating input', () => {
  const input = Object.freeze({ a: 'provider_default', b: 'high' });
  const output = edit(input, 'a', 'low');
  assert.deepEqual(output, { a: 'low', b: 'high' });
  assert.deepEqual(input, { a: 'provider_default', b: 'high' });
});

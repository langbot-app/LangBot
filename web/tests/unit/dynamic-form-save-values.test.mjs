import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(
  currentDirectory,
  '../../src/app/home/components/dynamic-form/DynamicFormSaveValues.ts',
);

function loadNormalizer() {
  const source = fs.readFileSync(sourcePath, 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  const loadedModule = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(
    () => {
      throw new Error('DynamicFormSaveValues must not have runtime imports');
    },
    loadedModule,
    loadedModule.exports,
  );
  return loadedModule.exports.normalizeDynamicFormValuesForSave;
}

test('normalizes only single-line text fields in a dynamic form save snapshot', () => {
  const normalizeDynamicFormValuesForSave = loadNormalizer();
  const specs = [
    { name: 'single-line', type: 'string', default: '' },
    { name: 'multiline', type: 'text', default: '' },
    { name: 'string-list', type: 'array[string]', default: [] },
    { name: 'count', type: 'integer', default: 0 },
  ];
  const values = {
    'single-line': '\t  hello  world \n',
    multiline: '  keep multiline whitespace  \n',
    'string-list': ['  first  ', ' second '],
    count: 3,
  };

  assert.deepEqual(normalizeDynamicFormValuesForSave(specs, values), {
    'single-line': 'hello  world',
    multiline: '  keep multiline whitespace  \n',
    'string-list': ['  first  ', ' second '],
    count: 3,
  });
});

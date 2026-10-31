import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(
  currentDirectory,
  '../../src/app/infra/entities/adapter-categories.ts',
);

function loadCategoryHelpers(language = 'zh-Hans') {
  const source = fs.readFileSync(sourcePath, 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      esModuleInterop: true,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;
  const loadedModule = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(
    (name) => {
      if (name === 'i18next') return { language };
      throw new Error(`Unexpected runtime import: ${name}`);
    },
    loadedModule,
    loadedModule.exports,
  );
  return loadedModule.exports;
}

test('places an adapter only once when metadata repeats a category', () => {
  const { groupByCategory } = loadCategoryHelpers();
  const adapter = { name: 'http_bot', categories: ['popular', 'popular'] };

  assert.deepEqual(groupByCategory([adapter]), [
    { categoryId: 'popular', items: [adapter] },
  ]);
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(
  currentDirectory,
  '../../src/app/home/components/dynamic-form/N8nAuthFieldVisibility.ts',
);

function loadVisibilityPolicy() {
  const source = fs.readFileSync(sourcePath, 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  const loadedModule = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(
    () => {
      throw new Error('N8nAuthFieldVisibility must not have runtime imports');
    },
    loadedModule,
    loadedModule.exports,
  );
  return loadedModule.exports;
}

test('shows response handling with the other common n8n fields', () => {
  const { shouldShowN8nConfigField } = loadVisibilityPolicy();

  for (const field of [
    'webhook-url',
    'auth-type',
    'timeout',
    'output-key',
    'response-handling',
  ]) {
    assert.equal(shouldShowN8nConfigField(field, 'none'), true, field);
  }
});

test('shows only fields for the selected n8n authentication method', () => {
  const { shouldShowN8nConfigField } = loadVisibilityPolicy();

  assert.equal(shouldShowN8nConfigField('basic-username', 'basic'), true);
  assert.equal(shouldShowN8nConfigField('basic-password', 'jwt'), false);
  assert.equal(shouldShowN8nConfigField('jwt-secret', 'jwt'), true);
  assert.equal(shouldShowN8nConfigField('header-name', 'header'), true);
  assert.equal(shouldShowN8nConfigField('unrelated-field', 'none'), false);
});

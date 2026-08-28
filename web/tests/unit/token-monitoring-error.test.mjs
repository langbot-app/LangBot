import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const utilsPath = path.resolve(
  currentDirectory,
  '../../src/app/home/monitoring/utils.ts',
);
const componentPath = path.resolve(
  currentDirectory,
  '../../src/app/home/monitoring/components/TokenMonitoring.tsx',
);

function loadMonitoringUtils() {
  const source = fs.readFileSync(utilsPath, 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  const loadedModule = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(
    () => {
      throw new Error('Monitoring utils must not have runtime imports');
    },
    loadedModule,
    loadedModule.exports,
  );
  return loadedModule.exports;
}

const { getErrorMessage } = loadMonitoringUtils();

test('token monitoring extracts messages from structured API errors', () => {
  assert.equal(
    getErrorMessage({
      code: 500,
      msg: 'SQLite aggregation failed',
      data: null,
    }),
    'SQLite aggregation failed',
  );
  assert.equal(getErrorMessage(new Error('Network failed')), 'Network failed');
  assert.equal(getErrorMessage('Request failed'), 'Request failed');
});

test('token monitoring uses the structured API error helper', () => {
  const source = fs.readFileSync(componentPath, 'utf8');
  assert.match(source, /import \{ getErrorMessage \} from '\.\.\/utils';/);
  assert.match(source, /setError\(getErrorMessage\(e\)\)/);
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const source = fs.readFileSync(
  path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    '../../src/app/home/monitoring/components/TokenMonitoring.tsx',
  ),
  'utf8',
);

test('TokenMonitoring prefers the API error message for plain error objects', () => {
  const helperStart = source.indexOf('function getErrorMessage');
  const helperEnd = source.indexOf('\n}\n', helperStart) + 2;
  const helper = source.slice(helperStart, helperEnd);

  assert.ok(helperStart >= 0, 'TokenMonitoring error helper is missing');
  assert.match(helper, /error instanceof Error/);
  assert.match(helper, /typeof error === 'object'/);
  assert.match(helper, /'msg' in error/);
  assert.match(helper, /error as \{ msg\?: unknown \}/);
  assert.match(source, /setError\(getErrorMessage\(e\)\)/);
});

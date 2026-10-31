import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const source = fs.readFileSync(
  new URL(
    '../../src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx',
    import.meta.url,
  ),
  'utf8',
);

// Shared WebSocket tests do not mount this component's socket replacement effect.
test('pipeline debug retains ownership guards before callback and connection-error updates', () => {
  for (const callback of [
    'onConnected',
    'onMessage',
    'onError',
    'onClose',
    'onBroadcast',
  ]) {
    assert.match(
      source,
      new RegExp(
        `\\.${callback}\\(\\([^)]*\\) => \\{\\s*if \\(wsClientRef\\.current !== wsClient\\) return;`,
      ),
    );
  }
  assert.match(
    source,
    /await wsClient\.connect\(\);\s*\} catch \(error\) \{\s*if \(!wsClient \|\| wsClientRef\.current !== wsClient\) return;/,
  );
});

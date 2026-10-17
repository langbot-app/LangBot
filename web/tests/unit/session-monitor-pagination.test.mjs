import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const includes = (source, token, message) =>
  assert.ok(source.includes(token), message);

test('stale session and message page responses cannot overwrite the latest page', () => {
  const monitor = read(
    'src/app/home/bots/components/bot-session/BotSessionMonitor.tsx',
  );
  for (const token of [
    'sessionRequestIdRef',
    'messageRequestIdRef',
    'requestId !== sessionRequestIdRef.current',
    'requestId !== messageRequestIdRef.current',
    'messageRequestIdRef.current += 1',
  ]) {
    includes(monitor, token, `stale response guard includes ${token}`);
  }
});

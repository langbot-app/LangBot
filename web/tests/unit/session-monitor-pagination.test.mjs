import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);
const repoRoot = path.resolve(root, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const readRepo = (file) => fs.readFileSync(path.join(repoRoot, file), 'utf8');
const includes = (source, token, message) =>
  assert.ok(source.includes(token), message);

test('session list request supports a server-side page and operator filters', () => {
  const client = read('src/app/infra/http/BackendClient.ts');
  includes(client, 'startTime?: string', 'client accepts a start date');
  includes(client, 'endTime?: string', 'client accepts an end date');
  includes(client, 'userQuery?: string', 'client accepts a user query');
  includes(
    client,
    "queryParams.append('offset', options.offset.toString())",
    'client sends the requested session offset',
  );
  includes(
    client,
    "queryParams.append('userQuery', options.userQuery)",
    'client sends the user query',
  );

  const monitor = read(
    'src/app/home/bots/components/bot-session/BotSessionMonitor.tsx',
  );
  for (const token of [
    'SESSION_PAGE_SIZE',
    'sessionTotal',
    'sessionPage',
    'startDate',
    'endDate',
    'userQuery',
  ]) {
    includes(monitor, token, `monitor includes ${token}`);
  }
});

test('session detail requests and renders a bounded message page', () => {
  const monitor = read(
    'src/app/home/bots/components/bot-session/BotSessionMonitor.tsx',
  );
  for (const token of [
    'MESSAGE_PAGE_SIZE',
    'messageTotal',
    'messagePage',
    'page * MESSAGE_PAGE_SIZE',
  ]) {
    includes(monitor, token, `message pagination includes ${token}`);
  }
});

test('backend filters sessions by user id or user name in the existing endpoint', () => {
  const controller = readRepo(
    'src/langbot/pkg/api/http/controller/groups/monitoring.py',
  );
  const service = readRepo('src/langbot/pkg/api/http/service/monitoring.py');
  includes(
    controller,
    "quart.request.args.get('userQuery')",
    'route accepts userQuery',
  );
  includes(controller, 'user_query=user_query', 'route forwards userQuery');
  includes(
    service,
    'user_query: str | None = None',
    'service accepts userQuery',
  );
  includes(
    service,
    'MonitoringSession.user_id.ilike',
    'service searches user ids',
  );
  includes(
    service,
    'MonitoringSession.user_name.ilike',
    'service searches user names',
  );
});

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

test('changing the session page or filters clears the selected detail', () => {
  const monitor = read(
    'src/app/home/bots/components/bot-session/BotSessionMonitor.tsx',
  );
  includes(monitor, 'setSelectedSessionId(null)', 'selection is cleared');
  includes(
    monitor,
    '[appliedUserQuery, botId, endDate, sessionPage, startDate]',
    'page and filters invalidate the selected session',
  );
});

test('date filters use the operator local calendar day', () => {
  const monitor = read(
    'src/app/home/bots/components/bot-session/BotSessionMonitor.tsx',
  );
  includes(
    monitor,
    'localDateBoundaryToISOString(startDate, false)',
    'local start-of-day conversion',
  );
  includes(
    monitor,
    'localDateBoundaryToISOString(endDate, true)',
    'local end-of-day conversion',
  );
});

test('session tool calls are bounded to the visible message page', () => {
  const monitor = read(
    'src/app/home/bots/components/bot-session/BotSessionMonitor.tsx',
  );
  includes(monitor, "analysisParams.set('startTime'", 'analysis page start');
  includes(monitor, "analysisParams.set('endTime'", 'analysis page end');
});

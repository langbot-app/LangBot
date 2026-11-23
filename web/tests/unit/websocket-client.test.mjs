import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import ts from 'typescript';
function load(file, deps = {}, globals = {}) {
  const source = fs
    .readFileSync(
      new URL('../../src/app/infra/websocket/' + file, import.meta.url),
      'utf8',
    )
    .replaceAll('import.meta.env.VITE_API_BASE_URL', 'undefined');
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const m = { exports: {} };
  new Function('require', 'module', 'exports', ...Object.keys(globals), code)(
    (id) => deps[id],
    m,
    m.exports,
    ...Object.values(globals),
  );
  return m.exports;
}
const urls = load('url.ts');
test('OSS and Cloud URLs follow HTTP backend scheme, port and prefix', () => {
  for (const [base, page, expected] of [
    [undefined, 'http://localhost:3000/home', 'ws://localhost:3000/api/ws'],
    [undefined, 'https://cloud.test/home', 'wss://cloud.test/api/ws'],
    [
      'http://localhost:5300',
      'http://localhost:3000',
      'ws://localhost:5300/api/ws',
    ],
    ['https://api.test/root/', 'https://ui.test', 'wss://api.test/root/api/ws'],
    ['/backend/', 'https://ui.test/home', 'wss://ui.test/backend/api/ws'],
    ['https://api.test', 'http://ui.test', 'wss://api.test/api/ws'],
  ])
    assert.equal(
      urls.backendWebSocketURL(base, page, '/api/ws').toString(),
      expected,
    );
});
function setup() {
  let workspace = 'one',
    next = 0;
  const timers = new Map(),
    win = new EventTarget(),
    doc = new EventTarget();
  win.location = { href: 'https://cloud.test/home' };
  doc.visibilityState = 'visible';
  class WS {
    static CONNECTING = 0;
    static OPEN = 1;
    static instances = [];
    readyState = 0;
    constructor(url) {
      this.url = url;
      WS.instances.push(this);
    }
    send(p) {
      this.sent = JSON.parse(p);
    }
    close() {
      this.readyState = 3;
    }
    closed() {
      this.readyState = 3;
      this.onclose?.();
    }
    open() {
      this.readyState = 1;
      this.onopen?.();
    }
    receive(data) {
      this.onmessage?.({ data: JSON.stringify(data) });
    }
  }
  const { WebSocketClient } = load(
    'WebSocketClient.ts',
    {
      './url': urls,
      '@/app/infra/http/workspaceContext': {
        getActiveWorkspaceUuid: () => workspace,
      },
    },
    {
      window: win,
      document: doc,
      WebSocket: WS,
      localStorage: { getItem: () => 'token' },
      setTimeout: (fn) => {
        timers.set(++next, fn);
        return next;
      },
      clearTimeout: (id) => timers.delete(id),
      setInterval: () => 1,
      clearInterval: () => {},
      console: { warn() {}, error() {}, debug() {} },
    },
  );
  return {
    client: new WebSocketClient('pipeline'),
    WS,
    win,
    timers,
    setWorkspace: (v) => (workspace = v),
  };
}
test('only authenticated sockets are connected; disposal removes recovery', async () => {
  const { client, WS, win } = setup(),
    pending = client.connect(),
    ws = WS.instances[0];
  ws.open();
  assert.equal(client.isConnected(), false);
  assert.equal(ws.sent.workspace_uuid, 'one');
  ws.receive({ type: 'connected', connection_id: 'id' });
  assert.equal(await pending, 'id');
  assert(client.isConnected());
  client.disconnect();
  ws.closed();
  win.dispatchEvent(new Event('focus'));
  assert.equal(WS.instances.length, 1);
});
test('closed handshakes settle and transient retries survive more than five failures', async () => {
  const { client, WS, timers } = setup();
  const first = client.connect().catch(() => {});
  WS.instances[0].closed();
  await first;
  for (let i = 0; i < 7; i++) {
    const [id, fn] = [...timers][0];
    timers.delete(id);
    fn();
    WS.instances.at(-1).closed();
    await Promise.resolve();
  }
  assert.equal(WS.instances.length, 8);
  assert.equal(timers.size, 1);
  client.disconnect();
  assert.equal(timers.size, 0);
});
test('stale closes do not affect replacement sockets and workspace changes block recovery', async () => {
  const { client, WS, win, setWorkspace } = setup();
  const pending = client.connect().catch(() => {}),
    old = WS.instances[0];
  client.disconnect();
  const current = client.connect(),
    ws = WS.instances[1];
  old.closed();
  await pending;
  ws.open();
  ws.receive({ type: 'connected', connection_id: 'new' });
  await current;
  assert(client.isConnected());
  setWorkspace('two');
  ws.closed();
  win.dispatchEvent(new Event('focus'));
  assert.equal(WS.instances.length, 2);
  client.disconnect();
});
test('authentication rejection does not reconnect', async () => {
  const { client, WS, timers, win } = setup();
  const pending = client.connect().catch(() => {}),
    ws = WS.instances[0];
  ws.open();
  ws.receive({ type: 'error', message: 'Unauthorized' });
  ws.closed();
  await pending;
  win.dispatchEvent(new Event('focus'));
  assert.equal(timers.size, 0);
  assert.equal(WS.instances.length, 1);
  client.disconnect();
});

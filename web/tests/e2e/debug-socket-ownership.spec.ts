import { createHash } from 'node:crypto';
import { createServer as createHttpServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import type { Duplex } from 'node:stream';
import { createServer as createViteServer } from 'vite';
import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

// A small native wire fixture lets the server delay the close acknowledgement.
// routeWebSocket closes a mocked transport before that browser lifecycle boundary.
function frame(opcode: number, payload: Buffer) {
  const header = Buffer.alloc(payload.length < 126 ? 2 : 4);
  header[0] = 0x80 | opcode;
  header[1] = payload.length < 126 ? payload.length : 126;
  if (payload.length >= 126) header.writeUInt16BE(payload.length, 2);
  return Buffer.concat([header, payload]);
}

function receiveFrames(socket: Duplex, onText: (text: string) => void) {
  let buffered = Buffer.alloc(0);
  socket.on('data', (chunk: Buffer) => {
    buffered = Buffer.concat([buffered, chunk]);
    while (buffered.length >= 2) {
      const opcode = buffered[0] & 0x0f;
      let length = buffered[1] & 0x7f;
      let offset = 2;
      if (length === 126) {
        if (buffered.length < 4) return;
        length = buffered.readUInt16BE(2);
        offset = 4;
      }
      if (length === 127) throw new Error('Unexpected large fixture frame');
      if (buffered.length < offset + 4 + length) return;
      const mask = buffered.subarray(offset, offset + 4);
      const payload = Buffer.from(
        buffered.subarray(offset + 4, offset + 4 + length),
      );
      buffered = buffered.subarray(offset + 4 + length);
      for (let index = 0; index < payload.length; index++)
        payload[index] ^= mask[index % 4];
      if (opcode === 8) socket.end(frame(8, payload));
      else if (opcode === 1) onText(payload.toString());
    }
  });
}

test('a cancelled native handshake cannot disable the replacement debug session', async ({
  page,
}, testInfo) => {
  const sockets = new Set<Duplex>();
  const authenticated: string[] = [];
  const failures: string[] = [];
  let pendingPerson: Duplex | undefined;
  let oldNativeClosed = false;
  let oldBrowserSocket: import('@playwright/test').WebSocket | undefined;
  const sent: unknown[] = [];
  const server = createHttpServer();
  server.on('upgrade', (request, socket) => {
    sockets.add(socket);
    socket.on('close', () => sockets.delete(socket));
    const key = request.headers['sec-websocket-key'];
    if (typeof key !== 'string') throw new Error('Missing fixture upgrade key');
    const accept = createHash('sha1')
      .update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11')
      .digest('base64');
    socket.write(
      `HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`,
    );
    const session = new URL(request.url!, 'http://fixture').searchParams.get(
      'session_type',
    )!;
    const send = (value: unknown) =>
      socket.write(frame(1, Buffer.from(JSON.stringify(value))));
    receiveFrames(socket, (text) => {
      const message = JSON.parse(text);
      if (message.type === 'authenticate') {
        authenticated.push(session);
        if (session === 'person') {
          pendingPerson = socket;
          // Authentication remains pending. Stop reading so the client's close
          // frame cannot be acknowledged until the group session is ready.
          socket.pause();
        } else
          send({
            type: 'connected',
            connection_id: 'current-group',
            pipeline_uuid: 'pipeline-workbench',
            session_type: 'group',
          });
      } else if (message.type === 'message') {
        sent.push(message.message);
        send({
          type: 'response',
          session_type: 'group',
          data: {
            id: 31,
            role: 'assistant',
            content: 'Native group reply',
            message_chain: [{ type: 'Plain', text: 'Native group reply' }],
            timestamp: new Date().toISOString(),
            is_final: true,
          },
        });
      }
    });
  });
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const backendPort = (server.address() as AddressInfo).port;
  let vite: Awaited<ReturnType<typeof createViteServer>> | undefined;
  try {
    vite = await createViteServer({
      cacheDir: testInfo.outputPath('vite-cache'),
      server: {
        host: '127.0.0.1',
        port: 0,
        proxy: {
          '/api': {
            target: `http://127.0.0.1:${backendPort}`,
            changeOrigin: true,
            ws: true,
          },
        },
      },
    });
    await vite.listen();
    const frontendPort = (vite.httpServer!.address() as AddressInfo).port;
    page.on('console', (message) => {
      if (
        message.type() === 'error' &&
        message.text().startsWith('WebSocket connection failed:')
      )
        failures.push(message.text());
    });
    page.on('websocket', (socket) => {
      if (new URL(socket.url()).searchParams.get('session_type') !== 'person')
        return;
      socket.on('framesent', (event) => {
        if (JSON.parse(String(event.payload)).type === 'authenticate')
          oldBrowserSocket = socket;
      });
      socket.on('close', () => {
        if (socket === oldBrowserSocket) oldNativeClosed = true;
      });
    });
    await installLangBotApiMocks(page, { authenticated: true });
    await page.goto(
      `http://127.0.0.1:${frontendPort}/home/pipelines?id=pipeline-workbench`,
    );
    const debug = page.getByRole('region', { name: 'Debug Chat' });
    await expect.poll(() => authenticated).toEqual(['person']);
    await debug.getByRole('button', { name: 'Group Chat' }).click();
    await expect.poll(() => authenticated).toEqual(['person', 'group']);
    await expect(debug.getByText('Connected', { exact: true })).toBeVisible();
    expect(oldNativeClosed).toBe(false);
    failures.length = 0;
    pendingPerson!.resume();
    await expect.poll(() => oldNativeClosed).toBe(true);
    await expect(debug.getByText('Connected', { exact: true })).toBeVisible();
    await debug
      .locator('[data-debug-composer="true"] textarea')
      .fill('Message after native close');
    await debug.getByRole('button', { name: 'Send', exact: true }).click();
    await expect
      .poll(() => sent)
      .toEqual([[{ type: 'Plain', text: 'Message after native close' }]]);
    await expect(debug.getByText('Native group reply')).toBeVisible();
    expect(failures).toEqual([]);
    await expect(
      page.getByText('WebSocket connection failed', { exact: true }),
    ).toHaveCount(0);
  } finally {
    for (const socket of sockets) socket.destroy();
    await vite?.close();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
});

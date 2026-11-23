/**
 * LangBot HTTP Bot adapter — reference client (TypeScript / Node 18+).
 *
 * Zero runtime dependencies (uses global `fetch`, `crypto`, and `http`).
 *
 *   - `push()`      : fire-and-collect; reply lands on your callback URL.
 *   - `pushSync()`  : POST /sync and await the collapsed reply.
 *   - `reset()`     : reset a session's conversation.
 *   - `startReceiver()` : a callback server that verifies signatures and logs
 *                         replies, so you can watch N->1 and 1->M live.
 *
 * Run the demos:
 *   npx tsx client.ts serve   8900 SHARED_SECRET
 *   npx tsx client.ts push    https://host/bots/<UUID> SHARED_SECRET ticket-1 "hello"
 *   npx tsx client.ts sync    https://host/bots/<UUID> SHARED_SECRET ticket-1 "hello"
 *   npx tsx client.ts reset   https://host/bots/<UUID> SHARED_SECRET ticket-1
 */

import { createHmac, randomUUID, timingSafeEqual } from 'node:crypto';
import { createServer } from 'node:http';

const HEADER_TIMESTAMP = 'X-LB-Timestamp';
const HEADER_SIGNATURE = 'X-LB-Signature';
const HEADER_IDEMPOTENCY = 'X-LB-Idempotency-Key';
const REPLAY_WINDOW = 300;

/** Compute the `sha256=<hex>` signature over `"{ts}." + body`. */
export function sign(secret: string, body: Buffer | string, timestamp?: number): [string, string] {
  const ts = String(timestamp ?? Math.floor(Date.now() / 1000));
  const buf = typeof body === 'string' ? Buffer.from(body) : body;
  const mac = createHmac('sha256', secret).update(Buffer.concat([Buffer.from(`${ts}.`), buf])).digest('hex');
  return [ts, `sha256=${mac}`];
}

/** Verify an inbound signature (used by the callback receiver). */
export function verify(secret: string, body: Buffer, timestamp?: string, signature?: string): boolean {
  if (!timestamp || !signature) return false;
  if (Math.abs(Math.floor(Date.now() / 1000) - Number(timestamp)) > REPLAY_WINDOW) return false;
  const [, expected] = sign(secret, body, Number(timestamp));
  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  return a.length === b.length && timingSafeEqual(a, b);
}

interface Segment { type: string; text?: string; url?: string; [k: string]: unknown }

async function post(url: string, secret: string, payload: object, idempotency = true) {
  const body = Buffer.from(JSON.stringify(payload));
  const [ts, sig] = sign(secret, body);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    [HEADER_TIMESTAMP]: ts,
    [HEADER_SIGNATURE]: sig,
  };
  if (idempotency) headers[HEADER_IDEMPOTENCY] = randomUUID();
  const resp = await fetch(url, { method: 'POST', headers, body });
  const text = await resp.text();
  console.log(`-> ${resp.status} ${text}`);
  return { status: resp.status, text };
}

/** Fire-and-collect: 202 now, reply later on your callback URL. */
export function push(url: string, secret: string, session: string, text: string, sessionType = 'person') {
  return post(url.replace(/\/$/, ''), secret, {
    session_id: session,
    session_type: sessionType,
    message: [{ type: 'Plain', text }] as Segment[],
  });
}

/** Blocking convenience: POST /sync, get the collapsed reply. */
export function pushSync(url: string, secret: string, session: string, text: string, sessionType = 'person') {
  return post(`${url.replace(/\/$/, '')}/sync`, secret, {
    session_id: session,
    session_type: sessionType,
    message: [{ type: 'Plain', text }] as Segment[],
  }, false);
}

/** Reset a session's conversation. */
export function reset(url: string, secret: string, session: string, sessionType = 'person') {
  return post(`${url.replace(/\/$/, '')}/reset`, secret, { session_id: session, session_type: sessionType }, false);
}

/** Run a callback receiver that verifies signatures and prints replies. */
export function startReceiver(port: number, secret: string) {
  const server = createServer((req, res) => {
    if (req.method !== 'POST') { res.writeHead(405).end(); return; }
    const chunks: Buffer[] = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      const raw = Buffer.concat(chunks);
      const ok = verify(secret, raw, req.headers[HEADER_TIMESTAMP.toLowerCase()] as string,
        req.headers[HEADER_SIGNATURE.toLowerCase()] as string);
      if (!ok) {
        console.log('!! signature verification FAILED — rejecting');
        res.writeHead(401, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: 'bad signature' }));
        return;
      }
      const data = JSON.parse(raw.toString());
      const parts = (data.message as Segment[]).filter((c) => c.type === 'Plain').map((c) => c.text).join(' ');
      const marker = data.is_final ? 'FINAL' : 'part ';
      console.log(`[${marker}] session=${data.session_id} seq=${data.sequence} reply_to=${data.reply_to}: ${parts}`);
      res.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ ok: true }));
    });
  });
  server.listen(port, () => console.log(`callback receiver listening on http://0.0.0.0:${port}/  (Ctrl-C to stop)`));
}

// --- CLI ---
const [cmd, ...rest] = process.argv.slice(2);
if (cmd === 'serve') {
  startReceiver(Number(rest[0] ?? 8900), rest[1] ?? 'SHARED_SECRET');
} else if (cmd === 'push') {
  push(rest[0], rest[1], rest[2], rest[3]);
} else if (cmd === 'sync') {
  pushSync(rest[0], rest[1], rest[2], rest[3]);
} else if (cmd === 'reset') {
  reset(rest[0], rest[1], rest[2]);
} else if (cmd) {
  console.error(`unknown command: ${cmd}`);
  process.exit(1);
}

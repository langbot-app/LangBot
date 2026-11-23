#!/usr/bin/env python3
"""LangBot HTTP Bot — interactive playground (public, browser-based).

This is a REAL end-to-end demo against the RUNNING LangBot instance on this
host. It is NOT a mock and NOT an in-process import: every message you type in
the browser is signed and POSTed to the live `http_bot` bot at
http://127.0.0.1:5300/bots/<uuid>, and the bot's replies come back to this
server's /callback endpoint over real HTTP, then stream to your browser via SSE.

What it does on startup:
  1. Reads the LangBot API key + the http_bot bot from data/langbot.db.
  2. Configures the bot via the LangBot API (PUT /api/v1/platform/bots/<uuid>):
     sets inbound_secret + outbound_secret + callback_url to point back here.
     (LangBot reloads the bot live — no server restart needed.)
  3. Serves a chat page on 0.0.0.0:<PORT> so you can open it from the internet.

Run:  ./.venv/bin/python examples/http-bot/playground.py
Then open:  http://<this-host-public-ip>:<PORT>/
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'src'))

from aiohttp import web  # noqa: E402
import aiohttp  # noqa: E402

from langbot.pkg.platform.sources import http_bot_signing as sg  # noqa: E402

# ---- config -----------------------------------------------------------------
LANGBOT_BASE = 'http://127.0.0.1:5300'
DB_PATH = os.path.join(REPO, 'data', 'langbot.db')
PUBLIC_IP = os.environ.get('PUBLIC_IP', '127.0.0.1')
PORT = int(os.environ.get('PLAYGROUND_PORT', '8920'))
SECRET = 'playground-shared-secret'

# SSE subscribers: list of asyncio.Queue
subscribers: list[asyncio.Queue] = []


def db_lookup() -> tuple[str, str]:
    """Return (api_key, http_bot_uuid) from the LangBot DB."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    api_key = db.execute('SELECT key FROM api_keys LIMIT 1').fetchone()['key']
    bot = db.execute("SELECT uuid FROM bots WHERE adapter='http_bot' LIMIT 1").fetchone()
    if not bot:
        raise SystemExit('No http_bot bot found. Create one in the WebUI first.')
    return api_key, bot['uuid']


async def configure_bot(api_key: str, bot_uuid: str, callback_url: str):
    """Point the live bot at this playground via the LangBot API.

    update_bot() runs a raw SQL UPDATE with whatever keys we send, so we send a
    MINIMAL payload: only adapter_config (built from scratch, not read back —
    the GET masks secrets). LangBot reloads + reruns the bot live.
    """
    cfg = {
        'inbound_secret': SECRET,
        'outbound_secret': SECRET,
        'callback_url': callback_url,
        'signature_required': True,
        'default_session_type': 'person',
        'callback_timeout': 15,
        'callback_max_retries': 3,
    }
    async with aiohttp.ClientSession() as s:
        async with s.put(
            f'{LANGBOT_BASE}/api/v1/platform/bots/{bot_uuid}',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'adapter_config': cfg},
        ) as r:
            txt = await r.text()
            print(f'[configure] PUT adapter_config -> {r.status} {txt[:200]}')
            return r.status < 400


async def broadcast(event: dict):
    for q in list(subscribers):
        try:
            q.put_nowait(event)
        except Exception:
            pass


# ---- HTTP handlers ----------------------------------------------------------
async def index(request: web.Request):
    return web.Response(text=PAGE, content_type='text/html')


async def send(request: web.Request):
    """Browser -> here -> signed POST -> live LangBot bot."""
    body_in = await request.json()
    session_id = body_in.get('session_id') or 'playground-1'
    text = body_in.get('text', '')
    bot_uuid = request.app['bot_uuid']

    payload = {
        'session_id': session_id,
        'sender': {'id': 'browser-user', 'name': 'You'},
        'message': [{'type': 'Plain', 'text': text}],
    }
    raw = json.dumps(payload, ensure_ascii=False).encode()
    ts, sig = sg.sign(SECRET, raw)
    url = f'{LANGBOT_BASE}/bots/{bot_uuid}'

    # echo what we send to the browser timeline
    await broadcast(
        {'dir': 'out', 'kind': 'request', 'session_id': session_id, 'text': text, 'url': url, 'sig': sig[:24] + '…'}
    )

    async with aiohttp.ClientSession() as s:
        async with s.post(
            url,
            data=raw,
            headers={
                'Content-Type': 'application/json',
                sg.HEADER_TIMESTAMP: ts,
                sg.HEADER_SIGNATURE: sig,
            },
        ) as r:
            status = r.status
            try:
                jr = await r.json()
            except Exception:
                jr = {'raw': await r.text()}
    await broadcast({'dir': 'in', 'kind': 'ack', 'status': status, 'data': jr})
    return web.json_response({'status': status, 'data': jr})


async def callback(request: web.Request):
    """Live LangBot bot -> here. Verify signature, stream to browser."""
    raw = await request.read()
    ok, why = sg.verify(SECRET, raw, request.headers.get(sg.HEADER_TIMESTAMP), request.headers.get(sg.HEADER_SIGNATURE))
    data = json.loads(raw)
    text = ' '.join(c.get('text', '') for c in data.get('message', []) if c.get('type') == 'Plain')
    await broadcast(
        {
            'dir': 'in',
            'kind': 'reply',
            'session_id': data.get('session_id'),
            'sequence': data.get('sequence'),
            'is_final': data.get('is_final'),
            'sig_ok': ok,
            'sig_why': why,
            'text': text,
        }
    )
    return web.json_response({'ok': True})


async def events(request: web.Request):
    """SSE stream to the browser."""
    resp = web.StreamResponse(
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        }
    )
    await resp.prepare(request)
    q: asyncio.Queue = asyncio.Queue()
    subscribers.append(q)
    try:
        await resp.write(b': connected\n\n')
        while True:
            try:
                ev = await asyncio.wait_for(q.get(), timeout=15)
                await resp.write(f'data: {json.dumps(ev, ensure_ascii=False)}\n\n'.encode())
            except asyncio.TimeoutError:
                await resp.write(b': ping\n\n')
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        if q in subscribers:
            subscribers.remove(q)
    return resp


PAGE = r"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>LangBot HTTP Bot · 调试台</title>
<style>
  :root{
    --bg:#f7f8fa; --panel:#ffffff; --line:#e8eaed; --ink:#1f2329; --mut:#8a909a;
    --brand:#2563eb; --brand-soft:#eef3ff; --ok:#16a34a; --bad:#dc2626; --code:#f3f4f6;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif}
  .top{height:52px;background:var(--panel);border-bottom:1px solid var(--line);
    display:flex;align-items:center;gap:10px;padding:0 18px}
  .logo{width:26px;height:26px;border-radius:7px;background:var(--brand);display:grid;place-items:center;color:#fff;font-weight:700;font-size:14px}
  .top b{font-size:15px} .top .ver{font-size:12px;color:var(--mut)}
  .dot{width:8px;height:8px;border-radius:50%;background:#cbd2dc;display:inline-block;margin-right:5px;vertical-align:middle}
  .dot.on{background:var(--ok)} .dot.off{background:var(--bad)}
  .conn{margin-left:auto;font-size:12px;color:var(--mut)}
  .wrap{max-width:1080px;margin:0 auto;padding:18px;display:grid;grid-template-columns:1fr 360px;gap:16px}
  @media(max-width:880px){.wrap{grid-template-columns:1fr}}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;display:flex;flex-direction:column;min-height:0}
  .card h3{margin:0;padding:12px 16px;font-size:13px;font-weight:600;color:#4b5563;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px}
  .chat{height:62vh}
  .msgs{flex:1;overflow:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
  .row{display:flex;flex-direction:column;gap:4px;max-width:82%}
  .row.me{align-self:flex-end;align-items:flex-end}
  .row.bot{align-self:flex-start}
  .bub{padding:9px 13px;border-radius:12px;white-space:pre-wrap;word-break:break-word}
  .me .bub{background:var(--brand);color:#fff;border-bottom-right-radius:3px}
  .bot .bub{background:#f1f3f6;color:var(--ink);border-bottom-left-radius:3px}
  .meta{font-size:11px;color:var(--mut)}
  .meta .ok{color:var(--ok)} .meta .bad{color:var(--bad)}
  .sys{align-self:center;font-size:12px;color:var(--mut);background:#f1f3f6;border-radius:8px;padding:4px 12px}
  .bar{display:flex;gap:8px;padding:12px;border-top:1px solid var(--line)}
  .bar input{flex:1;border:1px solid var(--line);border-radius:9px;padding:10px 12px;font-size:14px;outline:none}
  .bar input:focus{border-color:var(--brand);box-shadow:0 0 0 3px var(--brand-soft)}
  .bar button{background:var(--brand);color:#fff;border:0;border-radius:9px;padding:0 18px;font-size:14px;font-weight:500;cursor:pointer}
  .bar button:disabled{opacity:.5;cursor:default}
  .side{height:62vh}
  .kv{padding:12px 16px;border-bottom:1px solid var(--line);font-size:12px}
  .kv .k{color:var(--mut)} .kv .v{color:var(--ink);word-break:break-all}
  .kv code{background:var(--code);border-radius:5px;padding:1px 5px;font-size:11px}
  .sessrow{display:flex;align-items:center;gap:8px;padding:10px 16px;border-bottom:1px solid var(--line);font-size:12px}
  .sessrow input{flex:1;border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12px}
  .sessrow button{border:1px solid var(--line);background:#fff;border-radius:7px;padding:5px 9px;font-size:12px;cursor:pointer;color:#4b5563}
  .trace{flex:1;overflow:auto;padding:10px 12px;font:11px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
  .ev{padding:6px 8px;border-radius:7px;margin-bottom:6px;border:1px solid var(--line)}
  .ev .t{font-weight:600;font-size:10px;letter-spacing:.3px;text-transform:uppercase}
  .ev.out{background:#f5f8ff;border-color:#dbe6ff}.ev.out .t{color:var(--brand)}
  .ev.ack{background:#f4f6f8}.ev.ack .t{color:#6b7280}
  .ev.reply{background:#f1faf3;border-color:#cdeed6}.ev.reply .t{color:var(--ok)}
  .ev pre{margin:3px 0 0;white-space:pre-wrap;word-break:break-all;color:#374151}
</style></head>
<body>
<div class="top">
  <div class="logo">L</div>
  <b>HTTP Bot 调试台</b><span class="ver">examples/http-bot</span>
  <span class="conn"><span class="dot off" id="cdot"></span><span id="conn">连接中…</span></span>
</div>
<div class="wrap">
  <!-- chat -->
  <div class="card chat">
    <h3>对话 · 真实发往运行中的 http_bot</h3>
    <div class="msgs" id="msgs"></div>
    <div class="bar">
      <input id="msg" placeholder="输入消息,回车发送…" autofocus/>
      <button id="send">发送</button>
    </div>
  </div>
  <!-- debug -->
  <div class="card side">
    <h3>调试信息</h3>
    <div class="kv"><span class="k">入站地址</span><br><span class="v"><code id="endpoint">/bots/&lt;uuid&gt;</code></span></div>
    <div class="kv"><span class="k">签名</span> <span class="v">HMAC-SHA256 · <code>X-LB-Signature</code></span></div>
    <div class="sessrow">
      <span class="k">会话</span>
      <input id="sid" value="playground-1"/>
      <button id="reset">新会话</button>
    </div>
    <div class="trace" id="trace"></div>
  </div>
</div>
<script>
const $=s=>document.querySelector(s);
const msgs=$('#msgs'),trace=$('#trace'),inp=$('#msg'),btn=$('#send'),
      conn=$('#conn'),cdot=$('#cdot'),sidIn=$('#sid');
function el(c){const d=document.createElement('div');d.className=c;return d}
function atBottom(n){n.scrollTop=n.scrollHeight}
function bubble(side,text,metaHtml){
  const r=el('row '+side),b=el('bub');b.textContent=text;r.appendChild(b);
  if(metaHtml){const m=el('meta');m.innerHTML=metaHtml;r.appendChild(m)}
  msgs.appendChild(r);atBottom(msgs)}
function sys(t){const d=el('sys');d.textContent=t;msgs.appendChild(d);atBottom(msgs)}
function logEv(kind,title,obj){
  const e=el('ev '+kind),t=el('t');t.textContent=title;e.appendChild(t);
  if(obj!==undefined){const p=document.createElement('pre');
    p.textContent=typeof obj==='string'?obj:JSON.stringify(obj,null,2);e.appendChild(p)}
  trace.appendChild(e);atBottom(trace)}

const es=new EventSource('/events');
es.onopen=()=>{conn.textContent='SSE 已连接';cdot.className='dot on'};
es.onerror=()=>{conn.textContent='SSE 断开,重连…';cdot.className='dot off'};
es.onmessage=e=>{const ev=JSON.parse(e.data);
  if(ev.kind==='request'){
    if(ev.endpoint)$('#endpoint').textContent=ev.url||ev.endpoint;
    logEv('out','出站 · 已签名 POST',{url:ev.url,session_id:ev.session_id,'X-LB-Signature':ev.sig});
  }else if(ev.kind==='ack'){
    const id=ev.data&&ev.data.data&&ev.data.data.accepted_message_id;
    sys(`LangBot 已接收 · HTTP ${ev.status}`);
    logEv('ack','入站确认 202',{status:ev.status,accepted_message_id:id||'-'});
  }else if(ev.kind==='reply'){
    const sig=ev.sig_ok?'<span class=ok>验签通过</span>':'<span class=bad>验签失败</span>';
    bubble('bot',ev.text,`seq=${ev.sequence} · ${ev.is_final?'<b>FINAL</b>':'中间段'} · ${sig}`);
    logEv('reply',`回调 · seq ${ev.sequence}${ev.is_final?' · FINAL':''}`,
      {session_id:ev.session_id,sequence:ev.sequence,is_final:ev.is_final,sig_ok:ev.sig_ok,text:ev.text});
  }};

async function send(){
  const t=inp.value.trim();if(!t)return;inp.value='';btn.disabled=true;
  bubble('me',t,'已签名 → POST /bots/&lt;uuid&gt;');
  try{await fetch('/send',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({session_id:sidIn.value.trim()||'playground-1',text:t})});}
  catch(e){sys('发送失败:'+e)}
  btn.disabled=false;inp.focus();}
btn.onclick=send;inp.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
$('#reset').onclick=()=>{sidIn.value='playground-'+Math.random().toString(36).slice(2,7);
  sys('已切换到新会话 '+sidIn.value);};
sys('调试台就绪 · 每条消息都会真实发往运行中的 http_bot,右侧可观察签名 / 202 / 回调全过程。');
</script>
</body></html>"""


async def main():
    api_key, bot_uuid = db_lookup()
    callback_url = f'http://{PUBLIC_IP}:{PORT}/callback'
    print(f'[init] http_bot uuid = {bot_uuid}')
    print(f'[init] callback_url  = {callback_url}')
    ok = await configure_bot(api_key, bot_uuid, callback_url)
    if not ok:
        print('[warn] bot config update failed; check the API key / payload shape')

    app = web.Application()
    app['bot_uuid'] = bot_uuid
    app.router.add_get('/', index)
    app.router.add_post('/send', send)
    app.router.add_post('/callback', callback)
    app.router.add_get('/events', events)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f'\n  ▶ 打开:  http://{PUBLIC_IP}:{PORT}/\n')
    while True:
        await asyncio.sleep(3600)


if __name__ == '__main__':
    asyncio.run(main())

// Runs the console page's inline script inside a fake DOM with manually resolved
// API responses, so response-to-session attribution (review findings F1/F2) can be
// observed objectively: interleaved session loads, replies while switching,
// polling/stale writebacks, late attachment reads and per-session drafts.
//
// FileReader is stubbed so an attachment read can be completed by hand after a
// session switch, which makes the "late attachment writeback" deterministic.
//
// usage: node console_attribution_harness.mjs <path/to/index.html>
// prints one line: __RESULT__<json>
import fs from 'node:fs';
import vm from 'node:vm';

const htmlPath = process.argv[2];
if (!htmlPath) {
  console.error('usage: node console_attribution_harness.mjs <index.html>');
  process.exit(2);
}
const html = fs.readFileSync(htmlPath, 'utf8');
const inline = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)]
  .filter((m) => !/\bsrc\s*=/.test(m[1]))
  .map((m) => m[2])
  .join('\n;\n');
if (!inline.trim()) {
  console.error('no inline <script> found in ' + htmlPath);
  process.exit(2);
}

function makeElement(id) {
  const el = {
    id,
    style: {},
    dataset: {},
    value: '',
    textContent: '',
    className: '',
    disabled: false,
    scrollTop: 0,
    scrollHeight: 0,
    files: [],
    _innerHTML: '',
    _classes: new Set(),
    _listeners: {},
  };
  // innerHTML = '' really drops the children, like a browser does, so
  // "nothing was rendered" can be observed objectively.
  Object.defineProperty(el, 'innerHTML', {
    get() {
      return this._innerHTML;
    },
    set(value) {
      this._innerHTML = value;
      if (value === '') this._children = [];
    },
  });
  el.classList = {
    add: (...names) => names.forEach((n) => el._classes.add(n)),
    remove: (...names) => names.forEach((n) => el._classes.delete(n)),
    toggle: (n) => (el._classes.has(n) ? el._classes.delete(n) : el._classes.add(n)),
    contains: (n) => el._classes.has(n),
  };
  el.addEventListener = (ev, fn) => {
    (el._listeners[ev] || (el._listeners[ev] = [])).push(fn);
  };
  el.removeEventListener = () => {};
  el.appendChild = (child) => {
    (el._children || (el._children = [])).push(child);
    return child;
  };
  el.removeChild = () => {};
  el.querySelector = () => makeElement(id + ' > child');
  el.querySelectorAll = () => [];
  el.getAttribute = () => null;
  el.setAttribute = () => {};
  el.click = () => {};
  el.focus = () => {};
  return el;
}

function loadPage() {
  const elements = new Map();
  const documentStub = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, makeElement(id));
      return elements.get(id);
    },
    createElement(tag) {
      return makeElement('<' + tag + '>');
    },
    querySelector: () => makeElement('query'),
    querySelectorAll: () => [],
    addEventListener: () => {},
  };

  // /sessions is not part of the attribution scenarios, so it resolves at once;
  // every other endpoint stays pending until the scenario resolves it explicitly.
  const inflight = [];
  const intervals = [];
  const api = (path, body, method) => {
    if (path === '/sessions') return Promise.resolve({ sessions: [] });
    return new Promise((resolve, reject) => {
      inflight.push({ path, body, method, resolve, reject });
    });
  };

  // Reads stay pending until resolveReaders() completes them, so a read started
  // in one session can be delivered after the operator switched to another one.
  const readers = [];
  class FileReaderStub {
    constructor() {
      this.onload = null;
      this.onerror = null;
      this.result = null;
      readers.push(this);
    }
    readAsDataURL(file) {
      this._file = file;
    }
    abort() {}
  }

  const sandbox = {
    document: documentStub,
    window: {},
    console,
    FileReader: FileReaderStub,
    langbot: {
      api,
      t: (key, fallback) => (fallback === undefined ? key : fallback),
      applyI18n() {},
      onReady() {},
      onLanguageChange() {},
    },
    setInterval: (fn, ms) => {
      const handle = { fn, ms, cleared: false };
      intervals.push(handle);
      return handle;
    },
    clearInterval: (handle) => {
      if (handle) handle.cleared = true;
    },
    setTimeout: (fn, ms) => ({ fn, ms }),
    clearTimeout: () => {},
  };
  const ctx = vm.createContext(sandbox);
  vm.runInContext(inline, ctx, { filename: 'console-inline.js' });
  return { ctx, document: documentStub, elements, inflight, intervals, readers };
};

const settle = async (rounds = 60) => {
  for (let i = 0; i < rounds; i += 1) await new Promise((r) => setImmediate(r));
};

// Completes every attachment read started so far; resultFor receives the file.
function resolveReaders(page, resultFor) {
  const started = page.readers.splice(0, page.readers.length);
  started.forEach((reader) => {
    if (typeof reader.onload === 'function') reader.onload({ target: { result: resultFor(reader._file) } });
  });
  return started.length;
}

function pending(page, path, key) {
  const found = page.inflight.find(
    (r) => r.path === path && (key === undefined || (r.body && r.body.session_key === key)),
  );
  if (!found) {
    const seen = page.inflight.map((r) => [r.path, r.body && r.body.session_key].join(':'));
    throw new Error(`no pending ${path} (key=${key}); pending=[${seen.join(', ')}]`);
  }
  page.inflight.splice(page.inflight.indexOf(found), 1);
  return found;
}

function messagesPayload(key, extra = {}) {
  return {
    session_key: key,
    type: 'person',
    name: 'name-' + key,
    messages: [],
    members: {},
    takeover_active: false,
    takeover_remaining: 0,
    takeover_timeout: 600,
    ...extra,
  };
}

function snapshot(page) {
  const { ctx } = page;
  const data = ctx.state.currentData;
  return {
    current: ctx.state.current,
    currentKey: ctx.state.currentKey === undefined ? null : ctx.state.currentKey,
    displayedKey: data ? data.session_key : null,
    takeoverActive: data ? !!data.takeover_active : null,
    titleKey: page.document.getElementById('chatTitle').textContent,
    buttonText: page.document.getElementById('takeoverBtn').textContent,
    countdownShown: page.document.getElementById('countdown')._classes.has('show'),
    sendDisabled: page.document.getElementById('sendBtn').disabled === true,
    inputValue: page.document.getElementById('msgInput').value,
    pendingImage: ctx.state.pendingImage === undefined ? null : ctx.state.pendingImage,
    pendingFileName: ctx.state.pendingFile ? ctx.state.pendingFile.name : null,
    pendingFileBase64: ctx.state.pendingFile ? ctx.state.pendingFile.base64 : null,
    previewHtml: page.document.getElementById('previewStrip').innerHTML,
    previewChildren: (page.document.getElementById('previewStrip')._children || []).length,
  };
}

const result = {};
async function scenario(name, fn) {
  try {
    result[name] = await fn();
  } catch (err) {
    result[name] = { error: String((err && err.stack) || err) };
  }
}

// --- 1. Two interleaved loads; the older response lands last --------------
// Opening A then B must leave B on screen, and the reply must go to whatever
// session is actually displayed.
await scenario('interleaved_loads_and_reply', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('A');
  const requestA = pending(page, '/messages', 'A');
  ctx.openSession('B');
  const requestB = pending(page, '/messages', 'B');
  requestB.resolve(messagesPayload('B'));
  await settle();
  requestA.resolve(messagesPayload('A')); // stale response arrives last
  await settle();

  const afterLoads = snapshot(page);
  const displayedAtTyping = ctx.state.currentData ? ctx.state.currentData.session_key : null;
  page.document.getElementById('msgInput').value = 'answer for the conversation on screen';
  ctx.sendMessage();
  await settle();
  const reply = page.inflight.find((r) => r.path === '/reply') || null;

  const out = {
    afterLoads,
    displayedAtTyping,
    replySent: !!reply,
    replyKey: reply ? reply.body.session_key : null,
    replyText: reply ? reply.body.text : null,
  };
  out.replyKeyMatchesDisplayed = !!reply && reply.body.session_key === displayedAtTyping;

  if (reply) {
    reply.resolve({ takeover_active: false, takeover_remaining: 0 });
    await settle();
  }
  const refresh = page.inflight.find((r) => r.path === '/messages') || null;
  if (refresh) {
    refresh.resolve(messagesPayload(refresh.body.session_key));
    await settle();
  }
  out.afterSend = snapshot(page);
  return out;
});

// --- 2. Switching sessions clears the previous conversation and blocks send
await scenario('switch_while_loading', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('A');
  pending(page, '/messages', 'A').resolve(messagesPayload('A'));
  await settle();
  const loaded = snapshot(page);

  ctx.openSession('B'); // B's /messages is still in flight
  await settle(5);
  const whileLoading = snapshot(page);
  whileLoading.messagesHtml = page.document.getElementById('messages').innerHTML;
  whileLoading.infoHtml = page.document.getElementById('infoPanel').innerHTML;

  page.document.getElementById('msgInput').value = 'typed while B loads';
  ctx.sendMessage();
  await settle();
  whileLoading.replySentWhileLoading = page.inflight.some((r) => r.path === '/reply');

  pending(page, '/messages', 'B').resolve(messagesPayload('B'));
  await settle();
  return { loaded, whileLoading, afterLoad: snapshot(page) };
});

// --- 3. Polling must not write a previous session's snapshot onto the new one
await scenario('poll_stale_writeback', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.startPolling();
  const poll = page.intervals.filter((h) => h.ms === 5000).pop();
  ctx.openSession('A');
  pending(page, '/messages', 'A').resolve(messagesPayload('A'));
  await settle();
  const before = snapshot(page);

  poll.fn(); // poll starts for A and stays in flight
  await settle();
  const stale = pending(page, '/takeover_status', 'A');

  ctx.openSession('B');
  pending(page, '/messages', 'B').resolve(messagesPayload('B'));
  await settle();

  stale.resolve({ takeover_active: true, takeover_remaining: 300 }); // A's snapshot, late
  await settle();
  return { before, polledKey: stale.body.session_key, after: snapshot(page) };
});

// --- 4. A takeover response for the previous session must not repaint the new one
await scenario('takeover_stale_response', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('A');
  pending(page, '/messages', 'A').resolve(messagesPayload('A'));
  await settle();

  ctx.toggleTakeover();
  const request = pending(page, '/takeover', 'A');

  ctx.openSession('B');
  pending(page, '/messages', 'B').resolve(messagesPayload('B'));
  await settle();

  request.resolve({ takeover_active: true, takeover_remaining: 300 });
  await settle();
  return { requestKey: request.body.session_key, after: snapshot(page) };
});

// --- 5. Regression guards: the current session still works normally --------
await scenario('current_session_still_works', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('Z');
  pending(page, '/messages', 'Z').resolve(
    messagesPayload('Z', { takeover_active: true, takeover_remaining: 120 }),
  );
  await settle();
  const afterLoad = snapshot(page);

  page.document.getElementById('msgInput').value = 'hello';
  ctx.sendMessage();
  await settle();
  const reply = pending(page, '/reply', 'Z');
  const replyKey = reply.body.session_key;
  reply.resolve({ takeover_active: false, takeover_remaining: 0 });
  await settle();
  const refresh = pending(page, '/messages', 'Z');
  refresh.resolve(messagesPayload('Z'));
  await settle();
  return { afterLoad, replyKey, afterSend: snapshot(page) };
});

// --- 6. A late attachment read from A must not land in B ------------------
// Selecting a file in A, switching to B before the read completes and then
// finishing the read must not put A's attachment into B's composer (nor into
// B's reply request).
await scenario('late_attachment_writeback', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('A');
  pending(page, '/messages', 'A').resolve(messagesPayload('A'));
  await settle();

  ctx.handleImageFile({ name: 'A-private.png', type: 'image/png' });
  const readStarted = page.readers.length;

  ctx.openSession('B');
  pending(page, '/messages', 'B').resolve(messagesPayload('B'));
  await settle();
  const beforeLate = snapshot(page);

  resolveReaders(page, () => 'data:image/png;base64,QS1QUklWQVRF'); // A's read finishes late
  await settle();
  const afterLate = snapshot(page);

  page.document.getElementById('msgInput').value = 'hello from B';
  ctx.sendMessage();
  await settle();
  const reply = page.inflight.find((r) => r.path === '/reply') || null;
  const out = {
    readStarted,
    beforeLate,
    afterLate,
    replySent: !!reply,
    replyKey: reply ? reply.body.session_key : null,
    replyImage: reply ? reply.body.image_base64 : null,
    replyText: reply ? reply.body.text : null,
  };
  out.leakedImage = !!reply && reply.body.image_base64 === 'data:image/png;base64,QS1QUklWQVRF';
  if (reply) {
    reply.resolve({ takeover_active: false, takeover_remaining: 0 });
    await settle();
  }
  const refresh = page.inflight.find((r) => r.path === '/messages') || null;
  if (refresh) {
    refresh.resolve(messagesPayload(refresh.body.session_key));
    await settle();
  }
  out.afterSend = snapshot(page);
  return out;
});

// --- 7. An attachment committed in A stays with A -------------------------
// A's file must not travel with a reply typed while B is on screen, and it must
// come back when the operator returns to A (per-session draft, explicit restore).
await scenario('attachment_stays_with_its_session', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('A');
  pending(page, '/messages', 'A').resolve(messagesPayload('A'));
  await settle();

  ctx.handleFileSelected({ name: 'A-doc.txt', type: 'text/plain' });
  resolveReaders(page, () => 'data:text/plain;base64,QS1ET0M='); // completes while A is shown
  await settle();
  const inA = snapshot(page);

  ctx.openSession('B');
  pending(page, '/messages', 'B').resolve(messagesPayload('B'));
  await settle();
  const inB = snapshot(page);

  page.document.getElementById('msgInput').value = 'text for B';
  ctx.sendMessage();
  await settle();
  const reply = page.inflight.find((r) => r.path === '/reply') || null;
  const out = {
    inA,
    inB,
    replySent: !!reply,
    replyKey: reply ? reply.body.session_key : null,
    replyImage: reply ? reply.body.image_base64 : null,
    replyFile: reply ? reply.body.file_base64 : null,
    replyFileName: reply ? reply.body.file_name : null,
  };
  out.attachmentLeakedToB = !!reply && (reply.body.image_base64 !== '' || reply.body.file_base64 !== '');
  if (reply) {
    reply.resolve({ takeover_active: false, takeover_remaining: 0 });
    await settle();
  }

  ctx.openSession('A'); // A's /messages stays in flight; the draft restore is synchronous
  await settle(5);
  out.backInA = snapshot(page);
  return out;
});

// --- 8. A draft typed in A must not be sent while B is on screen ----------
await scenario('draft_typed_in_a_is_not_sent_from_b', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('A');
  pending(page, '/messages', 'A').resolve(messagesPayload('A'));
  await settle();
  page.document.getElementById('msgInput').value = 'private draft for A';

  ctx.openSession('B');
  pending(page, '/messages', 'B').resolve(messagesPayload('B'));
  await settle();
  const inB = snapshot(page);

  ctx.sendMessage();
  await settle();
  const replies = page.inflight
    .filter((r) => r.path === '/reply')
    .map((r) => ({ key: r.body.session_key, text: r.body.text }));

  ctx.openSession('A'); // A's /messages stays in flight; the draft restore is synchronous
  await settle(5);
  const backInA = snapshot(page);
  return {
    inB,
    replies,
    backInA,
    leakedDraft: replies.some((r) => r.text === 'private draft for A'),
  };
});

// --- 9. A reply result for A must not repaint B, nor clear B's composer ---
await scenario('reply_result_binds_to_sending_session', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('A');
  pending(page, '/messages', 'A').resolve(messagesPayload('A'));
  await settle();

  page.document.getElementById('msgInput').value = 'answer for A';
  ctx.sendMessage();
  await settle();
  const reply = pending(page, '/reply', 'A');

  ctx.openSession('B');
  pending(page, '/messages', 'B').resolve(messagesPayload('B'));
  await settle();

  // The operator drafts B's answer, including an attachment, while A's reply is in flight.
  page.document.getElementById('msgInput').value = 'B draft typed while A replied';
  ctx.handleFileSelected({ name: 'B-doc.txt', type: 'text/plain' });
  resolveReaders(page, () => 'data:text/plain;base64,Qi1ET0M=');
  await settle();
  const beforeResponse = snapshot(page);

  reply.resolve({ takeover_active: true, takeover_remaining: 300 }); // A's result, late
  await settle();
  const afterResponse = snapshot(page);

  return {
    replyKey: reply.body.session_key,
    replyText: reply.body.text,
    beforeResponse,
    afterResponse,
  };
});

// --- 10. An attachment staged under another session is never posted --------
// Defence in depth for the send path: whatever staged an attachment, a send can
// only carry attachments whose recorded owner is the session being replied to.
await scenario('foreign_attachment_is_never_posted', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('B');
  pending(page, '/messages', 'B').resolve(messagesPayload('B'));
  await settle();

  const stage = (field, value) => {
    ctx.state.attachmentOwner = ctx.state.attachmentOwner || { image: null, file: null };
    if (field === 'image') ctx.state.pendingImage = value;
    else ctx.state.pendingFile = value;
    ctx.state.attachmentOwner[field] = 'A'; // staged by another session
  };
  stage('image', 'data:image/png;base64,QS1QUklWQVRF');
  stage('file', { base64: 'data:text/plain;base64,QS1ET0M=', name: 'A-doc.txt' });

  page.document.getElementById('msgInput').value = 'text for B';
  ctx.sendMessage();
  await settle();
  const reply = page.inflight.find((r) => r.path === '/reply') || null;
  return {
    replySent: !!reply,
    replyKey: reply ? reply.body.session_key : null,
    replyText: reply ? reply.body.text : null,
    replyImage: reply ? reply.body.image_base64 : null,
    replyFile: reply ? reply.body.file_base64 : null,
    replyFileName: reply ? reply.body.file_name : null,
  };
});

// --- 11. Text/attachments added while a reply is in flight survive it ------
// The cleanup after a reply may only consume what was actually sent, so new
// input in the same session is not deleted by the response handling.
await scenario('composer_typed_during_send_is_kept', async () => {
  const page = loadPage();
  const { ctx } = page;
  ctx.openSession('C');
  pending(page, '/messages', 'C').resolve(messagesPayload('C'));
  await settle();

  const input = page.document.getElementById('msgInput');
  input.value = 'first message';
  ctx.sendMessage();
  await settle();
  const reply = pending(page, '/reply', 'C');

  input.value = 'second message typed while sending';
  ctx.handleFileSelected({ name: 'late.txt', type: 'text/plain' });
  resolveReaders(page, () => 'data:text/plain;base64,TEFURQ==');
  await settle();

  reply.resolve({ takeover_active: false, takeover_remaining: 0 });
  await settle();
  const afterReply = snapshot(page);

  const refresh = page.inflight.find((r) => r.path === '/messages') || null;
  if (refresh) {
    refresh.resolve(messagesPayload(refresh.body.session_key));
    await settle();
  }
  return { replyText: reply.body.text, afterReply, afterRefresh: snapshot(page) };
});

console.log('__RESULT__' + JSON.stringify(result));

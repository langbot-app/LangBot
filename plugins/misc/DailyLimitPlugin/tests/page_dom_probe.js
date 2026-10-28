'use strict';
// Renders a plugin page's inline script against a recording DOM.
//
//   node page_dom_probe.js <page.html> <config.json>
//
// The harness exists so the test can check the *rendered* page instead of the
// page source: it runs the real inline script, records every markup string the
// page hands to `innerHTML` (verbatim, so the caller can parse it with any real
// HTML parser), records every element the page creates together with the
// properties, attributes and listeners attached to it, and records the Page-SDK
// calls the page makes. It is intentionally small: only what these pages use.
//
// config.json:
//   { "responses": { "GET /entries": {...}, "/entries": {...} },
//     "drive": "<javascript run inside the page after the ready handlers>" }
//
// The report is printed to stdout as JSON.

const fs = require('fs');
const vm = require('vm');

const pagePath = process.argv[2];
const config = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const html = fs.readFileSync(pagePath, 'utf8');

const inlineScripts = [...html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/gi)].map(
  (match) => match[1],
);
if (inlineScripts.length === 0) {
  throw new Error(`no inline script found in ${pagePath}`);
}

const report = { markup_writes: [], elements: [], text_nodes: [], api_calls: [], alerts: [], errors: [] };
const created = [];
const byId = new Map();

// Browsers serialize `&`, `<` and `>` of a text node; quotes survive verbatim,
// which is exactly why text escaping is not attribute escaping.
const TEXT_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;' };

function escapeText(text) {
  return String(text).replace(/[&<>]/g, (ch) => TEXT_ESCAPES[ch]);
}

function makeElement(tag) {
  const el = {
    nodeType: 1,
    tagName: String(tag).toUpperCase(),
    className: '',
    children: [],
    attributes: {},
    props: {},
    listeners: {},
    style: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
  };
  let text = '';
  let markup = '';

  Object.defineProperty(el, 'id', {
    get() { return el.props.id || ''; },
    set(value) { el.props.id = String(value); byId.set(String(value), el); },
  });
  for (const prop of ['value', 'checked', 'placeholder', 'min', 'max', 'type', 'rows', 'disabled']) {
    Object.defineProperty(el, prop, {
      get() { return el.props[prop]; },
      set(value) { el.props[prop] = value; },
    });
  }
  Object.defineProperty(el, 'textContent', {
    get() { return text; },
    set(value) { text = value === null || value === undefined ? '' : String(value); },
  });
  Object.defineProperty(el, 'innerHTML', {
    get() { return markup === '' ? escapeText(text) : markup; },
    set(value) {
      markup = String(value);
      report.markup_writes.push({ tag: el.tagName, id: el.props.id || null, markup });
      el.children = [];
      text = '';
    },
  });

  el.appendChild = (child) => { el.children.push(child); return child; };
  el.append = (...nodes) => { el.children.push(...nodes); };
  el.replaceChildren = (...nodes) => { el.children = nodes.slice(); };
  el.remove = () => {};
  el.addEventListener = (type, fn) => { (el.listeners[type] || (el.listeners[type] = [])).push(fn); };
  el.removeEventListener = (type, fn) => {
    const list = el.listeners[type] || [];
    const index = list.indexOf(fn);
    if (index >= 0) list.splice(index, 1);
  };
  el.setAttribute = (name, value) => { el.attributes[String(name)] = String(value); };
  el.getAttribute = (name) => (name in el.attributes ? el.attributes[name] : null);
  el.removeAttribute = (name) => { delete el.attributes[name]; };
  el.querySelector = () => null;
  el.querySelectorAll = () => [];
  el.focus = () => {};
  return el;
}

function makeTextNode(text) {
  return { nodeType: 3, tagName: '#text', textContent: String(text), children: [], attributes: {} };
}

const document = {
  createElement(tag) { const el = makeElement(tag); created.push(el); return el; },
  createTextNode(text) { const node = makeTextNode(text); created.push(node); return node; },
  getElementById(id) {
    if (!byId.has(id)) {
      const el = makeElement('div');
      el.id = id;
    }
    return byId.get(id);
  },
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener: () => {},
  body: makeElement('body'),
  head: makeElement('head'),
  documentElement: makeElement('html'),
};

const responses = config.responses || {};
const readyHandlers = [];
const languageHandlers = [];

const langbot = {
  t: (key, fallback) => (fallback === undefined ? key : fallback),
  api: async (endpoint, body, method) => {
    method = method || 'GET';
    report.api_calls.push({ method, endpoint, body: body === undefined ? null : body });
    if (`${method} ${endpoint}` in responses) return responses[`${method} ${endpoint}`];
    if (endpoint in responses) return responses[endpoint];
    return {};
  },
  onReady: (fn) => { readyHandlers.push(fn); },
  onLanguageChange: (fn) => { languageHandlers.push(fn); },
};

const probe = {
  elements: () => created.filter((node) => node.nodeType === 1),
  byId: (id) => byId.get(id) || null,
  find: (predicate) => created.find((node) => node.nodeType === 1 && predicate(node)) || null,
  click: async (label) => {
    const button = created.find(
      (node) => node.nodeType === 1 && node.tagName === 'BUTTON' && node.textContent === label,
    );
    if (!button) return false;
    const results = (button.listeners.click || []).map((fn) => fn.call(button, { target: button }));
    await Promise.all(results);
    await probe.settle();
    return true;
  },
  change: async (id) => {
    const el = byId.get(id);
    if (!el) return false;
    await probe.fire(el, 'change');
    return true;
  },
  fire: async (element, type) => {
    const results = ((element && element.listeners[type]) || []).map((fn) =>
      fn.call(element, { target: element }),
    );
    await Promise.all(results);
    await probe.settle();
    return results.length;
  },
  settle: () => new Promise((resolve) => setImmediate(resolve)),
};

const sandbox = {
  document,
  langbot,
  console,
  __probe: probe,
  confirm: () => true,
  alert: (message) => { report.alerts.push(String(message)); },
  // Nothing in these pages depends on a timer firing; only toasts do.
  setTimeout: () => 0,
  clearTimeout: () => {},
};
vm.createContext(sandbox);
vm.runInContext('window = globalThis;', sandbox);

const source = inlineScripts.join('\n');
vm.runInContext(source, sandbox, { filename: pagePath });

(async () => {
  try {
    for (const handler of readyHandlers) await handler();
    await probe.settle();
    if (config.drive) {
      await vm.runInContext(`(async () => {${config.drive}\n})()`, sandbox, { filename: 'drive' });
    }
    for (const handler of languageHandlers) await handler();
  } catch (error) {
    report.errors.push(String((error && error.stack) || error));
  }

  for (const node of created) {
    if (node.nodeType === 3) {
      report.text_nodes.push(node.textContent);
      continue;
    }
    report.elements.push({
      tag: node.tagName,
      id: node.props.id || null,
      className: node.className,
      props: node.props,
      attrs: node.attributes,
      listeners: Object.keys(node.listeners),
      text: node.textContent,
      children: node.children.map((child) => `${child.tagName}${child.props && child.props.id ? '#' + child.props.id : ''}`),
    });
  }
  process.stdout.write(`${JSON.stringify(report)}\n`);
})();

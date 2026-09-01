import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const widgetPath = path.resolve(
  testDirectory,
  '../../../src/langbot/templates/embed/widget.js',
);
const widgetSource = fs.readFileSync(widgetPath, 'utf8');

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.className = '';
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this._innerHTML = '';
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  setAttribute(name, value) {
    this[name] = String(value);
  }

  addEventListener(event, listener) {
    this.listeners[event] = listener;
  }

  click() {
    this.listeners.click?.({});
  }

  attachShadow() {
    this.shadowRoot = new FakeElement('shadow-root');
    return this.shadowRoot;
  }

  get classList() {
    return {
      add: (...names) => {
        const classes = `${this.className} ${names.join(' ')}`
          .trim()
          .split(/\s+/);
        this.className = [...new Set(classes)].join(' ');
      },
    };
  }

  set textContent(value) {
    this._innerHTML = String(value ?? '');
  }

  set innerHTML(value) {
    this._innerHTML = String(value ?? '');
  }

  get innerHTML() {
    return this._innerHTML;
  }

  querySelectorAll(selector) {
    const matches = [];
    for (const child of this.children) {
      if (
        selector.startsWith('.') &&
        child.className.split(/\s+/).includes(selector.slice(1))
      ) {
        matches.push(child);
      }
      matches.push(...child.querySelectorAll(selector));
    }
    return matches;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

class FakeDocument {
  constructor() {
    this.body = new FakeElement('body');
    this.head = new FakeElement('head');
    this.readyState = 'complete';
    this.currentScript = { getAttribute: () => null };
  }

  createElement(tagName) {
    return new FakeElement(tagName);
  }

  getElementById(id) {
    const find = (element) => {
      if (element.id === id) return element;
      for (const child of element.children) {
        const match = find(child);
        if (match) return match;
      }
      return null;
    };
    return find(this.body) ?? find(this.head);
  }
}

class FakeWebSocket {
  static OPEN = 1;
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = FakeWebSocket.OPEN;
    FakeWebSocket.instances.push(this);
  }

  send() {}
}

function launchWidget() {
  FakeWebSocket.instances = [];
  const document = new FakeDocument();
  const window = {
    crypto: { randomUUID: () => '00000000-0000-4000-8000-000000000000' },
    sessionStorage: { getItem: () => null, setItem: () => {} },
  };
  const context = vm.createContext({
    document,
    window,
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    WebSocket: FakeWebSocket,
    fetch: () => new Promise(() => {}),
    requestAnimationFrame: () => 0,
    setTimeout: () => 0,
    clearTimeout: () => {},
    setInterval: () => 0,
    clearInterval: () => {},
  });

  vm.runInContext(widgetSource, context, { filename: widgetPath });
  const root = document.getElementById('langbot-widget-root');
  assert.ok(root, 'widget should initialize');
  root.shadowRoot.querySelector('.lb-bubble').click();
  const socket = FakeWebSocket.instances.at(-1);
  assert.ok(socket, 'opening widget should connect its WebSocket');

  return {
    receive(message) {
      socket.onmessage({
        data: JSON.stringify({ type: 'response', data: message }),
      });
    },
    assistantMessages() {
      return root.shadowRoot.querySelectorAll('.lb-msg-assistant');
    },
  };
}

function assistant(id, content) {
  return { id, role: 'assistant', content, is_final: true };
}

test('renders a non-empty reply after an empty assistant frame', () => {
  const widget = launchWidget();

  widget.receive(assistant('thought', ''));
  widget.receive(assistant('answer', 'visible answer'));

  const messages = widget.assistantMessages();
  assert.equal(messages.length, 2);
  assert.equal(
    messages[1].querySelector('.lb-msg-bubble').innerHTML,
    'visible answer',
  );
});

test('still drops a duplicate non-empty assistant frame', () => {
  const widget = launchWidget();

  widget.receive(assistant('answer-1', 'same answer'));
  widget.receive(assistant('answer-2', 'same answer'));

  assert.equal(widget.assistantMessages().length, 1);
});

test('still keeps two distinct non-empty assistant frames', () => {
  const widget = launchWidget();

  widget.receive(assistant('answer-1', 'first answer'));
  widget.receive(assistant('answer-2', 'second answer'));

  assert.equal(widget.assistantMessages().length, 2);
});

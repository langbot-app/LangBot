import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const widgetPath = path.resolve(
  currentDirectory,
  '../../../src/langbot/templates/embed/widget.js',
);
const widgetSource = fs.readFileSync(widgetPath, 'utf8');

class Element {
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

  addEventListener(type, handler) {
    this.listeners[type] = handler;
  }

  click() {
    this.listeners.click?.({});
  }

  attachShadow() {
    return (this.shadowRoot = new Element('shadow-root'));
  }

  get classList() {
    return {
      add: (...names) => {
        this.className = [
          ...new Set(
            `${this.className} ${names.join(' ')}`.trim().split(/\s+/),
          ),
        ].join(' ');
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
    const result = [];
    for (const child of this.children) {
      if (
        selector.startsWith('.') &&
        child.className.split(/\s+/).includes(selector.slice(1))
      ) {
        result.push(child);
      }
      result.push(...child.querySelectorAll(selector));
    }
    return result;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

class Document {
  constructor() {
    this.body = new Element('body');
    this.head = new Element('head');
    this.readyState = 'complete';
    this.currentScript = { getAttribute: () => null };
  }

  createElement(tagName) {
    return new Element(tagName);
  }

  getElementById(id) {
    const find = (element) => {
      if (element.id === id) return element;
      for (const child of element.children) {
        const found = find(child);
        if (found) return found;
      }
      return null;
    };
    return find(this.body) ?? find(this.head);
  }
}

class FakeWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = FakeWebSocket.OPEN;
    FakeWebSocket.instances.push(this);
  }

  send() {}
}

function startWidget() {
  FakeWebSocket.instances = [];
  const document = new Document();
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
  assert.ok(root, 'the widget should initialize');
  root.shadowRoot.querySelector('.lb-bubble').click();
  const socket = FakeWebSocket.instances.at(-1);
  assert.ok(socket, 'opening the widget should create its WebSocket');

  return {
    assistantMessages: () =>
      root.shadowRoot.querySelectorAll('.lb-msg-assistant'),
    receive(message) {
      socket.onmessage({
        data: JSON.stringify({ type: 'response', data: message }),
      });
    },
  };
}

function assistant(id, content) {
  return { id, role: 'assistant', content, is_final: true };
}

test('keeps a real reply after an empty assistant message', () => {
  const widget = startWidget();
  widget.receive(assistant('empty', ''));
  widget.receive(assistant('reply', 'real reply'));

  const messages = widget.assistantMessages();
  assert.equal(messages.length, 2);
  assert.equal(
    messages[1].querySelector('.lb-msg-bubble').innerHTML,
    'real reply',
  );
});

test('continues deduplicating identical assistant content', () => {
  const widget = startWidget();
  widget.receive(assistant('first', 'same reply'));
  widget.receive(assistant('second', 'same reply'));

  assert.equal(widget.assistantMessages().length, 1);
});

test('continues deduplicating contained assistant content', () => {
  const widget = startWidget();
  widget.receive(assistant('first', 'complete response'));
  widget.receive(assistant('second', 'response'));

  assert.equal(widget.assistantMessages().length, 1);
});

test('keeps different assistant content', () => {
  const widget = startWidget();
  widget.receive(assistant('first', 'first response'));
  widget.receive(assistant('second', 'different response'));

  assert.equal(widget.assistantMessages().length, 2);
});

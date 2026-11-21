import assert from 'node:assert/strict';
import test from 'node:test';
import { loadTs } from './load-ts.mjs';

const model = loadTs(
  new URL(
    '../../src/app/home/bots/components/bot-menu/wxoa-menu-model.ts',
    import.meta.url,
  ),
);

const menu = {
  buttons: [
    { id: 'site', name: '官网', type: 'view', url: 'https://langbot.app' },
    {
      id: 'more',
      name: '更多',
      type: 'group',
      sub_buttons: [
        { id: 'hours', name: '营业时间', type: 'reply', text: '9:00-18:00' },
        { id: 'ask', name: '问 AI', type: 'ai', text: '介绍产品' },
        { id: 'order', name: '查订单', type: 'event', key: 'ORDER' },
      ],
    },
  ],
};

test('builds the same menu/create body as the backend', () => {
  assert.deepEqual(model.toWechatBody(menu), {
    button: [
      { type: 'view', name: '官网', url: 'https://langbot.app' },
      {
        name: '更多',
        sub_button: [
          { type: 'click', name: '营业时间', key: 'lb:r:hours' },
          { type: 'click', name: '问 AI', key: 'lb:a:ask' },
          { type: 'click', name: '查订单', key: 'ORDER' },
        ],
      },
    ],
  });
  assert.deepEqual(model.validateMenu(menu), {});
});

test('validates names by UTF-8 bytes and per-type fields', () => {
  const errors = model.validateMenu({
    buttons: [
      { id: 'a', name: '一二三四五六', type: 'view', url: 'ftp://x' },
      { id: 'b', name: 'b', type: 'event', key: 'lb:x' },
      { id: 'c', name: 'c', type: 'unsupported' },
    ],
  });
  assert.deepEqual(errors, {
    a: ['nameTooLong', 'urlInvalid'],
    b: ['keyReserved'],
    c: ['unsupported'],
  });
});

test('reply text changes do not make a published menu out of sync', () => {
  const published = {
    button: [
      {
        type: 'view',
        name: '官网',
        url: 'https://langbot.app',
        sub_button: [],
      },
      {
        name: '更多',
        sub_button: [
          {
            type: 'click',
            name: '营业时间',
            key: 'lb:r:hours',
            sub_button: [],
          },
          { type: 'click', name: '问 AI', key: 'lb:a:ask', sub_button: [] },
          { type: 'click', name: '查订单', key: 'ORDER', sub_button: [] },
        ],
      },
    ],
  };
  assert.equal(model.isPublishedInSync(menu, published), true);
  const renamed = structuredClone(menu);
  renamed.buttons[0].name = '主页';
  assert.equal(model.isPublishedInSync(renamed, published), false);
  assert.equal(model.isPublishedInSync(menu, null), false);
});

// Custom menu model for WeChat Official Account bots. Mirrors the backend
// translation in src/langbot/pkg/platform/adapters/officialaccount/menu.py.

export type MenuButtonType =
  'group' | 'view' | 'miniprogram' | 'reply' | 'ai' | 'event' | 'unsupported';

export interface MenuButton {
  id: string;
  name: string;
  type: MenuButtonType;
  url?: string;
  appid?: string;
  pagepath?: string;
  text?: string;
  key?: string;
  original_type?: string;
  sub_buttons?: MenuButton[];
}

export interface CustomMenu {
  buttons: MenuButton[];
}

export const MENU_CONFIG_KEY = 'custom_menu';
export const MENU_PUBLISH_ACTION = 'menu.publish';
export const MAX_TOP_BUTTONS = 3;
export const MAX_SUB_BUTTONS = 5;
export const MAX_TOP_NAME_BYTES = 16;
export const MAX_SUB_NAME_BYTES = 60;
export const MAX_KEY_BYTES = 128;
export const MAX_URL_BYTES = 1024;
export const MAX_TEXT_CHARS = 2000;

/** Action types in the order the editor offers them, most common first. */
export const ACTION_TYPES: MenuButtonType[] = [
  'view',
  'miniprogram',
  'reply',
  'ai',
  'event',
];

export function byteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

export function newButtonId(): string {
  return Math.random().toString(16).slice(2, 10).padEnd(8, '0');
}

export function normalizeMenu(value: unknown): CustomMenu {
  if (!value || typeof value !== 'object') return { buttons: [] };
  const buttons = (value as { buttons?: unknown }).buttons;
  return { buttons: Array.isArray(buttons) ? (buttons as MenuButton[]) : [] };
}

export function createButton(name: string): MenuButton {
  return { id: newButtonId(), name, type: 'reply', text: '' };
}

/**
 * After importing from WeChat, buttons LangBot published earlier come back as
 * plain click events with an `lb:r:<id>` / `lb:a:<id>` key because WeChat does
 * not store their text. Restore them from the saved menu when it still has
 * the matching button.
 */
export function restoreLangBotButtons(
  imported: CustomMenu,
  saved: CustomMenu,
): CustomMenu {
  const known = new Map<string, MenuButton>();
  for (const button of saved.buttons) {
    known.set(button.id, button);
    for (const sub of button.sub_buttons || []) known.set(sub.id, sub);
  }
  const restore = (button: MenuButton): MenuButton => {
    if (button.type === 'group')
      return {
        ...button,
        sub_buttons: (button.sub_buttons || []).map(restore),
      };
    const match = /^lb:([ra]):(.+)$/.exec((button.key || '').trim());
    if (button.type !== 'event' || !match) return button;
    const type: MenuButtonType = match[1] === 'r' ? 'reply' : 'ai';
    const original = known.get(match[2]);
    if (!original || original.type !== type) return button;
    return { id: original.id, name: button.name, type, text: original.text };
  };
  return { buttons: imported.buttons.map(restore) };
}

/** Error codes are i18n keys under wxoaMenu.errors. */
export type ButtonError =
  | 'nameRequired'
  | 'nameTooLong'
  | 'urlInvalid'
  | 'urlTooLong'
  | 'appidRequired'
  | 'pagepathRequired'
  | 'textRequired'
  | 'textTooLong'
  | 'keyRequired'
  | 'keyReserved'
  | 'keyTooLong'
  | 'groupEmpty'
  | 'unsupported';

function isHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test(value.trim());
}

export function validateButton(
  button: MenuButton,
  level: 'top' | 'sub',
): ButtonError[] {
  const errors: ButtonError[] = [];
  const name = (button.name || '').trim();
  if (!name) errors.push('nameRequired');
  else if (
    byteLength(name) >
    (level === 'top' ? MAX_TOP_NAME_BYTES : MAX_SUB_NAME_BYTES)
  )
    errors.push('nameTooLong');

  const url = (button.url || '').trim();
  switch (button.type) {
    case 'group':
      if (!button.sub_buttons?.length) errors.push('groupEmpty');
      break;
    case 'view':
    case 'miniprogram':
      if (button.type === 'miniprogram') {
        if (!(button.appid || '').trim()) errors.push('appidRequired');
        if (!(button.pagepath || '').trim()) errors.push('pagepathRequired');
      }
      if (!isHttpUrl(url)) errors.push('urlInvalid');
      else if (byteLength(url) > MAX_URL_BYTES) errors.push('urlTooLong');
      break;
    case 'reply':
    case 'ai': {
      const text = (button.text || '').trim();
      if (!text) errors.push('textRequired');
      else if (text.length > MAX_TEXT_CHARS) errors.push('textTooLong');
      break;
    }
    case 'event': {
      const key = (button.key || '').trim();
      if (!key) errors.push('keyRequired');
      else if (key.startsWith('lb:')) errors.push('keyReserved');
      else if (byteLength(key) > MAX_KEY_BYTES) errors.push('keyTooLong');
      break;
    }
    default:
      errors.push('unsupported');
  }
  return errors;
}

/** Validation errors keyed by button id; empty when the menu can be published. */
export function validateMenu(menu: CustomMenu): Record<string, ButtonError[]> {
  const result: Record<string, ButtonError[]> = {};
  for (const button of menu.buttons) {
    const errors = validateButton(button, 'top');
    if (errors.length) result[button.id] = errors;
    if (button.type === 'group') {
      for (const sub of button.sub_buttons || []) {
        const subErrors = validateButton(sub, 'sub');
        if (subErrors.length) result[sub.id] = subErrors;
      }
    }
  }
  return result;
}

type WechatButton = Record<string, unknown>;

function actionToWechat(button: MenuButton): WechatButton {
  const name = button.name.trim();
  switch (button.type) {
    case 'view':
      return { type: 'view', name, url: (button.url || '').trim() };
    case 'miniprogram':
      return {
        type: 'miniprogram',
        name,
        url: (button.url || '').trim(),
        appid: (button.appid || '').trim(),
        pagepath: (button.pagepath || '').trim(),
      };
    case 'reply':
      return { type: 'click', name, key: `lb:r:${button.id}` };
    case 'ai':
      return { type: 'click', name, key: `lb:a:${button.id}` };
    default:
      return { type: 'click', name, key: (button.key || '').trim() };
  }
}

export function toWechatBody(menu: CustomMenu): { button: WechatButton[] } {
  return {
    button: menu.buttons.map((button) =>
      button.type === 'group'
        ? {
            name: button.name.trim(),
            sub_button: (button.sub_buttons || []).map(actionToWechat),
          }
        : actionToWechat(button),
    ),
  };
}

function canonicalWechat(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalWechat);
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      // menu/get echoes empty sub_button arrays on leaf buttons.
      .filter(
        ([key, item]) =>
          !(key === 'sub_button' && Array.isArray(item) && !item.length),
      )
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => [key, canonicalWechat(item)]);
    return Object.fromEntries(entries);
  }
  return value;
}

/** Whether the saved menu is exactly what WeChat currently serves. */
export function isPublishedInSync(
  menu: CustomMenu,
  published: unknown,
): boolean {
  if (!published || !menu.buttons.length) return false;
  return (
    JSON.stringify(canonicalWechat(toWechatBody(menu))) ===
    JSON.stringify(canonicalWechat(published))
  );
}

/** Known WeChat errcodes with a user-facing hint under wxoaMenu.wechatErrors. */
export const WECHAT_ERROR_HINTS: Record<number, string> = {
  40001: 'credentials',
  40013: 'credentials',
  40125: 'credentials',
  40164: 'ipWhitelist',
  48001: 'unauthorized',
  40054: 'url',
  40055: 'url',
  40016: 'buttonCount',
  40017: 'buttonCount',
  40018: 'buttonName',
  40019: 'buttonKey',
  85005: 'miniprogram',
  46003: 'noMenu',
};

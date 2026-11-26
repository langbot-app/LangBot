export default {
  tab: 'Custom Menu',
  title: 'Official Account Custom Menu',
  description:
    'Edit the buttons at the bottom of the Official Account chat. After the account is connected to LangBot, WeChat disables menus edited in its web console, so publish them from here.',
  status: {
    published: 'Published',
    outOfSync: 'Changes not synced',
    unpublished: 'Not synced to WeChat',
    unknown: 'Publish status unknown',
  },
  actions: {
    import: 'Import from WeChat',
    importing: 'Importing…',
    save: 'Save',
    saving: 'Saving…',
    more: 'More actions',
    deleteRemote: 'Delete the menu on WeChat',
    refresh: 'Refresh sync status',
    addTop: 'Add menu',
    addSub: 'Add sub-button',
    saveAndSync: 'Save and sync to WeChat',
    addTopFull: 'Add top-level menu',
    deleteTop: 'Delete this menu',
    deleteSub: 'Delete this sub-button',
    moveUp: 'Move up',
    moveDown: 'Move down',
  },
  unsaved: 'Unsaved changes',
  botDisabled:
    'The bot is disabled. Enable it to import, sync or delete the menu on WeChat; you can still edit and save here.',
  validationSummary:
    '{{count}} button(s) still need attention before the menu can be synced to WeChat.',
  structure: {
    title: 'Menu structure',
    hint: 'Click a button to edit it; use the arrows to reorder.',
    needsFix: 'Needs attention',
    subFull: 'Sub-buttons full (max {{max}})',
    topFull: 'Top-level menus full (max {{max}})',
  },
  empty: {
    title: 'No menu yet',
    description:
      'Import the menu you already had on WeChat, or start from scratch. Up to 3 top-level buttons, each with up to 5 sub-buttons.',
  },
  preview: {
    title: 'Preview',
    hint: 'Click a button in the preview to see what users get.',
    welcome: 'Hi, how can I help you?',
    clickedReply: '(Tapping "{{name}}" replies automatically)',
    clickedAi: '(Tapping "{{name}}" sends this message for the user)',
    aiReply: 'The AI answers this message using your chat configuration.',
    opensUrl: 'Opens web page: {{url}}',
    opensMiniprogram: 'Opens mini program: {{appid}}',
    eventSent:
      'Sends event {{key}}, handled by the processor bound in event routing.',
    empty: '(empty)',
  },
  editor: {
    title: 'Button settings',
    noSelection:
      'Select a button in Menu structure or in the preview to edit it.',
    name: 'Button name',
    nameBytes: '{{used}}/{{max}} bytes (a Chinese character is about 3 bytes)',
    type: 'When tapped',
    topLevel: 'Top-level menu',
    subLevel: 'Sub-button',
    defaultTopName: 'Menu {{n}}',
    defaultSubName: 'Item {{n}}',
    subButtons: 'Sub-buttons ({{count}}/{{max}})',
    groupHint:
      'Tapping a top-level menu opens its sub-buttons and triggers nothing itself. Add, reorder and delete sub-buttons in Menu structure.',
  },
  types: {
    group: {
      label: 'Open sub-buttons',
      description: 'Group several buttons under one menu',
    },
    view: { label: 'Open web page', description: 'Go to a URL' },
    miniprogram: {
      label: 'Open mini program',
      description: 'Open a page of a linked mini program',
    },
    reply: {
      label: 'Reply with fixed text',
      description: 'Reply with preset text, without calling the AI',
    },
    ai: {
      label: 'Let the AI reply',
      description: 'Sends a message for the user and the AI answers it',
    },
    event: {
      label: 'Trigger event (advanced)',
      description: 'Handled by an Agent or plugin through event routing',
    },
    unsupported: {
      label: 'Unsupported type',
      description:
        'News, image and other material buttons from the WeChat console; switch to another type',
    },
  },
  fields: {
    url: 'URL',
    urlPlaceholder: 'https://example.com',
    appid: 'Mini program AppID',
    appidPlaceholder: 'wx1234567890abcdef',
    pagepath: 'Mini program page path',
    pagepathPlaceholder: 'pages/index/index',
    fallbackUrl: 'Fallback web page',
    fallbackUrlHint:
      'Older WeChat clients that cannot open mini programs open this URL instead.',
    replyText: 'Reply text',
    replyTextPlaceholder: 'e.g. We are open Monday to Friday, 9:00-18:00',
    replyTextHint:
      'Users get this text right after tapping, without using AI credits.',
    aiText: 'Message sent to the AI',
    aiTextPlaceholder: 'e.g. Tell me about your products',
    aiTextHint:
      'LangBot treats this as a message from the user and lets the current chat pipeline or Agent answer it.',
    eventKey: 'Event key',
    eventKeyPlaceholder: 'ORDER_QUERY',
    eventKeyHint:
      'Tapping emits a platform.specific event (officialaccount.CLICK) whose EventKey is this value. Add a binding in Configuration → Event Routing and filter on EventKey to hand it to an Agent.',
    copyFilter: 'Copy filter',
    filterCopied: 'Filter copied',
  },
  errors: {
    nameRequired: 'Enter a button name',
    nameTooLong: 'Name is too long',
    urlInvalid: 'URL must start with http:// or https://',
    urlTooLong: 'URL must not exceed 1024 bytes',
    appidRequired: 'Enter the mini program AppID',
    pagepathRequired: 'Enter the mini program page path',
    textRequired: 'Enter the text',
    textTooLong: 'Text must not exceed 2000 characters',
    keyRequired: 'Enter an event key',
    keyReserved: 'Event key must not start with lb:',
    keyTooLong: 'Event key must not exceed 128 bytes',
    groupEmpty: 'Add at least one sub-button',
    unsupported: 'Switch to a supported button type',
  },
  importConfirm: {
    title: 'Replace the current menu with the one from WeChat?',
    confirm: 'Import',
    description:
      'Reads the menu currently on the Official Account (including one edited in the web console and disabled by WeChat) and saves it to LangBot, replacing the menu here. It reaches WeChat only after you click Save and sync to WeChat.',
  },
  deleteConfirm: {
    title: 'Delete the menu on WeChat?',
    description:
      'The Official Account chat will no longer show a menu. The menu saved in LangBot is kept and can be published again.',
    confirm: 'Delete',
  },
  toasts: {
    saved: 'Menu saved',
    imported:
      'Imported and saved to LangBot. Review it, then click Save and sync to WeChat.',
    importedEmpty: 'The account has no menu right now',
    importWarnings: '{{count}} button(s) need changes',
    deleted: 'The menu on WeChat was deleted',
    saveFailed: 'Failed to save the menu',
    importFailed: 'Import failed',
    deleteFailed: 'Delete failed',
    savedBotDisabled:
      'Saved. Enable the bot and save again to sync it to WeChat.',
    savedNotSynced: 'Saved to LangBot, but it cannot be synced to WeChat yet',
    synced: 'Saved and synced to WeChat',
    syncFailed: 'Saved to LangBot, but syncing to WeChat failed',
  },
  wechatErrors: {
    credentials:
      'The AppID or AppSecret is wrong. Check the bot configuration.',
    ipWhitelist:
      'The LangBot server outbound IP is not in the account IP whitelist. Copy the addresses under "IP Whitelist" on the Configuration tab and add them to the API IP whitelist in the WeChat developer platform.',
    unauthorized:
      'This account has no permission for the custom menu API. Unverified subscription accounts usually lack it; service accounts and verified subscription accounts have it.',
    url: 'A URL is invalid. Check the URLs in your buttons.',
    buttonCount: 'The number of buttons exceeds WeChat limits.',
    buttonName: 'A button name is too long.',
    buttonKey: 'An event key does not meet WeChat limits.',
    miniprogram:
      'The mini program is not linked to this account. Link it in the WeChat console first.',
    noMenu: 'The account has no menu published through the API.',
    generic: 'WeChat returned error {{errcode}}: {{errmsg}}',
  },
};

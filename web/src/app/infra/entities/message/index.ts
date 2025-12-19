// Message component base interface
export interface MessageComponent {
  type: string;
}

// Source component
export interface Source extends MessageComponent {
  type: 'Source';
  id: number | string;
  timestamp: number;
}

// Plain text component
export interface Plain extends MessageComponent {
  type: 'Plain';
  text: string;
}

// Quote component
export interface Quote extends MessageComponent {
  type: 'Quote';
  id?: number;
  group_id?: number | string;
  sender_id?: number | string;
  target_id?: number | string;
  origin: MessageComponent[];
}

// At component
export interface At extends MessageComponent {
  type: 'At';
  target: number | string;
  display?: string;
}

// AtAll component
export interface AtAll extends MessageComponent {
  type: 'AtAll';
}

// Image component
export interface Image extends MessageComponent {
  type: 'Image';
  image_id?: string;
  url?: string;
  path?: string;
  base64?: string;
}

// Voice component
export interface Voice extends MessageComponent {
  type: 'Voice';
  voice_id?: string;
  url?: string;
  path?: string;
  base64?: string;
  length?: number;
}

// File component
export interface File extends MessageComponent {
  type: 'File';
  id?: string;
  name?: string;
  size?: number;
  url?: string;
}

// Unknown component
export interface Unknown extends MessageComponent {
  type: 'Unknown';
  text?: string;
}

// Forward message node
export interface ForwardMessageNode {
  sender_id?: number | string;
  sender_name?: string;
  message_chain?: MessageComponent[];
  message_id?: number;
}

// Forward message display
export interface ForwardMessageDisplay {
  title?: string;
  brief?: string;
  source?: string;
  preview?: string[];
  summary?: string;
}

// Forward component
export interface Forward extends MessageComponent {
  type: 'Forward';
  display?: ForwardMessageDisplay;
  node_list?: ForwardMessageNode[];
}

// WeChat specific components
export interface WeChatMiniPrograms extends MessageComponent {
  type: 'WeChatMiniPrograms';
  mini_app_id: string;
  user_name: string;
  display_name?: string;
  page_path?: string;
  title?: string;
  image_url?: string;
}

export interface WeChatEmoji extends MessageComponent {
  type: 'WeChatEmoji';
  emoji_md5: string;
  emoji_size: number;
}

export interface WeChatLink extends MessageComponent {
  type: 'WeChatLink';
  link_title?: string;
  link_desc?: string;
  link_url?: string;
  link_thumb_url?: string;
}

// Union type for all message components
export type MessageChainComponent =
  | Source
  | Plain
  | Quote
  | At
  | AtAll
  | Image
  | Voice
  | File
  | Unknown
  | Forward
  | WeChatMiniPrograms
  | WeChatEmoji
  | WeChatLink;

// Message interface
export interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  message_chain: MessageChainComponent[];
  timestamp: string;
  is_final?: boolean;
}

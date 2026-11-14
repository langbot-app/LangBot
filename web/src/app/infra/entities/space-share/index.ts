import type { I18nObject } from '@/app/infra/entities/common';

// LANG-439: sharing Skills / remote MCP servers / prompts to LangBot Space and
// using the Space prompt library from Pipeline and Agent configuration.

export type PromptKind = 'messaging' | 'agent';

export interface PromptMessage {
  role: string;
  content: string;
}

export interface LibraryPrompt {
  prompt_id: string;
  author: string;
  name: string;
  kind: PromptKind;
  label: I18nObject;
  description: I18nObject;
  language: string;
  tags: string[] | null;
  messages: PromptMessage[];
  variables: { name: string; description?: string }[] | null;
  version: number;
  use_count: number;
  favorite_count: number;
}

export interface SpaceShareContext {
  space_connected: boolean;
  has_creator_profile: boolean;
  creator_slug: string | null;
  space_web_url: string;
}

export interface ShareFinding {
  kind: string;
  severity: 'block' | 'warn';
  where: string;
  excerpt: string;
}

export interface ShareMetadata {
  name: string;
  label: Record<string, string>;
  description: Record<string, string>;
  tags: string[];
  changelog?: string;
}

export interface MCPRequiredInput {
  name: string;
  label: string;
  description: string;
  secret: boolean;
  required: boolean;
}

export interface MCPSharePreview {
  payload: {
    mode: string;
    url: string;
    headers: Record<string, string>;
    required_inputs: MCPRequiredInput[];
    tools: { name: string; description: string }[];
    readme: string;
  };
  redactions: { where: string; placeholder: string }[];
}

export interface ContentSubmissionResult {
  submission: {
    uuid: string;
    item_id: string;
    status: string;
    review_status: string;
    version: number;
  };
  agent_review: boolean;
}

export interface MyContentSubmission {
  uuid: string;
  item_type: 'skill' | 'mcp' | 'prompt';
  item_id: string;
  name: string;
  version: number;
  label: I18nObject;
  status: 'pending' | 'approved' | 'rejected' | 'withdrawn';
  review_status: string;
  reject_reason: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

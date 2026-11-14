export type AlertEmailChannel = 'auto' | 'instance' | 'space' | 'off';
export type AlertRuleName =
  'pipeline_failures' | 'model_failures' | 'bot_offline';

export interface AlertRuleSetting {
  enabled: boolean;
  threshold: number;
  window_minutes: number;
}

export interface AlertSettings {
  enabled: boolean;
  email_channel: AlertEmailChannel;
  rules: Record<AlertRuleName, AlertRuleSetting>;
  webhook_ids: number[];
  extra_recipients: string[];
  muted_account_uuids: string[];
  notify_resolved: boolean;
}

export interface AlertRuleCatalogItem {
  name: AlertRuleName;
  default_threshold: number;
  min_threshold: number;
  max_threshold: number;
  default_window_minutes: number;
  min_window_minutes: number;
  max_window_minutes: number;
  auto_resolve_minutes: number | null;
}

export interface AlertSettingsResponse {
  enabled_instance_wide: boolean;
  settings: AlertSettings;
  rule_catalog: AlertRuleCatalogItem[];
  channels: {
    instance: { configured: boolean; provider: 'smtp' | 'resend' | null };
    space: { supported: boolean; available: boolean; accounts: string[] };
    effective_email_channel: 'instance' | 'space' | null;
  };
  recipients: {
    account_uuid: string;
    email: string;
    role: string;
    space_linked: boolean;
    muted: boolean;
  }[];
  webhooks: { id: number; name: string; enabled: boolean }[];
}

export interface AlertSummary {
  enabled_instance_wide: boolean;
  enabled: boolean;
  firing: number;
}

export interface AlertIncident {
  id: string;
  rule: AlertRuleName;
  subject_id: string;
  subject_name: string;
  state: 'firing' | 'resolved';
  event_count: number;
  error_type: string | null;
  error_summary: string | null;
  opened_at: string;
  last_seen_at: string | null;
  resolved_at: string | null;
}

export interface AlertDelivery {
  id: number;
  kind: 'fired' | 'reminder' | 'resolved' | 'test';
  channel: 'email' | 'space' | 'webhook';
  target: string;
  status: 'sent' | 'failed' | 'rate_limited' | 'skipped';
  error: string | null;
  incident_count: number;
  created_at: string | null;
}

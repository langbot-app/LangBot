/** Public device-login responses only. OAuth credentials stay on the server. */
export interface CodexAuthStatus {
  status: 'connected' | 'disconnected' | 'expired';
  connected: boolean;
  expires_at: number | null;
}

export interface CodexDeviceAuthorization {
  authorization_id: string;
  user_code: string;
  verification_uri: string;
  interval: number;
  expires_at: number;
}

export interface CodexDevicePoll {
  status: 'pending' | 'connected' | 'expired';
  interval?: number;
}

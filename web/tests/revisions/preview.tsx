import React from 'react';
import { createRoot } from 'react-dom/client';
import { createInstance } from 'i18next';
import { I18nextProvider } from 'react-i18next';
import enUS from '../../src/i18n/locales/en-US';
import CloudPlansDialog from '../../src/app/home/components/workspace-settings/CloudPlansDialog';
import '../../src/app/global.css';
const mode = new URLSearchParams(location.search).get('mode') || 'changed';
const current = {
  name: 'pro',
  subscription_started_at: 1790812800,
  revision: 1,
  limits: {
    'bots.max': 2,
    'members.max': 3,
    'chat_history.retention_days': 30,
  },
  entitlement_features: { mcp_stdio: false, 'platform.telegram': false },
  monthly_bonus_credits: 10,
};
const i18n = createInstance();
await i18n.init({
  lng: 'en-US',
  resources: { 'en-US': { translation: enUS } },
});
createRoot(document.getElementById('root')!).render(
  <I18nextProvider i18n={i18n}>
    <CloudPlansDialog
      open
      onOpenChange={() => {}}
      workspace={
        {
          workspace: { uuid: 'fixture', name: 'Review workspace' },
          membership: { role: mode === 'member' ? 'viewer' : 'owner' },
          plan_name: 'pro',
          current_plan: mode === 'unknown' ? null : current,
        } as any
      }
      spaceURL="https://space.example.test"
    />
  </I18nextProvider>,
);

import React from 'react';
import { createRoot } from 'react-dom/client';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { Toaster } from '/src/components/ui/sonner.tsx';
import '/src/app/global.css';
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from '/src/components/ui/dialog.tsx';
import Section from '/src/app/home/components/models-dialog/component/provider-form/CodexAccountSection.tsx';
i18n.use(initReactI18next);
await i18n.init({
  lng: 'en',
  resources: { en: { translation: {} } },
  interpolation: { escapeValue: false },
});
const root = createRoot(document.getElementById('root'));
window.renderCode = (code = 'FIXTURE-1234', attempt = 'attempt-1') =>
  root.render(
    React.createElement(
      Dialog,
      { open: true },
      React.createElement(
        DialogContent,
        {},
        React.createElement(DialogTitle, {}, 'Copy fixture'),
        React.createElement(Section, {
          providerId: 'fixture',
          login: {
            phase: 'pending',
            device: {
              user_code: code,
              authorization_id: attempt,
              verification_uri: 'https://example.invalid',
              expires_at: 9999999999,
            },
          },
        }),
      ),
      React.createElement(Toaster),
    ),
  );
window.renderCode();

import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';

import './app/global.css';
import 'react-photo-view/dist/react-photo-view.css';

import { ThemeProvider } from '@/components/providers/theme-provider';
import I18nProvider from '@/i18n/I18nProvider';
import { Toaster } from '@/components/ui/sonner';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <I18nProvider>
        <RouterProvider router={router} />
        <Toaster />
      </I18nProvider>
    </ThemeProvider>
  </React.StrictMode>,
);

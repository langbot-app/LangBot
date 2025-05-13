'use client';

import { ReactNode } from 'react';
import '@/i18n';

interface I18nProviderProps {
  children: ReactNode;
}

export default function I18nProvider({ children }: I18nProviderProps) {
  return <>{children}</>;
}

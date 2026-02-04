import './global.css';
import 'react-photo-view/dist/react-photo-view.css';
import type { Metadata } from 'next';
import { Toaster } from '@/components/ui/sonner';
import I18nProvider from '@/i18n/I18nProvider';
import { ThemeProvider } from '@/components/providers/theme-provider';

export const metadata: Metadata = {
  title: 'LangBot',
  description:
    'Production-grade platform for building agentic IM bots, integrated with Telegram, Slack, Discord, WeChat, QQ, etc.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh" suppressHydrationWarning>
      <body className={``}>
        <ThemeProvider>
          <I18nProvider>
            {children}
            <Toaster />
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

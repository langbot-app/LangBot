import './global.css';
import type { Metadata } from 'next';
import { Toaster } from '@/components/ui/sonner';

export const metadata: Metadata = {
  title: 'LangBot',
  description: 'LangBot 是大模型原生即时通信机器人平台',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={``}>
        {children}
        <Toaster />
      </body>
    </html>
  );
}

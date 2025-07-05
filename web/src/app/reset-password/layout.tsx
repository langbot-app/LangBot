'use client';

import React from 'react';

export default function ResetPasswordLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="min-h-screen bg-background">
      <main className="min-h-screen">{children}</main>
    </div>
  );
}

'use client';

import React from "react";
import { ConfigProvider, theme } from 'antd';

export default function LoginLayout({
    children
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <ConfigProvider
            theme={{
                token: {
                    colorPrimary: '#6f42c1',
                    borderRadius: 6,
                },
                algorithm: theme.defaultAlgorithm,
            }}
        >
            <div style={{ width: '100%', height: '100%' }}>
                <main style={{ width: '100%', height: '100%' }}>{children}</main>
            </div>
        </ConfigProvider>
    )
}

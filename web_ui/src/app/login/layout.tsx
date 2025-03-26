import React from "react";

export default function LoginLayout({
    children
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <div>
            <main>{children}</main>
        </div>
    )
}

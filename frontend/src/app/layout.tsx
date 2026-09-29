import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth/AuthContext";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI VMS — Edge Video Intelligence",
  description: "AI video surveillance and edge computing management platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}

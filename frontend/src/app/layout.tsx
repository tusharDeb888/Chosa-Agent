import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chōsa Agent | Autonomous Financial Agent",
  description: "Real-time autonomous market intelligence with AI-powered portfolio analysis, anomaly detection, and policy-guarded recommendations.",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

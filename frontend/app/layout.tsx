import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Proxy — Payment Operator",
  description: "A safety-first payment operations dashboard. Payments require explicit approval and provider verification.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LivingContract OS — AI Governance Dashboard",
  description: "Real-time monitoring of AI-governed smart contract parameter updates",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

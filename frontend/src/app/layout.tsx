import type { Metadata } from "next";
import { Roboto } from "next/font/google";

import "./globals.css";

// One typeface, as in Material You. next/font self-hosts it: no request to Google at runtime.
const roboto = Roboto({ subsets: ["latin"], weight: ["400", "500", "700"], variable: "--font-roboto" });

export const metadata: Metadata = {
  title: { default: "Quorix", template: "%s · Quorix" },
  description: "Answers from your own docs, and the questions your docs don't answer yet.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={roboto.variable}>
      <body>{children}</body>
    </html>
  );
}

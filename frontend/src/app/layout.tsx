import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Folio — Find your next favorite",
  description: "A thoughtful, hybrid book discovery experience built around your taste.",
  applicationName: "Folio",
  openGraph: {
    title: "Folio — Find your next favorite",
    description: "Thoughtful book discovery, picked around your taste.",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "Folio — Find your next favorite",
    description: "Thoughtful book discovery, picked around your taste.",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

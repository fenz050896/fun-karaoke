import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import ClientLayout from "./ClientLayout";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Fun Karaoke",
  description: "On-demand karaoke from YouTube with stem separation and synced lyrics",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <nav className="bg-zinc-900 border-b border-zinc-800 px-4 py-3 sticky top-0 z-50">
          <div className="max-w-4xl mx-auto flex justify-between items-center">
            <Link href="/" className="text-xl font-bold text-zinc-100">
              Fun Karaoke
            </Link>
            <div className="flex items-center gap-2">
              <Link
                href="/"
                className="px-4 py-2 rounded-md bg-zinc-800 text-zinc-200 hover:bg-zinc-700 text-sm font-medium"
              >
                Home
              </Link>
              <Link
                href="/processing"
                className="px-4 py-2 rounded-md bg-zinc-800 text-zinc-200 hover:bg-zinc-700 text-sm font-medium"
              >
                Processing
              </Link>
            </div>
          </div>
        </nav>
        <ClientLayout>
          <div className="flex-1">{children}</div>
        </ClientLayout>
      </body>
    </html>
  );
}
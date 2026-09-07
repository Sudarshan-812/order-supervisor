import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Order Supervisor",
  description: "Long-running AI supervisor for a single order",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-neutral-200 dark:border-neutral-800">
          <nav className="mx-auto flex max-w-6xl items-baseline gap-6 px-6 py-4 text-sm">
            <span className="font-semibold">Order Supervisor</span>
            <Link href="/" className="hover:underline">
              Runs
            </Link>
            <Link href="/supervisors" className="hover:underline">
              Supervisors
            </Link>
            <span className="ml-auto text-xs text-neutral-400">
              long-running AI supervisor, one workflow per order
            </span>
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}

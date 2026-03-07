import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/sidebar";

export const metadata: Metadata = {
  title: "ColdBrew — Warehouse Intelligence",
  description: "Video intelligence platform for warehouse monitoring",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#09090B] text-zinc-50 antialiased">
        <Sidebar />
        <main className="ml-56 min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}

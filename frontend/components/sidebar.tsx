"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Upload, LayoutDashboard, Bell, Activity } from "lucide-react";

const NAV_ITEMS = [
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/status", label: "Status", icon: Activity },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-56 bg-[#18181B] border-r border-[#27272A] flex flex-col z-50">
      <div className="px-4 py-5 border-b border-[#27272A]">
        <h1 className="text-[15px] font-semibold text-zinc-50 tracking-tight">
          ColdBrew
        </h1>
        <p className="text-[11px] text-zinc-500 mt-0.5">Warehouse Intelligence</p>
      </div>
      <nav className="flex-1 py-3 px-2">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors duration-100 ${
                isActive
                  ? "bg-[#27272A] text-zinc-50"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-[#27272A]/50"
              }`}
            >
              <item.icon size={16} strokeWidth={1.8} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-4 py-3 border-t border-[#27272A]">
        <p className="text-[11px] text-zinc-600">NomadicML Hackathon</p>
      </div>
    </aside>
  );
}

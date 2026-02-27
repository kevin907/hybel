"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMessagingStore } from "@/stores/messaging";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import Avatar from "@/components/ui/Avatar";
import Icon, { type IconName } from "@/components/ui/Icon";

const navItems: { label: string; href: string; icon: IconName }[] = [
  { label: "Annonser", href: "#", icon: "search" },
  { label: "Meldinger", href: "/meldinger", icon: "message" },
  { label: "Leiekontrakter", href: "#", icon: "document" },
  { label: "Depositumsgaranti", href: "#", icon: "shield" },
  { label: "Depositumskonto", href: "#", icon: "bank" },
  { label: "Min konto", href: "#", icon: "account" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  // Subscribe to unreadCounts directly so the component re-renders on updates
  const totalUnread = useMessagingStore((s) =>
    Object.values(s.unreadCounts || {}).reduce((sum, c) => sum + c, 0)
  );
  const displayName = user
    ? `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.email
    : "";

  return (
    <aside className="flex w-[156px] flex-col bg-sidebar text-white shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 pt-5 pb-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 text-sm font-bold">
          H
        </div>
        <span className="text-lg font-semibold">Hybel</span>
      </div>

      {/* User */}
      <div className="flex items-center gap-2 px-4 py-3">
        {user ? (
          <Avatar
            firstName={user.first_name || ""}
            lastName={user.last_name || ""}
            size="md"
            className="font-bold"
          />
        ) : (
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-500 text-[10px] font-bold">
            ?
          </div>
        )}
        <span className="text-sm font-medium truncate">{displayName}</span>
        <button className="ml-auto text-gray-400 hover:text-gray-300">
          <Icon name="clock" size={14} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="mt-2 flex flex-1 flex-col gap-0.5 px-2">
        {navItems.map((item) => {
          const isActive = item.href !== "#" && pathname.startsWith(item.href);
          return (
            <Link
              key={item.label}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2 py-2 text-[13px] transition-colors",
                isActive
                  ? "bg-sidebar-active text-white"
                  : "text-gray-300 hover:bg-sidebar-hover hover:text-white"
              )}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.label === "Meldinger" && (
                <span className="ml-auto flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-unread-badge" />
                  <span className="text-xs text-gray-300">{totalUnread}</span>
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="px-2 pb-4">
        <button
          onClick={() => logout()}
          className="flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-[13px] text-gray-300 transition-colors hover:bg-sidebar-hover hover:text-white"
        >
          <Icon name="logout" />
          <span>Logg ut</span>
        </button>
      </div>
    </aside>
  );
}

"use client";

import type { ReactNode } from "react";
import Sidebar from "./Sidebar";

interface InboxLayoutProps {
  list: ReactNode;
  children: ReactNode;
}

export default function InboxLayout({ list, children }: InboxLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Conversation list panel */}
      <div className="flex w-[280px] shrink-0 flex-col border-r border-gray-200 bg-white">
        {list}
      </div>

      {/* Detail panel */}
      <div className="flex flex-1 bg-cream">
        {children}
      </div>
    </div>
  );
}

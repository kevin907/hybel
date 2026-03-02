"use client";

import { memo } from "react";
import Link from "next/link";
import type { ConversationListItem } from "@/types/messaging";
import { useMessagingStore } from "@/stores/messaging";
import { cn, formatShortTime, truncate } from "@/lib/utils";
import Avatar from "@/components/ui/Avatar";

interface Props {
  conversation: ConversationListItem;
}

function ConversationItem({ conversation }: Props) {
  const activeId = useMessagingStore((s) => s.activeConversationId);
  const setActive = useMessagingStore((s) => s.setActiveConversation);
  const storeUnread = useMessagingStore(
    (s) => s.unreadCounts?.[conversation.id]
  );
  const isActive = activeId === conversation.id;
  const unreadCount = storeUnread ?? conversation.unread_count;
  const hasUnread = unreadCount > 0;

  return (
    <Link
      href={`/meldinger/${conversation.id}`}
      onClick={() => setActive(conversation.id)}
      className={cn(
        "flex gap-3 px-4 py-3 border-b border-gray-50 transition-colors cursor-pointer",
        isActive
          ? "bg-blue-50"
          : "hover:bg-gray-50"
      )}
    >
      {/* Participant avatars */}
      <div className="relative flex shrink-0">
        {conversation.participants.slice(0, 2).map((p, i) => {
          const nameParts = p.name.split(" ");
          return (
            <Avatar
              key={p.id}
              firstName={nameParts[0] || ""}
              lastName={nameParts[1] || ""}
              size="xl"
              colorIndex={i}
              className={cn(i > 0 && "-ml-3 ring-2 ring-white")}
            />
          );
        })}
        {conversation.participants.length > 2 && (
          <div className="-ml-3 flex h-10 w-10 items-center justify-center rounded-full bg-gray-300 text-xs font-medium text-gray-700 ring-2 ring-white">
            +{conversation.participants.length - 2}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-baseline justify-between gap-2">
          <span
            className={cn(
              "truncate text-sm",
              hasUnread ? "font-semibold text-gray-900" : "text-gray-700"
            )}
          >
            {conversation.subject || "Ingen emne"}
          </span>
          {conversation.last_message && (
            <span className="shrink-0 text-xs text-gray-400">
              {formatShortTime(conversation.last_message.created_at)}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-xs text-gray-500">
            {conversation.last_message
              ? truncate(conversation.last_message.content, 60)
              : "Ingen meldinger ennå"}
          </p>
          {hasUnread && (
            <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-unread-badge px-1.5 text-micro font-bold text-white">
              {unreadCount}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

export default memo(ConversationItem);

"use client";

import { memo, useEffect, useRef, useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import * as api from "@/lib/api";
import { useMessagingStore } from "@/stores/messaging";
import { useAuth } from "@/lib/auth";
import { queryKeys } from "@/lib/queryKeys";
import MessageBubble from "./MessageBubble";
import Spinner from "@/components/ui/Spinner";

interface Props {
  conversationId: string;
  messagesLoading: boolean;
  initialNextCursor: string | null;
}

/**
 * Extracted from ConversationDetail so that only this component re-renders
 * when the messages array changes (via Zustand store subscription).
 * The parent header, participant list, and compose box are unaffected.
 */
function MessageList({ conversationId, messagesLoading, initialNextCursor }: Props) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const messages = useMessagingStore((s) => s.messages);
  const prependMessages = useMessagingStore((s) => s.prependMessages);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(initialNextCursor);
  const [loadingOlder, setLoadingOlder] = useState(false);

  // Keep cursor in sync when parent passes a new one (conversation switch)
  useEffect(() => {
    setNextCursor(initialNextCursor);
  }, [initialNextCursor]);

  // Load older messages via cursor pagination
  const loadOlderMessages = useCallback(async () => {
    if (!nextCursor || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const older = await api.getMessages(conversationId, nextCursor);
      prependMessages(older.results);
      setNextCursor(older.next);
    } finally {
      setLoadingOlder(false);
    }
  }, [nextCursor, loadingOlder, conversationId, prependMessages]);

  // Virtual scrolling for message list
  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => messagesContainerRef.current,
    estimateSize: () => 80,
    overscan: 10,
  });

  // Mark as read
  const markReadMutation = useMutation({
    mutationFn: (lastMessageId: string) =>
      api.markAsRead(conversationId, lastMessageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    },
  });

  const markReadRef = useRef(markReadMutation);
  markReadRef.current = markReadMutation;

  const markReadTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // Track if user is near bottom (for auto-scroll decision)
  const wasAtBottomRef = useRef(true);
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const handleScroll = () => {
      const threshold = 100;
      wasAtBottomRef.current =
        container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
    };
    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  // Auto-scroll to bottom when new messages arrive (only if user was at bottom)
  useEffect(() => {
    if (messages.length > 0 && wasAtBottomRef.current) {
      virtualizer.scrollToIndex(messages.length - 1, { align: "end" });
    }
  }, [messages.length, virtualizer]);

  // IntersectionObserver: mark as read only when bottom sentinel is visible
  useEffect(() => {
    const sentinel = messagesEndRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && messagesRef.current.length > 0) {
          const lastMsg = messagesRef.current[messagesRef.current.length - 1];
          if (lastMsg.conversation === conversationId && !lastMsg._status) {
            if (markReadTimeoutRef.current)
              clearTimeout(markReadTimeoutRef.current);
            markReadTimeoutRef.current = setTimeout(() => {
              markReadRef.current.mutate(lastMsg.id);
            }, 500);
          }
        }
      },
      { threshold: 0.5 }
    );

    observer.observe(sentinel);
    return () => {
      observer.disconnect();
      if (markReadTimeoutRef.current) clearTimeout(markReadTimeoutRef.current);
    };
  }, [conversationId]);

  return (
    <div
      ref={messagesContainerRef}
      role="log"
      aria-live="polite"
      aria-label="Meldinger"
      className="flex-1 overflow-y-auto bg-cream scrollbar-thin"
    >
      {messagesLoading ? (
        <div className="flex items-center justify-center py-8">
          <Spinner />
        </div>
      ) : messages.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-400">
          Ingen meldinger ennå. Start samtalen!
        </p>
      ) : (
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {nextCursor && (
            <div className="flex justify-center py-2">
              <button
                onClick={loadOlderMessages}
                disabled={loadingOlder}
                className="text-xs text-primary hover:text-primary-dark disabled:text-gray-400"
              >
                {loadingOlder ? "Laster..." : "Last eldre meldinger"}
              </button>
            </div>
          )}
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const msg = messages[virtualRow.index];
            return (
              <div
                key={msg.id}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <MessageBubble
                  message={msg}
                  isOwn={msg.sender.id === user?.id}
                />
              </div>
            );
          })}
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
}

export default memo(MessageList);

"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import * as api from "@/lib/api";
import { useMessagingStore } from "@/stores/messaging";
import { useAuth } from "@/lib/auth";
import type { ParticipantRole, ParticipantSide } from "@/types/messaging";
import { getTypeLabelNO, getStatusLabelNO, cn } from "@/lib/utils";
import { queryKeys } from "@/lib/queryKeys";
import MessageBubble from "./MessageBubble";
import ComposeBox from "./ComposeBox";
import ParticipantList from "./ParticipantList";
import TypingIndicator from "./TypingIndicator";
import ConnectionStatus from "./ConnectionStatus";
import Spinner from "@/components/ui/Spinner";

interface Props {
  conversationId: string;
}

export default function ConversationDetail({ conversationId }: Props) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const setMessages = useMessagingStore((s) => s.setMessages);
  const messages = useMessagingStore((s) => s.messages);
  const prependMessages = useMessagingStore((s) => s.prependMessages);
  const setActiveConversation = useMessagingStore((s) => s.setActiveConversation);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Set active conversation and clear stale messages
  useEffect(() => {
    setMessages([]);
    setActiveConversation(conversationId);
    return () => setActiveConversation(null);
  }, [conversationId, setActiveConversation, setMessages]);

  // Fetch conversation detail
  const { data: conversation } = useQuery({
    queryKey: queryKeys.conversation(conversationId),
    queryFn: () => api.getConversation(conversationId),
  });

  // Fetch messages
  const { data: messagesData, isLoading: messagesLoading } = useQuery({
    queryKey: queryKeys.messages(conversationId),
    queryFn: () => api.getMessages(conversationId),
  });

  // Sync messages to store and track pagination cursor
  useEffect(() => {
    if (messagesData?.results) {
      setMessages(messagesData.results);
      setNextCursor(messagesData.next);
    }
  }, [messagesData, setMessages]);

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

  // Determine current user's side from participants
  const userSide = conversation?.participants.find(
    (p) => p.user.id === user?.id
  )?.side;

  // Mark as read
  const markReadMutation = useMutation({
    mutationFn: (lastMessageId: string) =>
      api.markAsRead(conversationId, lastMessageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    },
  });

  // Stable ref to avoid markReadMutation identity changes triggering re-runs
  const markReadRef = useRef(markReadMutation);
  markReadRef.current = markReadMutation;

  // Debounced mark-as-read ref
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
            // Debounce: only mark read after 500ms of stability
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

  // Remove participant handler
  const handleRemoveParticipant = useCallback(
    async (userId: string) => {
      try {
        setMutationError(null);
        await api.removeParticipant(conversationId, userId);
        queryClient.invalidateQueries({
          queryKey: queryKeys.conversation(conversationId),
        });
      } catch {
        setMutationError("Kunne ikke fjerne deltaker. Prøv igjen.");
      }
    },
    [conversationId, queryClient]
  );

  // Add participant handler
  const handleAddParticipant = useCallback(
    async (data: {
      user_id: string;
      role: ParticipantRole;
      side: ParticipantSide;
    }) => {
      try {
        setMutationError(null);
        await api.addParticipant(conversationId, data);
        queryClient.invalidateQueries({
          queryKey: queryKeys.conversation(conversationId),
        });
      } catch {
        setMutationError("Kunne ikke legge til deltaker. Prøv igjen.");
      }
    },
    [conversationId, queryClient]
  );

  if (!conversation) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      {/* Connection status banner */}
      <ConnectionStatus />

      {/* Mutation error banner */}
      {mutationError && (
        <div className="flex items-center gap-2 border-b border-destructive/20 bg-destructive-light px-4 py-2 text-xs text-destructive">
          <span className="flex-1">{mutationError}</span>
          <button
            onClick={() => setMutationError(null)}
            className="font-medium text-destructive/70 hover:text-destructive"
            aria-label="Lukk feilmelding"
          >
            Lukk
          </button>
        </div>
      )}

      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-gray-900">
              {conversation.subject || "Samtale"}
            </h2>
            <span className="rounded-md bg-gray-100 px-2 py-0.5 text-micro font-medium text-gray-500">
              {getTypeLabelNO(conversation.conversation_type)}
            </span>
            <span
              className={cn(
                "rounded-md px-2 py-0.5 text-micro font-medium",
                conversation.status === "open"
                  ? "bg-success-light text-success"
                  : conversation.status === "closed"
                    ? "bg-destructive-light text-destructive"
                    : "bg-gray-100 text-muted"
              )}
            >
              {getStatusLabelNO(conversation.status)}
            </span>
          </div>
          {conversation.active_delegation && (
            <span className="text-xs text-gray-500">
              Delegert til{" "}
              <span className="font-medium">
                {conversation.active_delegation.assigned_to.first_name}{" "}
                {conversation.active_delegation.assigned_to.last_name}
              </span>
            </span>
          )}
        </div>

        {/* Participants */}
        <div className="mt-2">
          <ParticipantList
            participants={conversation.participants}
            isLandlordSide={userSide === "landlord_side"}
            onRemove={handleRemoveParticipant}
            onAdd={handleAddParticipant}
          />
        </div>
      </div>

      {/* Messages — virtualized for performance with large lists */}
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

      {/* Typing indicator */}
      <TypingIndicator conversationId={conversationId} />

      {/* Compose */}
      <ComposeBox conversationId={conversationId} userSide={userSide} />
    </div>
  );
}

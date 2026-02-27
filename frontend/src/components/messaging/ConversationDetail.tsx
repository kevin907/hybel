"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  const { setMessages, messages, prependMessages, setActiveConversation } =
    useMessagingStore();
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
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

  // Sync messages to store and track pagination
  useEffect(() => {
    if (messagesData?.results) {
      setMessages(messagesData.results);
      // Extract page number from next URL if it exists
      if (messagesData.next) {
        const url = new URL(messagesData.next, window.location.origin);
        const page = url.searchParams.get("page");
        setNextPage(page ? parseInt(page, 10) : null);
      } else {
        setNextPage(null);
      }
    }
  }, [messagesData, setMessages]);

  // Load older messages
  const loadOlderMessages = useCallback(async () => {
    if (!nextPage || loadingOlder) return;
    setLoadingOlder(true);
    const container = messagesContainerRef.current;
    const prevScrollHeight = container?.scrollHeight || 0;
    try {
      const older = await api.getMessages(conversationId, nextPage);
      prependMessages(older.results);
      if (older.next) {
        const url = new URL(older.next, window.location.origin);
        const page = url.searchParams.get("page");
        setNextPage(page ? parseInt(page, 10) : null);
      } else {
        setNextPage(null);
      }
      // Preserve scroll position after prepending
      requestAnimationFrame(() => {
        if (container) {
          container.scrollTop = container.scrollHeight - prevScrollHeight;
        }
      });
    } finally {
      setLoadingOlder(false);
    }
  }, [nextPage, loadingOlder, conversationId, prependMessages]);

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

  // Auto-scroll and mark as read
  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.conversation === conversationId) {
        markReadRef.current.mutate(lastMsg.id);
      }
    }
  }, [messages.length, conversationId]);

  // Remove participant handler
  const handleRemoveParticipant = useCallback(
    async (userId: string) => {
      await api.removeParticipant(conversationId, userId);
      queryClient.invalidateQueries({
        queryKey: queryKeys.conversation(conversationId),
      });
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
      await api.addParticipant(conversationId, data);
      queryClient.invalidateQueries({
        queryKey: queryKeys.conversation(conversationId),
      });
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

      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-gray-900">
              {conversation.subject || "Samtale"}
            </h2>
            <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
              {getTypeLabelNO(conversation.conversation_type)}
            </span>
            <span
              className={cn(
                "rounded-md px-2 py-0.5 text-[10px] font-medium",
                conversation.status === "open"
                  ? "bg-green-50 text-green-700"
                  : conversation.status === "closed"
                    ? "bg-red-50 text-red-700"
                    : "bg-gray-100 text-gray-500"
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

      {/* Messages */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto bg-cream scrollbar-thin py-4"
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
          <>
            {nextPage && (
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
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                isOwn={msg.sender.id === user?.id}
              />
            ))}
          </>
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

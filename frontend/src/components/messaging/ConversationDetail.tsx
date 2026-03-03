"use client";

import { useEffect, useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import { useMessagingStore } from "@/stores/messaging";
import { useAuth } from "@/lib/auth";
import type { ParticipantRole, ParticipantSide } from "@/types/messaging";
import { getTypeLabelNO, getStatusLabelNO, cn } from "@/lib/utils";
import { queryKeys } from "@/lib/queryKeys";
import MessageList from "./MessageList";
import ComposeBox from "./ComposeBox";
import ParticipantList from "./ParticipantList";
import TypingIndicator from "./TypingIndicator";
import ConnectionStatus from "./ConnectionStatus";
import Spinner from "@/components/ui/Spinner";

interface Props {
  conversationId: string;
}

export default function ConversationDetail({ conversationId }: Props) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const setMessages = useMessagingStore((s) => s.setMessages);
  const setActiveConversation = useMessagingStore((s) => s.setActiveConversation);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

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

  // Determine current user's side from participants
  const userSide = conversation?.participants.find(
    (p) => p.user.id === user?.id
  )?.side;

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

      {/* Messages — extracted to isolate re-renders from store updates */}
      <MessageList
        conversationId={conversationId}
        messagesLoading={messagesLoading}
        initialNextCursor={nextCursor}
      />

      {/* Typing indicator */}
      <TypingIndicator conversationId={conversationId} />

      {/* Compose */}
      <ComposeBox conversationId={conversationId} userSide={userSide} />
    </div>
  );
}

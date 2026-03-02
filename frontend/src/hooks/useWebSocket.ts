import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getWebSocketManager } from "@/lib/websocket";
import type {
  ConversationListItem,
  PaginatedResponse,
  WSEvent,
  WSMessageNew,
} from "@/types/messaging";
import { queryKeys } from "@/lib/queryKeys";

/**
 * Optimistically bump a conversation to the top of the React Query cache
 * when a new message arrives via WebSocket.
 */
function bumpConversationInCache(
  queryClient: ReturnType<typeof useQueryClient>,
  event: WSMessageNew
): void {
  queryClient.setQueryData<PaginatedResponse<ConversationListItem>>(
    queryKeys.conversations,
    (old) => {
      if (!old) return old;
      const idx = old.results.findIndex(
        (c) => c.id === event.conversation_id
      );
      if (idx === -1) return old;

      const conv = old.results[idx];
      const updated: ConversationListItem = {
        ...conv,
        last_message: {
          id: event.message_id,
          content: event.content,
          sender: {
            id: event.sender_id,
            email: event.sender_email,
            first_name: event.sender_first_name,
            last_name: event.sender_last_name,
          },
          created_at: new Date().toISOString(),
          is_internal: event.is_internal,
        },
        updated_at: new Date().toISOString(),
      };
      const rest = old.results.filter((c) => c.id !== event.conversation_id);
      return { ...old, results: [updated, ...rest] };
    }
  );
}

export function useWebSocket(enabled = true) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled) return;

    const ws = getWebSocketManager();

    ws.setOnEvent((event: WSEvent) => {
      switch (event.type) {
        case "message.new":
          // Optimistically bump the conversation to the top of the list
          bumpConversationInCache(queryClient, event);
          // Also invalidate to get fresh data from server eventually
          queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
          if (event.conversation_id) {
            queryClient.invalidateQueries({
              queryKey: queryKeys.messages(event.conversation_id),
            });
          }
          break;

        case "participant.added":
        case "participant.removed":
        case "delegation.assigned":
        case "delegation.removed":
          queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
          if (event.conversation_id) {
            queryClient.invalidateQueries({
              queryKey: queryKeys.conversation(event.conversation_id),
            });
          }
          break;

        case "read.updated":
          queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
          break;
      }
    });

    ws.connect();

    return () => {
      ws.setOnEvent(null);
      // Don't disconnect — let the singleton persist across route changes.
      // Disconnect happens on logout (see auth.tsx).
    };
  }, [queryClient, enabled]);

  return getWebSocketManager();
}

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getWebSocketManager } from "@/lib/websocket";
import type { WSEvent } from "@/types/messaging";
import { queryKeys } from "@/lib/queryKeys";

export function useWebSocket(enabled = true) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled) return;

    const ws = getWebSocketManager();

    ws.setOnEvent((event: WSEvent) => {
      switch (event.type) {
        case "message.new":
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
      ws.disconnect();
    };
  }, [queryClient, enabled]);

  return getWebSocketManager();
}

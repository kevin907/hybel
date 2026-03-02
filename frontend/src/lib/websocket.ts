import { useMessagingStore } from "@/stores/messaging";
import type { WSEvent } from "@/types/messaging";
import * as api from "./api";

const MAX_RECONNECT_DELAY = 30_000;

export type WSCallback = (event: WSEvent) => void;

class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private url: string;
  private onEventCallback: WSCallback | null = null;

  constructor(url: string) {
    this.url = url;
  }

  /** Register a callback for events that need external handling (e.g. React Query invalidation). */
  setOnEvent(cb: WSCallback | null): void {
    this.onEventCallback = cb;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = () => this.onOpen();
      this.ws.onmessage = (e) => this.onMessage(e);
      this.ws.onclose = (e) => this.onClose(e);
      this.ws.onerror = () => {}; // onclose will handle it
    } catch {
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    useMessagingStore.getState().setConnectionStatus("disconnected");
  }

  send(data: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  sendTypingStart(conversationId: string): void {
    this.send({ type: "typing.start", conversation_id: conversationId });
  }

  sendTypingStop(conversationId: string): void {
    this.send({ type: "typing.stop", conversation_id: conversationId });
  }

  private onOpen(): void {
    const wasReconnect = this.reconnectAttempts > 0;
    this.reconnectAttempts = 0;
    useMessagingStore.getState().setConnectionStatus("connected");
    this.flushOfflineQueue();

    // Gap-fill: fetch any messages missed during disconnection
    if (wasReconnect) {
      this.gapFill();
    }
  }

  private async gapFill(): Promise<void> {
    const store = useMessagingStore.getState();
    const convId = store.activeConversationId;
    if (!convId || store.messages.length === 0) return;

    const lastMsg = store.messages[store.messages.length - 1];
    // Don't gap-fill against optimistic (unsent) messages
    if (lastMsg._status) return;

    try {
      const missed = await api.getMessagesSince(convId, lastMsg.id);
      for (const msg of missed) {
        store.addMessage(msg);
      }
    } catch {
      // Silently fail — eventual consistency via React Query refetch
    }
  }

  private onMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data) as WSEvent;
      this.handleEvent(data);
    } catch {
      // Ignore malformed messages
    }
  }

  private onClose(_event: CloseEvent): void {
    this.ws = null;
    useMessagingStore.getState().setConnectionStatus("reconnecting");
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    const delay = this.getReconnectDelay();
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private getReconnectDelay(): number {
    const delay = Math.min(
      1000 * Math.pow(2, this.reconnectAttempts),
      MAX_RECONNECT_DELAY
    );
    // Add jitter
    return delay + Math.random() * 1000;
  }

  private handleEvent(event: WSEvent): void {
    const store = useMessagingStore.getState();

    switch (event.type) {
      case "connection.sync":
        store.setUnreadCounts(event.unread_counts);
        break;

      case "message.new":
        // Only add to message list if it's for the active conversation
        if (store.activeConversationId === event.conversation_id) {
          store.addMessage({
            id: event.message_id,
            conversation: event.conversation_id,
            sender: {
              id: event.sender_id,
              email: event.sender_email,
              first_name: event.sender_first_name,
              last_name: event.sender_last_name,
            },
            content: event.content,
            message_type: event.message_type,
            is_internal: event.is_internal,
            attachments: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          });
        } else {
          // Bump unread for non-active conversations
          const current =
            store.unreadCounts[event.conversation_id] || 0;
          store.updateUnreadCount(event.conversation_id, current + 1);
        }
        // Notify callback to update React Query cache (single source of truth)
        this.onEventCallback?.(event);
        break;

      case "read.updated":
        store.updateUnreadCount(
          event.conversation_id,
          event.unread_count
        );
        this.onEventCallback?.(event);
        break;

      case "typing.started":
        store.setTyping(event.conversation_id, event.user_id, event.user_name, true);
        // Auto-clear after 3 seconds
        setTimeout(() => {
          store.setTyping(event.conversation_id, event.user_id, event.user_name, false);
        }, 3000);
        break;

      case "typing.stopped":
        store.setTyping(event.conversation_id, event.user_id, event.user_name, false);
        break;

      case "participant.added":
      case "participant.removed":
      case "delegation.assigned":
      case "delegation.removed":
        // Notify callback to refresh conversation detail and list
        this.onEventCallback?.(event);
        break;
    }
  }

  private async flushOfflineQueue(): Promise<void> {
    const store = useMessagingStore.getState();
    const queue = [...store.offlineQueue];
    if (queue.length === 0) return;

    store.clearOfflineQueue();

    for (const msg of queue) {
      try {
        await api.sendMessage(msg.conversationId, {
          content: msg.content,
          is_internal: msg.is_internal,
        });
      } catch {
        // Re-add failed messages
        store.addToOfflineQueue(msg);
      }
    }
  }
}

let instance: WebSocketManager | null = null;

export function getWebSocketManager(): WebSocketManager {
  if (!instance) {
    const wsBase = process.env.NEXT_PUBLIC_WS_URL;
    let url: string;
    if (wsBase) {
      // Dev: connect directly to backend WS
      url = `${wsBase}/inbox/`;
    } else {
      // Production: connect via same host (nginx proxies WS)
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      url = `${protocol}//${window.location.host}/ws/inbox/`;
    }
    instance = new WebSocketManager(url);
  }
  return instance;
}

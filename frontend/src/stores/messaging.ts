import { create } from "zustand";
import type {
  Message,
  SendMessageRequest,
} from "@/types/messaging";

interface OfflineMessage extends SendMessageRequest {
  conversationId: string;
}

interface MessagingState {
  // Active conversation
  activeConversationId: string | null;
  setActiveConversation: (id: string | null) => void;

  // Messages for active conversation
  messages: Message[];
  setMessages: (msgs: Message[]) => void;
  addMessage: (msg: Message) => void;
  prependMessages: (msgs: Message[]) => void;
  replaceMessage: (tempId: string, msg: Message) => void;
  markMessageFailed: (tempId: string) => void;

  // Unread counts
  unreadCounts: Record<string, number>;
  setUnreadCounts: (counts: Record<string, number>) => void;
  updateUnreadCount: (conversationId: string, count: number) => void;
  getTotalUnread: () => number;

  // Typing indicators
  typingUsers: Record<string, { userId: string; userName: string }[]>;
  setTyping: (
    conversationId: string,
    userId: string,
    userName: string,
    isTyping: boolean
  ) => void;

  // Connection status
  connectionStatus: "connected" | "reconnecting" | "disconnected";
  setConnectionStatus: (
    status: "connected" | "reconnecting" | "disconnected"
  ) => void;

  // Offline queue
  offlineQueue: OfflineMessage[];
  addToOfflineQueue: (msg: OfflineMessage) => void;
  clearOfflineQueue: () => void;

  // Search mode
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  isSearchActive: boolean;
}

export const useMessagingStore = create<MessagingState>((set, get) => ({
  // Active conversation
  activeConversationId: null,
  setActiveConversation: (id) => set({ activeConversationId: id }),

  // Messages
  messages: [],
  setMessages: (msgs) => set({ messages: msgs }),
  addMessage: (msg) =>
    set((state) => {
      // Deduplicate
      if (state.messages.some((m) => m.id === msg.id)) return state;
      return { messages: [...state.messages, msg] };
    }),
  prependMessages: (msgs) =>
    set((state) => {
      const existingIds = new Set(state.messages.map((m) => m.id));
      const newMsgs = msgs.filter((m) => !existingIds.has(m.id));
      return { messages: [...newMsgs, ...state.messages] };
    }),
  replaceMessage: (tempId, msg) =>
    set((state) => ({
      messages: state.messages
        .filter((m) => m.id !== msg.id) // Remove any WS-delivered duplicate first
        .map((m) => (m.id === tempId ? msg : m)),
    })),
  markMessageFailed: (tempId) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === tempId ? { ...m, _status: "failed" as const } : m
      ),
    })),

  // Unread counts
  unreadCounts: {},
  setUnreadCounts: (counts) => set({ unreadCounts: counts }),
  updateUnreadCount: (conversationId, count) =>
    set((state) => ({
      unreadCounts: { ...state.unreadCounts, [conversationId]: count },
    })),
  getTotalUnread: () => {
    const counts = get().unreadCounts;
    return Object.values(counts).reduce((sum, c) => sum + c, 0);
  },

  // Typing
  typingUsers: {},
  setTyping: (conversationId, userId, userName, isTyping) =>
    set((state) => {
      const current = state.typingUsers[conversationId] || [];
      const updated = isTyping
        ? current.some((u) => u.userId === userId)
          ? current
          : [...current, { userId, userName }]
        : current.filter((u) => u.userId !== userId);
      return {
        typingUsers: { ...state.typingUsers, [conversationId]: updated },
      };
    }),

  // Connection
  connectionStatus: "disconnected",
  setConnectionStatus: (status) => set({ connectionStatus: status }),

  // Offline queue
  offlineQueue: [],
  addToOfflineQueue: (msg) =>
    set((state) => ({ offlineQueue: [...state.offlineQueue, msg] })),
  clearOfflineQueue: () => set({ offlineQueue: [] }),

  // Search
  searchQuery: "",
  setSearchQuery: (query) =>
    set({ searchQuery: query, isSearchActive: query.length > 0 }),
  isSearchActive: false,
}));

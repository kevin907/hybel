import { create } from "zustand";
import type {
  ConversationListItem,
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

  // Conversations cache
  conversations: ConversationListItem[];
  setConversations: (items: ConversationListItem[]) => void;
  updateConversation: (
    id: string,
    updates: Partial<ConversationListItem>
  ) => void;

  // Messages for active conversation
  messages: Message[];
  setMessages: (msgs: Message[]) => void;
  addMessage: (msg: Message) => void;
  prependMessages: (msgs: Message[]) => void;

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

  // Bump conversation to top (optimistic sidebar update)
  bumpConversation: (
    conversationId: string,
    lastMessage: { id: string; content: string; sender_id: string; is_internal: boolean }
  ) => void;

  // Search mode
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  isSearchActive: boolean;
}

export const useMessagingStore = create<MessagingState>((set, get) => ({
  // Active conversation
  activeConversationId: null,
  setActiveConversation: (id) => set({ activeConversationId: id }),

  // Conversations
  conversations: [],
  setConversations: (items) => set({ conversations: items }),
  updateConversation: (id, updates) =>
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, ...updates } : c
      ),
    })),

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

  // Bump conversation to top
  bumpConversation: (conversationId, lastMessage) =>
    set((state) => {
      const idx = state.conversations.findIndex((c) => c.id === conversationId);
      if (idx === -1) return state;
      const conv = state.conversations[idx];
      const updated: ConversationListItem = {
        ...conv,
        last_message: {
          id: lastMessage.id,
          content: lastMessage.content,
          sender: { id: lastMessage.sender_id, email: "", first_name: "", last_name: "" },
          created_at: new Date().toISOString(),
          is_internal: lastMessage.is_internal,
        },
        updated_at: new Date().toISOString(),
      };
      const rest = state.conversations.filter((c) => c.id !== conversationId);
      return { conversations: [updated, ...rest] };
    }),

  // Search
  searchQuery: "",
  setSearchQuery: (query) =>
    set({ searchQuery: query, isSearchActive: query.length > 0 }),
  isSearchActive: false,
}));

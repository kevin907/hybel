import { useMessagingStore } from "@/stores/messaging";

describe("MessagingStore", () => {
  beforeEach(() => {
    useMessagingStore.setState({
      activeConversationId: null,
      conversations: [],
      messages: [],
      unreadCounts: {},
      typingUsers: {},
      connectionStatus: "disconnected",
      offlineQueue: [],
      searchQuery: "",
      isSearchActive: false,
    });
  });

  it("sets active conversation", () => {
    const store = useMessagingStore.getState();
    store.setActiveConversation("conv-1");
    expect(useMessagingStore.getState().activeConversationId).toBe("conv-1");
  });

  it("adds message without duplicates", () => {
    const store = useMessagingStore.getState();
    const msg = {
      id: "msg-1",
      conversation: "conv-1",
      sender: { id: "u1", email: "", first_name: "Ola", last_name: "N" },
      content: "Hei",
      message_type: "message" as const,
      is_internal: false,
      attachments: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    store.addMessage(msg);
    store.addMessage(msg); // duplicate
    expect(useMessagingStore.getState().messages).toHaveLength(1);
  });

  it("updates unread counts", () => {
    const store = useMessagingStore.getState();
    store.updateUnreadCount("conv-1", 5);
    store.updateUnreadCount("conv-2", 3);
    expect(store.getTotalUnread()).toBe(8);
  });

  it("sets and clears typing users", () => {
    const store = useMessagingStore.getState();
    store.setTyping("conv-1", "user-1", "Ola Nordmann", true);
    expect(useMessagingStore.getState().typingUsers["conv-1"]).toEqual([
      { userId: "user-1", userName: "Ola Nordmann" },
    ]);

    store.setTyping("conv-1", "user-1", "Ola Nordmann", false);
    expect(useMessagingStore.getState().typingUsers["conv-1"]).toEqual([]);
  });

  it("manages offline queue", () => {
    const store = useMessagingStore.getState();
    store.addToOfflineQueue({
      conversationId: "conv-1",
      content: "Offline melding",
    });
    expect(useMessagingStore.getState().offlineQueue).toHaveLength(1);

    store.clearOfflineQueue();
    expect(useMessagingStore.getState().offlineQueue).toHaveLength(0);
  });

  it("sets connection status", () => {
    const store = useMessagingStore.getState();
    store.setConnectionStatus("connected");
    expect(useMessagingStore.getState().connectionStatus).toBe("connected");

    store.setConnectionStatus("reconnecting");
    expect(useMessagingStore.getState().connectionStatus).toBe("reconnecting");
  });

  it("manages search state", () => {
    const store = useMessagingStore.getState();
    store.setSearchQuery("test");
    expect(useMessagingStore.getState().searchQuery).toBe("test");
    expect(useMessagingStore.getState().isSearchActive).toBe(true);

    store.setSearchQuery("");
    expect(useMessagingStore.getState().isSearchActive).toBe(false);
  });

  it("setConversations replaces the list", () => {
    const store = useMessagingStore.getState();
    const convA = {
      id: "conv-a",
      subject: "A",
      conversation_type: "general" as const,
      status: "open" as const,
      property: null,
      unread_count: 0,
      last_message: null,
      participants: [],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };
    const convB = { ...convA, id: "conv-b", subject: "B" };

    store.setConversations([convA, convB]);
    expect(useMessagingStore.getState().conversations).toHaveLength(2);

    store.setConversations([convA]);
    expect(useMessagingStore.getState().conversations).toHaveLength(1);
    expect(useMessagingStore.getState().conversations[0].id).toBe("conv-a");
  });

  it("updateConversation patches a conversation", () => {
    const store = useMessagingStore.getState();
    const conv = {
      id: "conv-1",
      subject: "Original",
      conversation_type: "general" as const,
      status: "open" as const,
      property: null,
      unread_count: 0,
      last_message: null,
      participants: [],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };

    store.setConversations([conv]);
    store.updateConversation("conv-1", { subject: "Updated" });

    expect(useMessagingStore.getState().conversations[0].subject).toBe("Updated");
  });

  it("bumpConversation moves conversation to top with updated last_message", () => {
    const store = useMessagingStore.getState();
    const conv1 = {
      id: "conv-1",
      subject: "First",
      conversation_type: "general" as const,
      status: "open" as const,
      property: null,
      unread_count: 0,
      last_message: null,
      participants: [],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };
    const conv2 = { ...conv1, id: "conv-2", subject: "Second" };

    store.setConversations([conv1, conv2]);
    store.bumpConversation("conv-2", {
      id: "msg-new",
      content: "Ny melding",
      sender_id: "u-1",
      is_internal: false,
    });

    const convs = useMessagingStore.getState().conversations;
    expect(convs[0].id).toBe("conv-2");
    expect(convs[0].last_message?.content).toBe("Ny melding");
    expect(convs[1].id).toBe("conv-1");
  });

  it("bumpConversation is a no-op for unknown id", () => {
    const store = useMessagingStore.getState();
    const conv = {
      id: "conv-1",
      subject: "Only",
      conversation_type: "general" as const,
      status: "open" as const,
      property: null,
      unread_count: 0,
      last_message: null,
      participants: [],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };

    store.setConversations([conv]);
    store.bumpConversation("nonexistent", {
      id: "msg-1",
      content: "test",
      sender_id: "u-1",
      is_internal: false,
    });

    const convs = useMessagingStore.getState().conversations;
    expect(convs).toHaveLength(1);
    expect(convs[0].id).toBe("conv-1");
    expect(convs[0].last_message).toBeNull();
  });

  it("prepends messages without duplicates", () => {
    const store = useMessagingStore.getState();
    const msg1 = {
      id: "msg-1",
      conversation: "conv-1",
      sender: { id: "u1", email: "", first_name: "A", last_name: "B" },
      content: "First",
      message_type: "message" as const,
      is_internal: false,
      attachments: [],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };
    const msg2 = { ...msg1, id: "msg-2", content: "Second" };
    const msg3 = { ...msg1, id: "msg-3", content: "Third" };

    store.addMessage(msg2);
    store.prependMessages([msg1, msg2]); // msg2 should be deduplicated

    const messages = useMessagingStore.getState().messages;
    expect(messages).toHaveLength(2);
    expect(messages[0].id).toBe("msg-1");
    expect(messages[1].id).toBe("msg-2");
  });
});

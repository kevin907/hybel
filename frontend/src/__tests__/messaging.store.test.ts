import { useMessagingStore } from "@/stores/messaging";
import type { Message, ConversationListItem } from "@/types/messaging";

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: "msg-1",
    conversation: "conv-1",
    sender: { id: "u-1", email: "a@b.no", first_name: "A", last_name: "B" },
    content: "Hei",
    message_type: "message",
    is_internal: false,
    attachments: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeConversation(
  overrides: Partial<ConversationListItem> = {}
): ConversationListItem {
  return {
    id: "conv-1",
    subject: "Test",
    conversation_type: "general",
    status: "open",
    property: null,
    unread_count: 0,
    last_message: null,
    participants: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("useMessagingStore", () => {
  beforeEach(() => {
    // Reset store between tests
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

  it("setActiveConversation updates state", () => {
    useMessagingStore.getState().setActiveConversation("conv-1");
    expect(useMessagingStore.getState().activeConversationId).toBe("conv-1");
  });

  it("setConversations replaces list", () => {
    const convs = [makeConversation(), makeConversation({ id: "conv-2" })];
    useMessagingStore.getState().setConversations(convs);
    expect(useMessagingStore.getState().conversations).toHaveLength(2);
  });

  it("addMessage appends to messages", () => {
    const msg = makeMessage();
    useMessagingStore.getState().addMessage(msg);
    expect(useMessagingStore.getState().messages).toHaveLength(1);
    expect(useMessagingStore.getState().messages[0].id).toBe("msg-1");
  });

  it("addMessage deduplicates", () => {
    const msg = makeMessage();
    useMessagingStore.getState().addMessage(msg);
    useMessagingStore.getState().addMessage(msg);
    expect(useMessagingStore.getState().messages).toHaveLength(1);
  });

  it("prependMessages adds to front and deduplicates", () => {
    useMessagingStore.getState().setMessages([makeMessage({ id: "msg-2" })]);
    useMessagingStore
      .getState()
      .prependMessages([makeMessage({ id: "msg-1" }), makeMessage({ id: "msg-2" })]);
    const msgs = useMessagingStore.getState().messages;
    expect(msgs).toHaveLength(2);
    expect(msgs[0].id).toBe("msg-1");
    expect(msgs[1].id).toBe("msg-2");
  });

  it("updateUnreadCount updates count for conversation", () => {
    useMessagingStore.getState().updateUnreadCount("conv-1", 5);
    expect(useMessagingStore.getState().unreadCounts["conv-1"]).toBe(5);
  });

  it("getTotalUnread sums all counts", () => {
    useMessagingStore.getState().updateUnreadCount("conv-1", 3);
    useMessagingStore.getState().updateUnreadCount("conv-2", 2);
    expect(useMessagingStore.getState().getTotalUnread()).toBe(5);
  });

  it("setConnectionStatus transitions between states", () => {
    useMessagingStore.getState().setConnectionStatus("connected");
    expect(useMessagingStore.getState().connectionStatus).toBe("connected");
    useMessagingStore.getState().setConnectionStatus("reconnecting");
    expect(useMessagingStore.getState().connectionStatus).toBe("reconnecting");
  });

  it("setTyping adds and removes typing users", () => {
    useMessagingStore.getState().setTyping("conv-1", "u-1", "Ola Nordmann", true);
    expect(useMessagingStore.getState().typingUsers["conv-1"]).toEqual([
      { userId: "u-1", userName: "Ola Nordmann" },
    ]);

    useMessagingStore.getState().setTyping("conv-1", "u-1", "Ola Nordmann", false);
    expect(useMessagingStore.getState().typingUsers["conv-1"]).toEqual([]);
  });

  it("addToOfflineQueue and clearOfflineQueue manages queue", () => {
    useMessagingStore.getState().addToOfflineQueue({
      conversationId: "conv-1",
      content: "Offline msg",
      is_internal: false,
    });
    expect(useMessagingStore.getState().offlineQueue).toHaveLength(1);

    useMessagingStore.getState().clearOfflineQueue();
    expect(useMessagingStore.getState().offlineQueue).toHaveLength(0);
  });

  it("setSearchQuery activates search mode", () => {
    useMessagingStore.getState().setSearchQuery("heisen");
    expect(useMessagingStore.getState().searchQuery).toBe("heisen");
    expect(useMessagingStore.getState().isSearchActive).toBe(true);
  });

  it("setSearchQuery with empty string deactivates search", () => {
    useMessagingStore.getState().setSearchQuery("heisen");
    useMessagingStore.getState().setSearchQuery("");
    expect(useMessagingStore.getState().isSearchActive).toBe(false);
  });

  it("bumpConversation moves conversation to top", () => {
    useMessagingStore.getState().setConversations([
      makeConversation({ id: "conv-1", subject: "First" }),
      makeConversation({ id: "conv-2", subject: "Second" }),
    ]);
    useMessagingStore.getState().bumpConversation("conv-2", {
      id: "msg-new",
      content: "New msg",
      sender_id: "u-1",
      is_internal: false,
    });
    const convs = useMessagingStore.getState().conversations;
    expect(convs[0].id).toBe("conv-2");
    expect(convs[1].id).toBe("conv-1");
  });

  it("updateConversation merges updates", () => {
    useMessagingStore
      .getState()
      .setConversations([makeConversation({ id: "conv-1", subject: "Old" })]);
    useMessagingStore.getState().updateConversation("conv-1", { subject: "New" });
    expect(useMessagingStore.getState().conversations[0].subject).toBe("New");
  });
});

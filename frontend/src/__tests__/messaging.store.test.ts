import { useMessagingStore } from "@/stores/messaging";
import type { Message } from "@/types/messaging";

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

describe("useMessagingStore", () => {
  beforeEach(() => {
    // Reset store between tests
    useMessagingStore.setState({
      activeConversationId: null,
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

  it("S3.1 — store no longer holds conversations array", () => {
    const state = useMessagingStore.getState();
    expect(state).not.toHaveProperty("conversations");
    expect(state).not.toHaveProperty("setConversations");
    expect(state).not.toHaveProperty("bumpConversation");
    expect(state).not.toHaveProperty("updateConversation");
  });
});

// ── Bug 2: replaceMessage WS race condition ──────────────────────────────────
describe("replaceMessage WS race condition", () => {
  beforeEach(() => {
    useMessagingStore.setState({
      activeConversationId: null,
      messages: [],
      unreadCounts: {},
      typingUsers: {},
      connectionStatus: "disconnected",
      offlineQueue: [],
      searchQuery: "",
      isSearchActive: false,
    });
  });

  const makeMsg = (overrides: Partial<{ id: string; content: string; _status: "pending" | "failed" }>) => ({
    id: overrides.id ?? "msg-1",
    conversation: "conv-1",
    sender: { id: "u1", email: "", first_name: "A", last_name: "B" },
    content: overrides.content ?? "Hello",
    message_type: "message" as const,
    is_internal: false,
    attachments: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...(overrides._status ? { _status: overrides._status } : {}),
  });

  it("handles WS message arriving before HTTP response (no duplicate keys)", () => {
    const store = useMessagingStore.getState();

    // 1. Optimistic add with temp ID
    store.addMessage(makeMsg({ id: "temp-abc", _status: "pending" }));

    // 2. WS delivers the real message before HTTP response
    store.addMessage(makeMsg({ id: "real-123" }));
    expect(useMessagingStore.getState().messages).toHaveLength(2);

    // 3. HTTP response triggers replaceMessage
    store.replaceMessage("temp-abc", makeMsg({ id: "real-123" }));
    const msgs = useMessagingStore.getState().messages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].id).toBe("real-123");
    expect(msgs[0]._status).toBeUndefined();
  });

  it("handles HTTP response arriving before WS (normal case)", () => {
    const store = useMessagingStore.getState();

    // 1. Optimistic add
    store.addMessage(makeMsg({ id: "temp-abc", _status: "pending" }));
    expect(useMessagingStore.getState().messages).toHaveLength(1);

    // 2. HTTP response arrives first
    store.replaceMessage("temp-abc", makeMsg({ id: "real-123" }));
    expect(useMessagingStore.getState().messages).toHaveLength(1);
    expect(useMessagingStore.getState().messages[0].id).toBe("real-123");

    // 3. WS message arrives — addMessage deduplicates
    store.addMessage(makeMsg({ id: "real-123" }));
    expect(useMessagingStore.getState().messages).toHaveLength(1);
  });

  it("replaceMessage preserves other messages in the list", () => {
    const store = useMessagingStore.getState();

    store.addMessage(makeMsg({ id: "existing-1", content: "First" }));
    store.addMessage(makeMsg({ id: "temp-abc", _status: "pending", content: "Optimistic" }));
    store.addMessage(makeMsg({ id: "existing-2", content: "Third" }));
    expect(useMessagingStore.getState().messages).toHaveLength(3);

    store.replaceMessage("temp-abc", makeMsg({ id: "real-123", content: "Server confirmed" }));
    const msgs = useMessagingStore.getState().messages;
    expect(msgs).toHaveLength(3);
    expect(msgs.map((m) => m.id)).toEqual(["existing-1", "real-123", "existing-2"]);
  });

  it("replaceMessage with non-existent tempId is a no-op", () => {
    const store = useMessagingStore.getState();

    store.addMessage(makeMsg({ id: "msg-1" }));
    store.replaceMessage("non-existent", makeMsg({ id: "real-123" }));
    const msgs = useMessagingStore.getState().messages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].id).toBe("msg-1");
  });

  it("multiple rapid sends don't create duplicate keys", () => {
    const store = useMessagingStore.getState();

    // Two optimistic messages sent rapidly
    store.addMessage(makeMsg({ id: "temp-1", _status: "pending", content: "Msg A" }));
    store.addMessage(makeMsg({ id: "temp-2", _status: "pending", content: "Msg B" }));

    // WS delivers both real messages
    store.addMessage(makeMsg({ id: "real-1", content: "Msg A" }));
    store.addMessage(makeMsg({ id: "real-2", content: "Msg B" }));
    expect(useMessagingStore.getState().messages).toHaveLength(4);

    // HTTP responses replace both optimistic messages
    store.replaceMessage("temp-1", makeMsg({ id: "real-1", content: "Msg A" }));
    store.replaceMessage("temp-2", makeMsg({ id: "real-2", content: "Msg B" }));

    const msgs = useMessagingStore.getState().messages;
    expect(msgs).toHaveLength(2);
    const ids = msgs.map((m) => m.id);
    expect(ids).toEqual(["real-1", "real-2"]);
    // No duplicates
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("markMessageFailed sets _status to failed", () => {
    const store = useMessagingStore.getState();

    store.addMessage(makeMsg({ id: "temp-abc", _status: "pending" }));
    store.markMessageFailed("temp-abc");
    const msg = useMessagingStore.getState().messages[0];
    expect(msg._status).toBe("failed");
  });

  it("markMessageFailed does not affect other messages", () => {
    const store = useMessagingStore.getState();

    store.addMessage(makeMsg({ id: "msg-ok", content: "OK" }));
    store.addMessage(makeMsg({ id: "temp-fail", _status: "pending", content: "Will fail" }));
    store.markMessageFailed("temp-fail");

    const msgs = useMessagingStore.getState().messages;
    expect(msgs[0]._status).toBeUndefined();
    expect(msgs[1]._status).toBe("failed");
  });

  it("replaceMessage clears _status from optimistic message", () => {
    const store = useMessagingStore.getState();

    store.addMessage(makeMsg({ id: "temp-abc", _status: "pending" }));
    expect(useMessagingStore.getState().messages[0]._status).toBe("pending");

    store.replaceMessage("temp-abc", makeMsg({ id: "real-123" }));
    expect(useMessagingStore.getState().messages[0]._status).toBeUndefined();
  });
});

// ── Attachment preservation through replaceMessage ───────────────────────────
describe("replaceMessage attachment preservation", () => {
  beforeEach(() => {
    useMessagingStore.setState({
      activeConversationId: null,
      messages: [],
      unreadCounts: {},
      typingUsers: {},
      connectionStatus: "disconnected",
      offlineQueue: [],
      searchQuery: "",
      isSearchActive: false,
    });
  });

  it("replaceMessage preserves attachment data from merged message", () => {
    const store = useMessagingStore.getState();

    // Optimistic message with no attachments
    store.addMessage(
      makeMessage({
        id: "temp-abc",
        _status: "pending",
        attachments: [],
      })
    );

    // Replace with server response that has attachments merged in
    store.replaceMessage(
      "temp-abc",
      makeMessage({
        id: "real-123",
        attachments: [
          {
            id: "att-1",
            filename: "photo.jpg",
            file_type: "image/jpeg",
            file_size: 12345,
            uploaded_at: new Date().toISOString(),
          },
        ],
      })
    );

    const msgs = useMessagingStore.getState().messages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].id).toBe("real-123");
    expect(msgs[0].attachments).toHaveLength(1);
    expect(msgs[0].attachments[0].filename).toBe("photo.jpg");
  });

  it("replaceMessage with multiple attachments preserves all", () => {
    const store = useMessagingStore.getState();

    store.addMessage(
      makeMessage({ id: "temp-xyz", _status: "pending", attachments: [] })
    );

    store.replaceMessage(
      "temp-xyz",
      makeMessage({
        id: "real-456",
        attachments: [
          {
            id: "att-1",
            filename: "photo.jpg",
            file_type: "image/jpeg",
            file_size: 12345,
            uploaded_at: new Date().toISOString(),
          },
          {
            id: "att-2",
            filename: "document.pdf",
            file_type: "application/pdf",
            file_size: 54321,
            uploaded_at: new Date().toISOString(),
          },
        ],
      })
    );

    const msgs = useMessagingStore.getState().messages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].attachments).toHaveLength(2);
    expect(msgs[0].attachments[0].filename).toBe("photo.jpg");
    expect(msgs[0].attachments[1].filename).toBe("document.pdf");
  });
});

// ── Bug 1: connection.sync flat payload (frontend contract) ──────────────────
describe("connection.sync payload contract", () => {
  it("store correctly processes flat unread_counts from sync event", () => {
    // Simulates the frontend side of Bug 1 fix: connection.sync sends
    // unread_counts at top level (not nested in payload)
    const syncEvent = {
      type: "connection.sync" as const,
      version: 1,
      conversations: ["conv-1", "conv-2"],
      unread_counts: { "conv-1": 3, "conv-2": 0 },
    };

    // setUnreadCounts should accept the flat structure directly
    useMessagingStore.getState().setUnreadCounts(syncEvent.unread_counts);
    expect(useMessagingStore.getState().unreadCounts["conv-1"]).toBe(3);
    expect(useMessagingStore.getState().unreadCounts["conv-2"]).toBe(0);
    expect(useMessagingStore.getState().getTotalUnread()).toBe(3);
  });

  it("setUnreadCounts replaces entire record (not merge)", () => {
    const store = useMessagingStore.getState();
    store.updateUnreadCount("conv-old", 5);

    // Full sync replaces everything
    store.setUnreadCounts({ "conv-new": 2 });
    expect(useMessagingStore.getState().unreadCounts).toEqual({ "conv-new": 2 });
    expect(useMessagingStore.getState().unreadCounts["conv-old"]).toBeUndefined();
  });
});

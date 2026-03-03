import { useMessagingStore } from "@/stores/messaging";
import type { Message } from "@/types/messaging";

// ──────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: "msg-1",
    conversation: "conv-1",
    sender: {
      id: "u-1",
      email: "a@b.no",
      first_name: "A",
      last_name: "B",
    },
    content: "Hei",
    message_type: "message",
    is_internal: false,
    attachments: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

const INITIAL_STATE = {
  activeConversationId: null,
  messages: [],
  unreadCounts: {},
  typingUsers: {},
  connectionStatus: "disconnected" as const,
  offlineQueue: [],
  searchQuery: "",
  isSearchActive: false,
};

// ──────────────────────────────────────────────────
// 1. Store selector isolation
// ──────────────────────────────────────────────────

describe("Store selector isolation", () => {
  beforeEach(() => {
    useMessagingStore.setState(INITIAL_STATE);
  });

  it("updating unreadCounts does not change messages reference", () => {
    const msgsBefore = useMessagingStore.getState().messages;
    useMessagingStore.getState().updateUnreadCount("conv-1", 3);
    const msgsAfter = useMessagingStore.getState().messages;
    expect(msgsAfter).toBe(msgsBefore);
  });

  it("updating connectionStatus does not change messages reference", () => {
    const msgsBefore = useMessagingStore.getState().messages;
    useMessagingStore.getState().setConnectionStatus("connected");
    const msgsAfter = useMessagingStore.getState().messages;
    expect(msgsAfter).toBe(msgsBefore);
  });

  it("updating typingUsers does not change unreadCounts reference", () => {
    useMessagingStore.getState().setUnreadCounts({ "conv-1": 2 });
    const countsBefore = useMessagingStore.getState().unreadCounts;
    useMessagingStore.getState().setTyping("conv-1", "u-2", "Ola", true);
    const countsAfter = useMessagingStore.getState().unreadCounts;
    expect(countsAfter).toBe(countsBefore);
  });
});

// ──────────────────────────────────────────────────
// 2. Message deduplication
// ──────────────────────────────────────────────────

describe("Message deduplication", () => {
  beforeEach(() => {
    useMessagingStore.setState(INITIAL_STATE);
  });

  it("addMessage with same id is a no-op", () => {
    const msg = makeMessage({ id: "msg-dup" });
    useMessagingStore.getState().addMessage(msg);
    const refAfterFirst = useMessagingStore.getState().messages;

    useMessagingStore.getState().addMessage(msg);
    const refAfterSecond = useMessagingStore.getState().messages;

    expect(refAfterSecond).toHaveLength(1);
    // Reference equality — no new array was created
    expect(refAfterSecond).toBe(refAfterFirst);
  });

  it("prependMessages deduplicates by id", () => {
    useMessagingStore.getState().setMessages([
      makeMessage({ id: "msg-2", content: "Second" }),
    ]);

    useMessagingStore.getState().prependMessages([
      makeMessage({ id: "msg-1", content: "First" }),
      makeMessage({ id: "msg-2", content: "Duplicate" }),
    ]);

    const msgs = useMessagingStore.getState().messages;
    expect(msgs).toHaveLength(2);
    expect(msgs[0].id).toBe("msg-1");
    expect(msgs[1].id).toBe("msg-2");
    // The existing message's content should be preserved, not overwritten
    expect(msgs[1].content).toBe("Second");
  });

  it("replaceMessage handles WS arriving before HTTP response (temp + real -> single real)", () => {
    const store = useMessagingStore.getState();

    // 1. Optimistic add with temp ID
    store.addMessage(makeMessage({ id: "temp-abc", _status: "pending" }));

    // 2. WS delivers the real message before HTTP response
    store.addMessage(makeMessage({ id: "real-123", content: "Server" }));
    expect(useMessagingStore.getState().messages).toHaveLength(2);

    // 3. HTTP response triggers replaceMessage
    store.replaceMessage(
      "temp-abc",
      makeMessage({ id: "real-123", content: "Server" })
    );

    const msgs = useMessagingStore.getState().messages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].id).toBe("real-123");
    expect(msgs[0]._status).toBeUndefined();
  });
});

// ──────────────────────────────────────────────────
// 3. WebSocket event store updates
// ──────────────────────────────────────────────────

describe("WebSocket event store updates", () => {
  beforeEach(() => {
    useMessagingStore.setState(INITIAL_STATE);
  });

  it("message.new for non-active conversation only updates unreadCounts, not messages", () => {
    // Simulate: active conversation is conv-1, new message arrives for conv-2
    useMessagingStore.getState().setActiveConversation("conv-1");
    useMessagingStore.getState().setMessages([
      makeMessage({ id: "m1", conversation: "conv-1" }),
    ]);

    const msgsBefore = useMessagingStore.getState().messages;

    // Simulate what the WS handler does for a different conversation:
    // only update unread count, do NOT add message to the store
    const incomingConvId = "conv-2";
    const activeId = useMessagingStore.getState().activeConversationId;

    if (incomingConvId !== activeId) {
      useMessagingStore.getState().updateUnreadCount(incomingConvId, 1);
    }

    const msgsAfter = useMessagingStore.getState().messages;
    // messages array should be the same reference — untouched
    expect(msgsAfter).toBe(msgsBefore);
    expect(msgsAfter).toHaveLength(1);
    // unread count was updated
    expect(useMessagingStore.getState().unreadCounts["conv-2"]).toBe(1);
  });

  it("typing events set and clear correctly", () => {
    const store = useMessagingStore.getState();

    // typing.started
    store.setTyping("conv-1", "u-2", "Kari Nordmann", true);
    expect(useMessagingStore.getState().typingUsers["conv-1"]).toEqual([
      { userId: "u-2", userName: "Kari Nordmann" },
    ]);

    // Add a second user typing in the same conversation
    store.setTyping("conv-1", "u-3", "Per Hansen", true);
    expect(useMessagingStore.getState().typingUsers["conv-1"]).toHaveLength(2);

    // typing.stopped for first user
    store.setTyping("conv-1", "u-2", "Kari Nordmann", false);
    expect(useMessagingStore.getState().typingUsers["conv-1"]).toEqual([
      { userId: "u-3", userName: "Per Hansen" },
    ]);

    // typing.stopped for second user
    store.setTyping("conv-1", "u-3", "Per Hansen", false);
    expect(useMessagingStore.getState().typingUsers["conv-1"]).toEqual([]);
  });

  it("setting same user typing twice does not duplicate", () => {
    const store = useMessagingStore.getState();

    store.setTyping("conv-1", "u-2", "Kari", true);
    store.setTyping("conv-1", "u-2", "Kari", true);
    expect(useMessagingStore.getState().typingUsers["conv-1"]).toHaveLength(1);
  });

  it("getTotalUnread sums all conversation counts", () => {
    const store = useMessagingStore.getState();
    store.updateUnreadCount("conv-1", 3);
    store.updateUnreadCount("conv-2", 7);
    store.updateUnreadCount("conv-3", 0);
    expect(store.getTotalUnread()).toBe(10);
  });

  it("getTotalUnread returns 0 when no counts exist", () => {
    expect(useMessagingStore.getState().getTotalUnread()).toBe(0);
  });
});

// ──────────────────────────────────────────────────
// 4. Offline queue
// ──────────────────────────────────────────────────

describe("Offline queue", () => {
  beforeEach(() => {
    useMessagingStore.setState(INITIAL_STATE);
  });

  it("preserves order of queued messages", () => {
    const store = useMessagingStore.getState();

    store.addToOfflineQueue({
      conversationId: "conv-1",
      content: "First",
      is_internal: false,
    });
    store.addToOfflineQueue({
      conversationId: "conv-1",
      content: "Second",
      is_internal: false,
    });
    store.addToOfflineQueue({
      conversationId: "conv-2",
      content: "Third",
      is_internal: true,
    });

    const queue = useMessagingStore.getState().offlineQueue;
    expect(queue).toHaveLength(3);
    expect(queue[0].content).toBe("First");
    expect(queue[1].content).toBe("Second");
    expect(queue[2].content).toBe("Third");
    expect(queue[2].conversationId).toBe("conv-2");
    expect(queue[2].is_internal).toBe(true);
  });

  it("clearOfflineQueue removes all queued messages", () => {
    const store = useMessagingStore.getState();

    store.addToOfflineQueue({
      conversationId: "conv-1",
      content: "Pending 1",
    });
    store.addToOfflineQueue({
      conversationId: "conv-1",
      content: "Pending 2",
    });
    expect(useMessagingStore.getState().offlineQueue).toHaveLength(2);

    store.clearOfflineQueue();
    expect(useMessagingStore.getState().offlineQueue).toHaveLength(0);
    expect(useMessagingStore.getState().offlineQueue).toEqual([]);
  });

  it("setUnreadCounts replaces entirely (old keys gone)", () => {
    const store = useMessagingStore.getState();

    // Set initial counts
    store.updateUnreadCount("conv-old-1", 5);
    store.updateUnreadCount("conv-old-2", 3);
    expect(useMessagingStore.getState().unreadCounts["conv-old-1"]).toBe(5);

    // Full replacement via setUnreadCounts
    store.setUnreadCounts({ "conv-new": 2 });

    const counts = useMessagingStore.getState().unreadCounts;
    expect(counts).toEqual({ "conv-new": 2 });
    expect(counts["conv-old-1"]).toBeUndefined();
    expect(counts["conv-old-2"]).toBeUndefined();
  });
});

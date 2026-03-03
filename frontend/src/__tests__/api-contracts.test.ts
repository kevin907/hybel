/**
 * API contract tests: verify the frontend API client sends the correct
 * request shapes and expects the correct response structures.
 *
 * These tests mock fetch and verify:
 * 1. Request URLs match backend URL patterns
 * 2. Request bodies match backend serializer input shapes
 * 3. Response parsing handles the backend's exact output shape
 */

import * as api from "@/lib/api";
import type {
  ConversationListItem,
  Message,
  SearchResult,
  CursorPaginatedResponse,
  PaginatedResponse,
} from "@/types/messaging";

const originalFetch = global.fetch;
let fetchFn: jest.Mock;

function mockFetch(data: unknown, status = 200) {
  fetchFn = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    headers: new Headers({ "content-type": "application/json" }),
  });
  global.fetch = fetchFn;
}

afterEach(() => {
  global.fetch = originalFetch;
});

// ──────────────────────────────────────────────
// Contract: Conversation List (now cursor-paginated)
// ──────────────────────────────────────────────

describe("Conversation list API contract", () => {
  const sampleListResponse: CursorPaginatedResponse<ConversationListItem> = {
    next: null,
    previous: null,
    results: [
      {
        id: "conv-1",
        subject: "Test",
        conversation_type: "general",
        status: "open",
        property: null,
        unread_count: 0,
        last_message: {
          id: "lm-1",
          content: "Hello",
          sender: {
            id: "u1",
            email: "a@b.com",
            first_name: "Ola",
            last_name: "N",
          },
          created_at: "2026-01-01T00:00:00Z",
          is_internal: false,
        },
        participants: [
          { id: "u1", name: "Ola N", role: "tenant", side: "tenant_side" },
        ],
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ],
  };

  it("GET /conversations/ returns paginated response", async () => {
    mockFetch(sampleListResponse);
    const data = await api.getConversations();
    expect(data.results[0].id).toBe("conv-1");
    expect(data.results[0].last_message?.sender.email).toBe("a@b.com");
  });

  it("sends cursor URL for next page", async () => {
    mockFetch(sampleListResponse);
    await api.getConversations("http://localhost/api/conversations/?cursor=abc");
    expect(fetchFn).toHaveBeenCalledWith(
      expect.stringContaining("cursor=abc"),
      expect.any(Object)
    );
  });
});

// ──────────────────────────────────────────────
// Contract: Message List (cursor pagination)
// ──────────────────────────────────────────────

describe("Message list API contract", () => {
  const sampleMessages: CursorPaginatedResponse<Message> = {
    next: "http://api/conversations/c1/messages/?cursor=abc",
    previous: null,
    results: [
      {
        id: "m1",
        conversation: "c1",
        sender: {
          id: "u1",
          email: "a@b.com",
          first_name: "Ola",
          last_name: "N",
        },
        content: "Hello",
        message_type: "message",
        is_internal: false,
        attachments: [],
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ],
  };

  it("returns CursorPaginatedResponse (no count field)", async () => {
    mockFetch(sampleMessages);
    const data = await api.getMessages("c1");
    expect(data.next).toBeTruthy();
    expect(data.results).toHaveLength(1);
    expect((data as unknown as { count?: number }).count).toBeUndefined();
  });

  it("passes cursor URL for older messages", async () => {
    mockFetch(sampleMessages);
    await api.getMessages("c1", "http://api/messages/?cursor=xyz");
    expect(fetchFn).toHaveBeenCalledWith(
      expect.stringContaining("cursor=xyz"),
      expect.any(Object)
    );
  });
});

// ──────────────────────────────────────────────
// Contract: Send Message
// ──────────────────────────────────────────────

describe("Send message API contract", () => {
  it("POST body matches SendMessageRequest", async () => {
    const sampleMessage: Message = {
      id: "m1",
      conversation: "c1",
      sender: {
        id: "u1",
        email: "a@b.com",
        first_name: "T",
        last_name: "U",
      },
      content: "Hello",
      message_type: "message",
      is_internal: false,
      attachments: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    mockFetch(sampleMessage, 201);

    await api.sendMessage("c1", { content: "Hello", is_internal: false });

    const body = JSON.parse(fetchFn.mock.calls[0][1].body);
    expect(body).toEqual({ content: "Hello", is_internal: false });
  });

  it("response is a full Message object", async () => {
    const full: Message = {
      id: "m1",
      conversation: "c1",
      sender: {
        id: "u1",
        email: "a@b.com",
        first_name: "T",
        last_name: "U",
      },
      content: "Hello",
      message_type: "message",
      is_internal: false,
      attachments: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    mockFetch(full, 201);

    const msg = await api.sendMessage("c1", { content: "Hello" });
    expect(msg.id).toBe("m1");
    expect(msg.sender.email).toBe("a@b.com");
    expect(msg.attachments).toEqual([]);
  });
});

// ──────────────────────────────────────────────
// Contract: Search
// ──────────────────────────────────────────────

describe("Search API contract", () => {
  it("builds URLSearchParams correctly from SearchParams", async () => {
    mockFetch({ count: 0, next: null, previous: null, results: [] });
    await api.searchMessages({
      q: "vedlikehold",
      status: "open",
      has_attachment: true,
    });

    const url = fetchFn.mock.calls[0][0] as string;
    expect(url).toContain("q=vedlikehold");
    expect(url).toContain("status=open");
    expect(url).toContain("has_attachment=true");
  });

  it("search result has snippet field", async () => {
    const result: PaginatedResponse<SearchResult> = {
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: "m1",
          conversation_id: "c1",
          conversation_subject: "Test",
          sender: {
            id: "u1",
            email: "a@b.com",
            first_name: "T",
            last_name: "U",
          },
          content: "vedlikehold",
          snippet: "<b>vedlikehold</b> reparasjon",
          message_type: "message",
          is_internal: false,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    };
    mockFetch(result);

    const data = await api.searchMessages({ q: "vedlikehold" });
    expect(data.results[0].snippet).toContain("<b>");
  });
});

// ──────────────────────────────────────────────
// Contract: Gap-fill
// ──────────────────────────────────────────────

describe("Gap-fill API contract", () => {
  it("returns flat Message[] not paginated", async () => {
    const messages: Message[] = [
      {
        id: "m2",
        conversation: "c1",
        sender: {
          id: "u1",
          email: "a@b.com",
          first_name: "T",
          last_name: "U",
        },
        content: "Missed",
        message_type: "message",
        is_internal: false,
        attachments: [],
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ];
    mockFetch(messages);

    const data = await api.getMessagesSince("c1", "m1");
    expect(Array.isArray(data)).toBe(true);
    expect(data[0].id).toBe("m2");
  });

  it("sends since_id as query parameter", async () => {
    mockFetch([]);
    await api.getMessagesSince("c1", "msg-uuid-123");
    expect(fetchFn).toHaveBeenCalledWith(
      expect.stringContaining("since_id=msg-uuid-123"),
      expect.any(Object)
    );
  });
});

// ──────────────────────────────────────────────
// Contract: Mark Read
// ──────────────────────────────────────────────

describe("Mark read API contract", () => {
  it("POST body matches MarkReadRequest", async () => {
    mockFetch({ unread_count: 0 });
    await api.markAsRead("c1", "msg-123");

    const body = JSON.parse(fetchFn.mock.calls[0][1].body);
    expect(body).toEqual({ last_read_message_id: "msg-123" });
  });

  it("response has unread_count number", async () => {
    mockFetch({ unread_count: 0 });
    const resp = await api.markAsRead("c1", "msg-123");
    expect(resp.unread_count).toBe(0);
  });
});

// ──────────────────────────────────────────────
// Contract: Delegate
// ──────────────────────────────────────────────

describe("Delegate API contract", () => {
  it("POST body matches DelegateRequest", async () => {
    mockFetch({ id: "d1", assigned_to: "u2" }, 201);
    await api.delegate("c1", { assigned_to: "u2", note: "Ta over" });

    const body = JSON.parse(fetchFn.mock.calls[0][1].body);
    expect(body).toEqual({ assigned_to: "u2", note: "Ta over" });
  });

  it("response has id and assigned_to", async () => {
    mockFetch({ id: "d1", assigned_to: "u2" }, 201);
    const resp = await api.delegate("c1", { assigned_to: "u2" });
    expect(resp.id).toBe("d1");
    expect(resp.assigned_to).toBe("u2");
  });
});

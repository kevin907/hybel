import { ApiError } from "@/lib/api";

// Save original fetch
const originalFetch = global.fetch;

function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  const fn = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
    ...response,
  });
  global.fetch = fn;
  return fn;
}

afterEach(() => {
  global.fetch = originalFetch;
  // Clear csrftoken cookie
  Object.defineProperty(document, "cookie", { value: "", writable: true });
});

describe("api module", () => {
  // Re-import for each test to reset module state
  async function getApi() {
    return await import("@/lib/api");
  }

  describe("request()", () => {
    it("includes credentials", async () => {
      const fetchFn = mockFetch({
        json: () => Promise.resolve({ results: [] }),
      });
      const api = await getApi();
      await api.getConversations();

      expect(fetchFn).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ credentials: "include" })
      );
    });

    it("adds CSRF token for POST requests", async () => {
      Object.defineProperty(document, "cookie", {
        value: "csrftoken=abc123",
        writable: true,
      });
      const fetchFn = mockFetch({
        json: () =>
          Promise.resolve({ id: "msg-1", content: "test", sender: {} }),
      });
      const api = await getApi();
      await api.sendMessage("conv-1", { content: "test", is_internal: false });

      expect(fetchFn).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({ "X-CSRFToken": "abc123" }),
        })
      );
    });

    it("throws ApiError on non-OK responses", async () => {
      mockFetch({
        ok: false,
        status: 403,
        statusText: "Forbidden",
        json: () => Promise.resolve({ detail: "Ingen tilgang" }),
      });
      const api = await getApi();

      await expect(api.getConversation("conv-1")).rejects.toThrow(ApiError);
      await expect(api.getConversation("conv-1")).rejects.toMatchObject({
        status: 403,
      });
    });

    it("returns undefined for 204 responses", async () => {
      mockFetch({ status: 204, ok: true });
      const api = await getApi();
      const result = await api.removeParticipant("conv-1", "user-1");
      expect(result).toBeUndefined();
    });
  });

  describe("getConversations()", () => {
    it("calls the correct URL", async () => {
      const fetchFn = mockFetch({
        json: () => Promise.resolve({ results: [], count: 0 }),
      });
      const api = await getApi();
      await api.getConversations();

      expect(fetchFn).toHaveBeenCalledWith(
        "/api/conversations/?page=1",
        expect.any(Object)
      );
    });

    it("passes page parameter", async () => {
      const fetchFn = mockFetch({
        json: () => Promise.resolve({ results: [], count: 0 }),
      });
      const api = await getApi();
      await api.getConversations(3);

      expect(fetchFn).toHaveBeenCalledWith(
        "/api/conversations/?page=3",
        expect.any(Object)
      );
    });
  });

  describe("sendMessage()", () => {
    it("calls correct URL with POST", async () => {
      const fetchFn = mockFetch({
        json: () => Promise.resolve({ id: "msg-1" }),
      });
      const api = await getApi();
      await api.sendMessage("conv-1", {
        content: "Hei",
        is_internal: false,
      });

      expect(fetchFn).toHaveBeenCalledWith(
        "/api/conversations/conv-1/messages/",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  describe("addParticipant()", () => {
    it("calls correct URL with POST", async () => {
      const fetchFn = mockFetch({
        json: () => Promise.resolve({ id: "p-1", user_id: "u-1" }),
      });
      const api = await getApi();
      await api.addParticipant("conv-1", {
        user_id: "u-1",
        role: "contractor",
        side: "landlord_side",
      });

      expect(fetchFn).toHaveBeenCalledWith(
        "/api/conversations/conv-1/participants/",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  describe("uploadAttachment()", () => {
    it("uses FormData", async () => {
      const fetchFn = mockFetch({
        json: () =>
          Promise.resolve({ id: "a-1", filename: "test.pdf" }),
      });
      const api = await getApi();
      const file = new File(["content"], "test.pdf", {
        type: "application/pdf",
      });
      await api.uploadAttachment("conv-1", "msg-1", file);

      const callArgs = fetchFn.mock.calls[0];
      expect(callArgs[1].body).toBeInstanceOf(FormData);
    });
  });

  describe("searchMessages()", () => {
    it("builds URLSearchParams correctly", async () => {
      const fetchFn = mockFetch({
        json: () => Promise.resolve({ results: [], count: 0 }),
      });
      const api = await getApi();
      await api.searchMessages({
        q: "heisen",
        status: "open",
        has_attachment: true,
      });

      const url = fetchFn.mock.calls[0][0] as string;
      expect(url).toContain("q=heisen");
      expect(url).toContain("status=open");
      expect(url).toContain("has_attachment=true");
    });
  });

  describe("getAttachmentDownloadUrl()", () => {
    it("returns the correct URL", async () => {
      const api = await getApi();
      expect(api.getAttachmentDownloadUrl("att-1")).toBe(
        "/api/attachments/att-1/download/"
      );
    });
  });

  describe("markAsRead()", () => {
    it("calls correct URL with POST", async () => {
      const fetchFn = mockFetch({
        json: () => Promise.resolve({ unread_count: 0 }),
      });
      const api = await getApi();
      await api.markAsRead("conv-1", "msg-99");

      expect(fetchFn).toHaveBeenCalledWith(
        "/api/conversations/conv-1/read/",
        expect.objectContaining({ method: "POST" })
      );
    });
  });
});

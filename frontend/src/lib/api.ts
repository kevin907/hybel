import type {
  Attachment,
  ConversationDetail,
  ConversationListItem,
  CreateConversationRequest,
  CursorPaginatedResponse,
  DelegateRequest,
  Message,
  AddParticipantRequest,
  PaginatedResponse,
  SearchParams,
  SearchResult,
  SendMessageRequest,
  User,
} from "@/types/messaging";

const API_BASE = "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

function getCsrfToken(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : "";
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    headers["X-CSRFToken"] = getCsrfToken();
  }

  const res = await fetch(url, {
    credentials: "include",
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ──────────────────────────────────────────────────
// Conversations
// ──────────────────────────────────────────────────

export function getConversations(
  page = 1
): Promise<PaginatedResponse<ConversationListItem>> {
  return request(`/conversations/?page=${page}`);
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return request(`/conversations/${id}/`);
}

export function createConversation(
  data: CreateConversationRequest
): Promise<ConversationDetail> {
  return request("/conversations/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateConversation(
  id: string,
  data: { subject?: string; status?: string }
): Promise<ConversationDetail> {
  return request(`/conversations/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ──────────────────────────────────────────────────
// Messages
// ──────────────────────────────────────────────────

export function getMessages(
  conversationId: string,
  cursorUrl?: string
): Promise<CursorPaginatedResponse<Message>> {
  if (cursorUrl) {
    // cursorUrl is a full URL from the `next` field — extract the path + query
    const url = new URL(cursorUrl, window.location.origin);
    return request(`${url.pathname}${url.search}`);
  }
  return request(`/conversations/${conversationId}/messages/`);
}

export function getMessagesSince(
  conversationId: string,
  sinceId: string
): Promise<Message[]> {
  return request(`/conversations/${conversationId}/messages/since/?since_id=${sinceId}`);
}

export function sendMessage(
  conversationId: string,
  data: SendMessageRequest
): Promise<Message> {
  return request(`/conversations/${conversationId}/messages/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ──────────────────────────────────────────────────
// Participants
// ──────────────────────────────────────────────────

export function addParticipant(
  conversationId: string,
  data: AddParticipantRequest
): Promise<{ id: string; user_id: string }> {
  return request(`/conversations/${conversationId}/participants/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function removeParticipant(
  conversationId: string,
  userId: string
): Promise<void> {
  return request(`/conversations/${conversationId}/participants/${userId}/`, {
    method: "DELETE",
  });
}

// ──────────────────────────────────────────────────
// Attachments
// ──────────────────────────────────────────────────

export async function uploadAttachment(
  conversationId: string,
  messageId: string,
  file: File
): Promise<Attachment> {
  const formData = new FormData();
  formData.append("file", file);

  const url = `${API_BASE}/conversations/${conversationId}/messages/${messageId}/attachments/`;
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRFToken": getCsrfToken() },
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  return res.json();
}

export function getAttachmentDownloadUrl(attachmentId: string): string {
  return `${API_BASE}/attachments/${attachmentId}/download/`;
}

// ──────────────────────────────────────────────────
// Read State
// ──────────────────────────────────────────────────

export function markAsRead(
  conversationId: string,
  lastReadMessageId: string
): Promise<{ unread_count: number }> {
  return request(`/conversations/${conversationId}/read/`, {
    method: "POST",
    body: JSON.stringify({ last_read_message_id: lastReadMessageId }),
  });
}

// ──────────────────────────────────────────────────
// Delegation
// ──────────────────────────────────────────────────

export function delegate(
  conversationId: string,
  data: DelegateRequest
): Promise<{ id: string; assigned_to: string }> {
  return request(`/conversations/${conversationId}/delegate/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function removeDelegate(conversationId: string): Promise<void> {
  return request(`/conversations/${conversationId}/delegate/`, {
    method: "DELETE",
  });
}

// ──────────────────────────────────────────────────
// Search
// ──────────────────────────────────────────────────

export function searchMessages(
  params: SearchParams
): Promise<PaginatedResponse<SearchResult>> {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set("q", params.q);
  if (params.property) searchParams.set("property", params.property);
  if (params.status) searchParams.set("status", params.status);
  if (params.conversation_type)
    searchParams.set("conversation_type", params.conversation_type);
  if (params.has_attachment) searchParams.set("has_attachment", "true");
  if (params.date_from) searchParams.set("date_from", params.date_from);
  if (params.date_to) searchParams.set("date_to", params.date_to);
  if (params.unread_only) searchParams.set("unread_only", "true");
  if (params.page) searchParams.set("page", String(params.page));

  return request(`/conversations/search/?${searchParams.toString()}`);
}

// ──────────────────────────────────────────────────
// Auth
// ──────────────────────────────────────────────────

export function fetchCsrfToken(): Promise<{ csrfToken: string }> {
  return request("/auth/csrf/");
}

export function login(
  email: string,
  password: string
): Promise<{ id: string; email: string; first_name: string; last_name: string }> {
  return request("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<void> {
  return request("/auth/logout/", { method: "POST" });
}

export function getCurrentUser(): Promise<{
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}> {
  return request("/auth/me/");
}

// ──────────────────────────────────────────────────
// User Search (for autocomplete)
// ──────────────────────────────────────────────────

export function searchUsers(query: string): Promise<User[]> {
  return request(`/auth/users/search/?q=${encodeURIComponent(query)}`);
}

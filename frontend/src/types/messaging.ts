// ──────────────────────────────────────────────────
// Enums (match backend TextChoices)
// ──────────────────────────────────────────────────

export type ConversationType =
  | "general"
  | "maintenance"
  | "lease"
  | "rent_query";

export type ConversationStatus = "open" | "closed" | "archived";

export type ParticipantRole =
  | "tenant"
  | "landlord"
  | "property_manager"
  | "contractor"
  | "staff";

export type ParticipantSide = "tenant_side" | "landlord_side";

export type MessageType = "message" | "internal_comment" | "system_event";

// ──────────────────────────────────────────────────
// Core entities
// ──────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

export interface Attachment {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  uploaded_at: string;
}

export interface Participant {
  id: string;
  user: User;
  role: ParticipantRole;
  side: ParticipantSide;
  is_active: boolean;
  joined_at: string;
  left_at: string | null;
}

export interface Message {
  id: string;
  conversation: string;
  sender: User;
  content: string;
  message_type: MessageType;
  is_internal: boolean;
  attachments: Attachment[];
  created_at: string;
  updated_at: string;
}

export interface Delegation {
  id: string;
  assigned_to: User;
  assigned_by: User;
  note: string;
  is_active: boolean;
  assigned_at: string;
}

// ──────────────────────────────────────────────────
// Conversation list / detail shapes
// ──────────────────────────────────────────────────

export interface LastMessage {
  id: string;
  content: string;
  sender: User;
  created_at: string;
  is_internal: boolean;
}

export interface ConversationParticipantSummary {
  id: string;
  name: string;
  role: ParticipantRole;
  side: ParticipantSide;
}

export interface ConversationListItem {
  id: string;
  subject: string;
  conversation_type: ConversationType;
  status: ConversationStatus;
  property: string | null;
  unread_count: number;
  last_message: LastMessage | null;
  participants: ConversationParticipantSummary[];
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  subject: string;
  conversation_type: ConversationType;
  status: ConversationStatus;
  property: string | null;
  participants: Participant[];
  active_delegation: Delegation | null;
  created_at: string;
  updated_at: string;
}

// ──────────────────────────────────────────────────
// Search
// ──────────────────────────────────────────────────

export interface SearchResult {
  id: string;
  conversation_id: string;
  conversation_subject: string;
  sender: User;
  content: string;
  snippet: string;
  message_type: MessageType;
  is_internal: boolean;
  created_at: string;
}

// ──────────────────────────────────────────────────
// Pagination (DRF PageNumberPagination)
// ──────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ──────────────────────────────────────────────────
// Request bodies
// ──────────────────────────────────────────────────

export interface AddParticipantRequest {
  user_id: string;
  role: ParticipantRole;
  side: ParticipantSide;
}

export interface CreateConversationRequest {
  subject?: string;
  conversation_type?: ConversationType;
  property_id?: string | null;
  participants: AddParticipantRequest[];
  initial_message?: string;
}

export interface SendMessageRequest {
  content: string;
  is_internal?: boolean;
}

export interface DelegateRequest {
  assigned_to: string;
  note?: string;
}

export interface MarkReadRequest {
  last_read_message_id: string;
}

export interface SearchParams {
  q?: string;
  property?: string;
  status?: ConversationStatus;
  conversation_type?: ConversationType;
  has_attachment?: boolean;
  date_from?: string;
  date_to?: string;
  unread_only?: boolean;
  page?: number;
}

// ──────────────────────────────────────────────────
// WebSocket events
// ──────────────────────────────────────────────────

export interface WSMessageNew {
  type: "message.new";
  message_id: string;
  conversation_id: string;
  sender_id: string;
  content: string;
  message_type: MessageType;
  is_internal: boolean;
}

export interface WSReadUpdated {
  type: "read.updated";
  conversation_id: string;
  unread_count: number;
}

export interface WSParticipantChange {
  type: "participant.added" | "participant.removed";
  conversation_id: string;
  user_id: string;
  user_name: string;
}

export interface WSDelegationChange {
  type: "delegation.assigned" | "delegation.removed";
  conversation_id: string;
  assigned_to_id?: string;
  assigned_by_id?: string;
}

export interface WSTyping {
  type: "typing.started" | "typing.stopped";
  conversation_id: string;
  user_id: string;
  user_name: string;
}

export interface WSConnectionSync {
  type: "connection.sync";
  conversations: string[];
  unread_counts: Record<string, number>;
}

export type WSEvent =
  | WSMessageNew
  | WSReadUpdated
  | WSParticipantChange
  | WSDelegationChange
  | WSTyping
  | WSConnectionSync;

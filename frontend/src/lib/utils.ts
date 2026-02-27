import { clsx, type ClassValue } from "clsx";
import {
  formatDistanceToNow,
  format,
  isToday,
  isYesterday,
} from "date-fns";
import { nb } from "date-fns/locale";
import type {
  ConversationStatus,
  ConversationType,
  ParticipantRole,
  ParticipantSide,
} from "@/types/messaging";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  return formatDistanceToNow(date, { addSuffix: true, locale: nb });
}

export function formatMessageTime(dateStr: string): string {
  const date = new Date(dateStr);
  const time = format(date, "HH:mm", { locale: nb });

  if (isToday(date)) return time;
  if (isYesterday(date)) return `i går ${time}`;
  return format(date, "d. MMM HH:mm", { locale: nb });
}

export function formatShortTime(dateStr: string): string {
  const date = new Date(dateStr);
  if (isToday(date)) return format(date, "HH:mm", { locale: nb });
  if (isYesterday(date)) return "i går";
  return format(date, "d. MMM", { locale: nb });
}

export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + "…";
}

export function getInitials(firstName: string, lastName: string): string {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}

export function getParticipantDisplayName(participant: {
  name?: string;
  first_name?: string;
  last_name?: string;
}): string {
  if (participant.name) return participant.name;
  return `${participant.first_name || ""} ${participant.last_name || ""}`.trim();
}

export function getRoleLabelNO(role: ParticipantRole): string {
  const labels: Record<ParticipantRole, string> = {
    tenant: "Leietaker",
    landlord: "Utleier",
    property_manager: "Forvalter",
    contractor: "Håndverker",
    staff: "Stab",
  };
  return labels[role] || role;
}

export function getTypeLabelNO(type: ConversationType): string {
  const labels: Record<ConversationType, string> = {
    general: "Generell",
    maintenance: "Vedlikehold",
    lease: "Leiekontrakt",
    rent_query: "Leiespørsmål",
  };
  return labels[type] || type;
}

export function getStatusLabelNO(status: ConversationStatus): string {
  const labels: Record<ConversationStatus, string> = {
    open: "Åpen",
    closed: "Lukket",
    archived: "Arkivert",
  };
  return labels[status] || status;
}

export function getSideLabelNO(side: ParticipantSide): string {
  const labels: Record<ParticipantSide, string> = {
    tenant_side: "Leietaker-side",
    landlord_side: "Utleier-side",
  };
  return labels[side] || side;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ──────────────────────────────────────────────────
// Option arrays for <select> elements (single source of truth)
// ──────────────────────────────────────────────────

export const ROLE_OPTIONS: { value: ParticipantRole; label: string }[] = [
  { value: "tenant", label: "Leietaker" },
  { value: "landlord", label: "Utleier" },
  { value: "property_manager", label: "Forvalter" },
  { value: "contractor", label: "Håndverker" },
  { value: "staff", label: "Stab" },
];

export const SIDE_OPTIONS: { value: ParticipantSide; label: string }[] = [
  { value: "tenant_side", label: "Leietaker-side" },
  { value: "landlord_side", label: "Utleier-side" },
];

export const TYPE_OPTIONS: { value: ConversationType; label: string }[] = [
  { value: "general", label: "Generell" },
  { value: "maintenance", label: "Vedlikehold" },
  { value: "lease", label: "Leiekontrakt" },
  { value: "rent_query", label: "Leiespørsmål" },
];

export const STATUS_OPTIONS: { value: ConversationStatus; label: string }[] = [
  { value: "open", label: "Åpen" },
  { value: "closed", label: "Lukket" },
  { value: "archived", label: "Arkivert" },
];

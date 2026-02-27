export const queryKeys = {
  conversations: ["conversations"] as const,
  conversation: (id: string) => ["conversation", id] as const,
  messages: (id: string) => ["messages", id] as const,
  search: (params: Record<string, unknown>) => ["search", params] as const,
  userSearch: (query: string) => ["user-search", query] as const,
};

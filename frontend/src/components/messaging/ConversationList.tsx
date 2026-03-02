"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "@/lib/api";
import { useMessagingStore } from "@/stores/messaging";
import { useDebounce } from "@/hooks/useDebounce";
import Link from "next/link";
import { queryKeys } from "@/lib/queryKeys";
import Icon from "@/components/ui/Icon";
import ConversationItem from "./ConversationItem";
import SearchBar from "./SearchBar";
import SearchFilters, { type FilterValues } from "./SearchFilters";
import SearchResults from "./SearchResults";

export default function ConversationListPanel() {
  const { searchQuery, isSearchActive } = useMessagingStore();
  const [filters, setFilters] = useState<FilterValues>({});

  const debouncedQuery = useDebounce(searchQuery, 300);

  // Fetch conversation list — React Query cache is the single source of truth
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.conversations,
    queryFn: () => api.getConversations(),
  });

  // Fetch search results (search mode)
  const { data: searchData, isLoading: searchLoading } = useQuery({
    queryKey: ["search", debouncedQuery, filters],
    queryFn: () =>
      api.searchMessages({
        q: debouncedQuery || undefined,
        ...filters,
      }),
    enabled: isSearchActive || Object.values(filters).some((v) => v !== undefined && v !== false),
  });

  const conversations = data?.results ?? [];

  const showSearch =
    isSearchActive || Object.values(filters).some((v) => v !== undefined && v !== false);

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <div className="flex items-center gap-3">
          <button className="text-gray-500 hover:text-gray-700">
            <Icon name="menu" size={18} />
          </button>
          <h2 className="text-[15px] font-semibold text-gray-900">
            Alle samtaler
          </h2>
        </div>
        <Link
          href="/meldinger/ny"
          className="flex h-7 w-7 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          title="Ny samtale"
        >
          <Icon name="plus" size={18} />
        </Link>
      </div>

      {/* Search */}
      <SearchBar />
      <SearchFilters filters={filters} onChange={setFilters} />

      {/* Content: search results or conversation list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {showSearch ? (
          searchLoading ? (
            <ConversationListSkeleton />
          ) : (
            <SearchResults
              results={searchData?.results || []}
              totalCount={searchData?.count || 0}
            />
          )
        ) : isLoading ? (
          <ConversationListSkeleton />
        ) : conversations.length === 0 ? (
          <p className="px-4 py-4 text-sm text-gray-500">
            Fant ingen meldinger
          </p>
        ) : (
          conversations.map((conv) => (
            <ConversationItem key={conv.id} conversation={conv} />
          ))
        )}
      </div>
    </>
  );
}

function ConversationListSkeleton() {
  return (
    <div className="space-y-0">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex gap-3 px-4 py-3 animate-pulse">
          <div className="h-10 w-10 rounded-full bg-gray-200" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-2/3 rounded bg-gray-200" />
            <div className="h-3 w-full rounded bg-gray-100" />
          </div>
        </div>
      ))}
    </div>
  );
}

"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDebounce } from "@/hooks/useDebounce";
import * as api from "@/lib/api";
import type { User } from "@/types/messaging";
import { cn } from "@/lib/utils";
import { queryKeys } from "@/lib/queryKeys";
import Avatar from "@/components/ui/Avatar";

interface Props {
  onSelect: (user: User) => void;
  onClear?: () => void;
  selectedUser?: User | null;
  placeholder?: string;
  className?: string;
}

export default function UserAutocomplete({
  onSelect,
  onClear,
  selectedUser,
  placeholder = "Søk etter bruker...",
  className,
}: Props) {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const debouncedQuery = useDebounce(query, 300);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: users = [], isLoading } = useQuery({
    queryKey: queryKeys.userSearch(debouncedQuery),
    queryFn: () => api.searchUsers(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
  });

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (selectedUser) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm",
          className
        )}
      >
        <Avatar
          firstName={selectedUser.first_name}
          lastName={selectedUser.last_name}
          size="xs"
        />
        <span className="flex-1 truncate text-gray-700">
          {selectedUser.first_name} {selectedUser.last_name}
        </span>
        {onClear && (
          <button
            onClick={onClear}
            className="text-gray-400 hover:text-gray-600"
            type="button"
          >
            ×
          </button>
        )}
      </div>
    );
  }

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setIsOpen(true);
        }}
        onFocus={() => query.length >= 2 && setIsOpen(true)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
      />

      {isOpen && debouncedQuery.length >= 2 && (
        <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg">
          {isLoading ? (
            <div className="px-3 py-2 text-xs text-gray-400">Søker...</div>
          ) : users.length === 0 ? (
            <div className="px-3 py-2 text-xs text-gray-400">
              Ingen brukere funnet
            </div>
          ) : (
            <ul className="max-h-48 overflow-y-auto py-1">
              {users.map((user) => (
                <li key={user.id}>
                  <button
                    onClick={() => {
                      onSelect(user);
                      setQuery("");
                      setIsOpen(false);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50"
                    type="button"
                  >
                    <Avatar
                      firstName={user.first_name}
                      lastName={user.last_name}
                      size="sm"
                    />
                    <div>
                      <p className="text-xs font-medium text-gray-800">
                        {user.first_name} {user.last_name}
                      </p>
                      <p className="text-[10px] text-gray-400">{user.email}</p>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

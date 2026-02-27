"use client";

import { useMessagingStore } from "@/stores/messaging";
import Icon from "@/components/ui/Icon";

export default function SearchBar() {
  const { searchQuery, setSearchQuery } = useMessagingStore();

  return (
    <div className="px-4 py-2">
      <div className="relative">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Søk i meldinger..."
          className="w-full rounded-md border border-gray-200 bg-white py-2 pl-3 pr-8 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
        />
        <div className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400">
          <Icon name="search" size={14} />
        </div>
      </div>
    </div>
  );
}

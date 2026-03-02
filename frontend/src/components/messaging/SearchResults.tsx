"use client";

import Link from "next/link";
import type { SearchResult } from "@/types/messaging";
import { useMessagingStore } from "@/stores/messaging";
import { formatShortTime } from "@/lib/utils";
import Icon from "@/components/ui/Icon";

interface Props {
  results: SearchResult[];
  totalCount: number;
}

export default function SearchResults({ results, totalCount }: Props) {
  const setActive = useMessagingStore((s) => s.setActiveConversation);

  if (results.length === 0) {
    return (
      <p className="px-4 py-4 text-sm text-gray-500">Fant ingen meldinger</p>
    );
  }

  return (
    <div>
      <p className="px-4 py-2 text-micro text-gray-400">
        {totalCount} treff
      </p>
      {results.map((result) => (
        <Link
          key={result.id}
          href={`/meldinger/${result.conversation_id}`}
          onClick={() => setActive(result.conversation_id)}
          className="block border-b border-gray-50 px-4 py-3 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate text-xs font-medium text-gray-800">
              {result.conversation_subject || "Samtale"}
            </span>
            <span className="shrink-0 text-micro text-gray-400">
              {formatShortTime(result.created_at)}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-gray-500">
            {result.sender.first_name} {result.sender.last_name}
          </p>
          <p
            className="mt-1 text-xs text-gray-600 line-clamp-2"
            dangerouslySetInnerHTML={{
              __html: sanitizeSnippet(result.snippet),
            }}
          />
          {result.is_internal && (
            <span className="mt-1 inline-flex items-center gap-1 text-micro text-amber-600">
              <Icon name="lock" size={8} />
              Intern
            </span>
          )}
        </Link>
      ))}
    </div>
  );
}

function sanitizeSnippet(html: string): string {
  // Preserve only <b></b> tags from ts_headline, escape everything else
  const OPEN = "\u0000BOPEN\u0000";
  const CLOSE = "\u0000BCLOSE\u0000";

  let safe = html.replace(/<b>/g, OPEN).replace(/<\/b>/g, CLOSE);

  safe = safe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  return safe.replaceAll(OPEN, "<b>").replaceAll(CLOSE, "</b>");
}

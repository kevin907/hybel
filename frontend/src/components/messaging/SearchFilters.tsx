"use client";

import { useState } from "react";
import type { ConversationStatus, ConversationType } from "@/types/messaging";
import { cn, STATUS_OPTIONS, TYPE_OPTIONS } from "@/lib/utils";
import Icon from "@/components/ui/Icon";

export interface FilterValues {
  status?: ConversationStatus;
  conversation_type?: ConversationType;
  has_attachment?: boolean;
  date_from?: string;
  date_to?: string;
  unread_only?: boolean;
}

interface Props {
  filters: FilterValues;
  onChange: (filters: FilterValues) => void;
}

export default function SearchFilters({ filters, onChange }: Props) {
  const [expanded, setExpanded] = useState(false);

  const activeCount = Object.values(filters).filter(
    (v) => v !== undefined && v !== false && v !== ""
  ).length;

  const reset = () => onChange({});

  return (
    <div className="px-4 pb-2">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className={cn(
            "flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors",
            expanded ? "bg-blue-50 text-blue-600" : "text-gray-500 hover:bg-gray-100"
          )}
        >
          <Icon name="filter" size={12} />
          Filtre
          {activeCount > 0 && (
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-blue-500 text-[9px] text-white">
              {activeCount}
            </span>
          )}
        </button>
        {activeCount > 0 && (
          <button
            onClick={reset}
            className="text-[10px] text-gray-400 hover:text-gray-600"
          >
            Nullstill
          </button>
        )}
      </div>

      {expanded && (
        <div className="mt-2 grid grid-cols-2 gap-2">
          <select
            value={filters.status || ""}
            onChange={(e) =>
              onChange({
                ...filters,
                status: (e.target.value || undefined) as ConversationStatus | undefined,
              })
            }
            className="rounded-md border border-gray-200 px-2 py-1.5 text-xs outline-none"
          >
            <option value="">Alle statuser</option>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <select
            value={filters.conversation_type || ""}
            onChange={(e) =>
              onChange({
                ...filters,
                conversation_type: (e.target.value || undefined) as ConversationType | undefined,
              })
            }
            className="rounded-md border border-gray-200 px-2 py-1.5 text-xs outline-none"
          >
            <option value="">Alle typer</option>
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <input
            type="date"
            value={filters.date_from || ""}
            onChange={(e) =>
              onChange({ ...filters, date_from: e.target.value || undefined })
            }
            placeholder="Fra"
            className="rounded-md border border-gray-200 px-2 py-1.5 text-xs outline-none"
          />

          <input
            type="date"
            value={filters.date_to || ""}
            onChange={(e) =>
              onChange({ ...filters, date_to: e.target.value || undefined })
            }
            placeholder="Til"
            className="rounded-md border border-gray-200 px-2 py-1.5 text-xs outline-none"
          />

          <label className="col-span-2 flex items-center gap-2 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={filters.has_attachment || false}
              onChange={(e) =>
                onChange({
                  ...filters,
                  has_attachment: e.target.checked || undefined,
                })
              }
              className="rounded"
            />
            Kun med vedlegg
          </label>

          <label className="col-span-2 flex items-center gap-2 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={filters.unread_only || false}
              onChange={(e) =>
                onChange({
                  ...filters,
                  unread_only: e.target.checked || undefined,
                })
              }
              className="rounded"
            />
            Kun uleste
          </label>
        </div>
      )}
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  AddParticipantRequest,
  ConversationType,
  User,
} from "@/types/messaging";
import { cn, TYPE_OPTIONS, ROLE_OPTIONS, SIDE_OPTIONS } from "@/lib/utils";
import UserAutocomplete from "@/components/ui/UserAutocomplete";

export default function NewConversationPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [subject, setSubject] = useState("");
  const [conversationType, setConversationType] =
    useState<ConversationType>("general");
  const [initialMessage, setInitialMessage] = useState("");
  const [participants, setParticipants] = useState<AddParticipantRequest[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<Record<number, User>>({});

  // Pre-fill with the current user as the first participant
  useEffect(() => {
    if (user && participants.length === 0) {
      setParticipants([
        { user_id: user.id, role: "landlord", side: "landlord_side" },
        { user_id: "", role: "tenant", side: "tenant_side" },
      ]);
    }
  }, [user, participants.length]);

  const createMutation = useMutation({
    mutationFn: () =>
      api.createConversation({
        subject,
        conversation_type: conversationType,
        participants: participants.filter((p) => p.user_id.trim()),
        initial_message: initialMessage,
      }),
    onSuccess: (conv) => {
      router.push(`/meldinger/${conv.id}`);
    },
  });

  const updateParticipant = (
    index: number,
    field: keyof AddParticipantRequest,
    value: string
  ) => {
    const updated = [...participants];
    updated[index] = { ...updated[index], [field]: value };
    setParticipants(updated);
  };

  const addParticipantRow = () => {
    setParticipants([
      ...participants,
      { user_id: "", role: "tenant", side: "tenant_side" },
    ]);
  };

  const removeParticipantRow = (index: number) => {
    if (participants.length <= 1) return;
    setParticipants(participants.filter((_, i) => i !== index));
    setSelectedUsers((prev) => {
      const next: Record<number, User> = {};
      Object.entries(prev).forEach(([key, val]) => {
        const k = Number(key);
        if (k < index) next[k] = val;
        else if (k > index) next[k - 1] = val;
      });
      return next;
    });
  };

  const hasValidParticipant = participants.some((p) => p.user_id.trim());

  return (
    <div className="flex flex-1 flex-col">
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <h2 className="text-lg font-semibold text-gray-900">Ny samtale</h2>
      </div>

      <div className="flex-1 overflow-y-auto bg-cream p-6">
        <div className="mx-auto max-w-lg space-y-5">
          {/* Subject */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Emne (valgfritt)
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="F.eks. Vannlekkasje på badet"
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
            />
          </div>

          {/* Type */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Type
            </label>
            <select
              value={conversationType}
              onChange={(e) =>
                setConversationType(e.target.value as ConversationType)
              }
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
            >
              {TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Participants */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Deltakere
            </label>
            <div className="space-y-2">
              {participants.map((p, i) => {
                const isCreator = p.user_id === user?.id;
                return (
                  <div key={i} className="flex gap-2">
                    {isCreator ? (
                      <div className="flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">
                        {user.first_name} {user.last_name} (deg)
                      </div>
                    ) : (
                      <UserAutocomplete
                        selectedUser={selectedUsers[i] ?? null}
                        onSelect={(u) => {
                          updateParticipant(i, "user_id", u.id);
                          setSelectedUsers((prev) => ({ ...prev, [i]: u }));
                        }}
                        onClear={() => {
                          updateParticipant(i, "user_id", "");
                          setSelectedUsers((prev) => {
                            const next = { ...prev };
                            delete next[i];
                            return next;
                          });
                        }}
                        className="flex-1"
                      />
                    )}
                    <select
                      value={p.role}
                      onChange={(e) =>
                        updateParticipant(i, "role", e.target.value)
                      }
                      className="w-32 rounded-lg border border-gray-200 bg-white px-2 py-2 text-sm"
                    >
                      {ROLE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    <select
                      value={p.side}
                      onChange={(e) =>
                        updateParticipant(i, "side", e.target.value)
                      }
                      className="w-32 rounded-lg border border-gray-200 bg-white px-2 py-2 text-sm"
                    >
                      {SIDE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    {participants.length > 1 && !isCreator && (
                      <button
                        onClick={() => removeParticipantRow(i)}
                        className="text-gray-400 hover:text-red-500"
                      >
                        ×
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
            <button
              onClick={addParticipantRow}
              className="mt-2 text-xs text-blue-500 hover:text-blue-700"
            >
              + Legg til deltaker
            </button>
          </div>

          {/* Initial message */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Melding
            </label>
            <textarea
              value={initialMessage}
              onChange={(e) => setInitialMessage(e.target.value)}
              placeholder="Skriv din første melding..."
              rows={4}
              className="w-full resize-none rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
            />
          </div>

          {/* Error */}
          {createMutation.isError && (
            <p className="text-sm text-red-500">
              Kunne ikke opprette samtale. Prøv igjen.
            </p>
          )}

          {/* Submit */}
          <button
            onClick={() => createMutation.mutate()}
            disabled={!hasValidParticipant || createMutation.isPending}
            className={cn(
              "w-full rounded-lg py-2.5 text-sm font-medium text-white transition-colors",
              hasValidParticipant && !createMutation.isPending
                ? "bg-primary hover:bg-primary-dark"
                : "bg-gray-300 cursor-not-allowed"
            )}
          >
            {createMutation.isPending ? "Oppretter..." : "Opprett samtale"}
          </button>
        </div>
      </div>
    </div>
  );
}

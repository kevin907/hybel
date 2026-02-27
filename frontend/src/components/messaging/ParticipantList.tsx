"use client";

import { useState } from "react";
import type {
  Participant,
  ParticipantRole,
  ParticipantSide,
  User,
} from "@/types/messaging";
import { cn, getRoleLabelNO, ROLE_OPTIONS, SIDE_OPTIONS } from "@/lib/utils";
import UserAutocomplete from "@/components/ui/UserAutocomplete";
import Avatar from "@/components/ui/Avatar";
import Icon from "@/components/ui/Icon";

interface Props {
  participants: Participant[];
  isLandlordSide: boolean;
  onRemove?: (userId: string) => void;
  onAdd?: (data: {
    user_id: string;
    role: ParticipantRole;
    side: ParticipantSide;
  }) => void;
}

export default function ParticipantList({
  participants,
  isLandlordSide,
  onRemove,
  onAdd,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newUser, setNewUser] = useState<User | null>(null);
  const [newRole, setNewRole] = useState<ParticipantRole>("contractor");
  const [newSide, setNewSide] = useState<ParticipantSide>("landlord_side");
  const active = participants.filter((p) => p.is_active);

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700"
      >
        <Icon name="users" size={12} />
        {active.length} deltakere
        <Icon
          name="chevron-down"
          size={10}
          className={cn("transition-transform", expanded && "rotate-180")}
        />
      </button>

      {expanded && (
        <div className="mt-2 space-y-1">
          {participants.map((p) => (
            <div
              key={p.id}
              className={cn(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
                !p.is_active && "opacity-50"
              )}
            >
              <Avatar
                firstName={p.user.first_name}
                lastName={p.user.last_name}
                size="md"
                inactive={!p.is_active}
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium text-gray-800">
                  {p.user.first_name} {p.user.last_name}
                </p>
                <p className="text-[10px] text-gray-400">
                  {getRoleLabelNO(p.role)}
                  {!p.is_active && " · Fjernet"}
                </p>
              </div>
              {isLandlordSide && p.is_active && onRemove && (
                <button
                  onClick={() => onRemove(p.user.id)}
                  className="text-[10px] text-gray-400 hover:text-red-500"
                >
                  Fjern
                </button>
              )}
            </div>
          ))}

          {isLandlordSide && onAdd && (
            <>
              {showAddForm ? (
                <div className="mt-2 space-y-2 rounded-md border border-gray-200 bg-white p-2">
                  <UserAutocomplete
                    selectedUser={newUser}
                    onSelect={setNewUser}
                    onClear={() => setNewUser(null)}
                    placeholder="Søk etter deltaker..."
                  />
                  <div className="flex gap-2">
                    <select
                      value={newRole}
                      onChange={(e) =>
                        setNewRole(e.target.value as ParticipantRole)
                      }
                      className="flex-1 rounded-md border border-gray-200 px-1 py-1 text-xs"
                    >
                      {ROLE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    <select
                      value={newSide}
                      onChange={(e) =>
                        setNewSide(e.target.value as ParticipantSide)
                      }
                      className="flex-1 rounded-md border border-gray-200 px-1 py-1 text-xs"
                    >
                      {SIDE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        if (newUser) {
                          onAdd({
                            user_id: newUser.id,
                            role: newRole,
                            side: newSide,
                          });
                          setNewUser(null);
                          setShowAddForm(false);
                        }
                      }}
                      className="rounded-md bg-blue-500 px-2 py-1 text-[10px] font-medium text-white hover:bg-blue-600"
                    >
                      Legg til
                    </button>
                    <button
                      onClick={() => {
                        setNewUser(null);
                        setShowAddForm(false);
                      }}
                      className="rounded-md px-2 py-1 text-[10px] text-gray-500 hover:text-gray-700"
                    >
                      Avbryt
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowAddForm(true)}
                  className="mt-2 text-[10px] text-blue-500 hover:text-blue-700"
                >
                  + Legg til deltaker
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

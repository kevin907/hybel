"use client";

import { useMessagingStore } from "@/stores/messaging";

export default function ConnectionStatus() {
  const status = useMessagingStore((s) => s.connectionStatus);

  if (status === "connected") return null;

  return (
    <div
      role="alert"
      className={
        status === "reconnecting"
          ? "flex items-center gap-2 bg-amber-50 px-4 py-2 text-xs text-amber-700"
          : "flex items-center gap-2 bg-red-50 px-4 py-2 text-xs text-red-700"
      }
    >
      <span
        className={
          status === "reconnecting"
            ? "h-2 w-2 rounded-full bg-amber-500 animate-pulse"
            : "h-2 w-2 rounded-full bg-red-500"
        }
      />
      {status === "reconnecting"
        ? "Kobler til på nytt..."
        : "Frakoblet. Meldinger sendes når tilkoblingen er tilbake."}
    </div>
  );
}
